"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
# pylint: disable=too-many-lines

import base64
import codecs
from collections import OrderedDict
import copy
import datetime
import errno
import fnmatch
import getpass
from graphlib import TopologicalSorter
import importlib.machinery
import inspect
from io import StringIO
import json
import logging
import os
import re
import shutil
import sys
import tarfile
import tempfile
import types

import jinja2
import requests

from vcsinfo import detect_vcs, VCSUnsupported, VCSMissingRevision

from buildrunner import docker
from buildrunner.docker.builder import DockerBuilder
from buildrunner.errors import (
    BuildRunnerConfigurationError,
    BuildRunnerProcessingError,
    BuildRunnerVersionError,
    ConfigVersionFormatError,
    ConfigVersionTypeError,
)
from buildrunner.sshagent import load_ssh_key_from_file, load_ssh_key_from_str
from buildrunner.steprunner import BuildStepRunner
from buildrunner.steprunner.tasks.push import sanitize_tag
from buildrunner.utils import (
    ConsoleLogger,
    checksum,
    epoch_time,
    hash_sha1,
    load_config,
)
from . import fetch
# from . import BuildRunnerVersionError, ConfigVersionFormatError, ConfigVersionTypeError

LOGGER = logging.getLogger(__name__)

__version__ = 'DEVELOPMENT'
try:
    _VERSION_FILE = os.path.join(os.path.dirname(__file__), 'version.py')
    if os.path.exists(_VERSION_FILE):
        loader = importlib.machinery.SourceFileLoader('buildrunnerversion', _VERSION_FILE)
        _VERSION_MOD = types.ModuleType(loader.name)
        loader.exec_module(_VERSION_MOD)
        __version__ = getattr(_VERSION_MOD, '__version__', __version__)
except:
    pass

MASTER_GLOBAL_CONFIG_FILE = '/etc/buildrunner/buildrunner.yaml'
DEFAULT_GLOBAL_CONFIG_FILES = [
    MASTER_GLOBAL_CONFIG_FILE,
    '~/.buildrunner.yaml',
]

DEFAULT_CACHES_ROOT = '~/.buildrunner/caches'
DEFAULT_RUN_CONFIG_FILES = ['buildrunner.yaml', 'gauntlet.yaml']
RESULTS_DIR = 'buildrunner.results'

SOURCE_DOCKERFILE = os.path.join(os.path.dirname(__file__), 'SourceDockerfile')


class BuildRunner:  # pylint: disable=too-many-instance-attributes
    """
    Class used to manage running a build.
    """

    CONTEXT_ENV_PREFIXES = ['BUILDRUNNER_', 'VCSINFO_', 'PACKAGER_', 'GAUNTLET_']

    def _get_config_context(self, ctx=None):
        """
        Generate the Jinja configuration context for substitution

        Args:
          ctx (dict): A dictionary of key/values to be merged
          over the default, generated context.

        Returns:
          dict: A dictionary of key/values to be substituted
        """

        context = {
            'BUILDRUNNER_BUILD_NUMBER': str(self.build_number),
            'BUILDRUNNER_BUILD_ID': str(self.build_id),
            'BUILDRUNNER_BUILD_DOCKER_TAG': str(sanitize_tag(self.build_id)),
            'BUILDRUNNER_BUILD_TIME': str(self.build_time),
            'VCSINFO_NAME': str(self.vcs.name),
            'VCSINFO_BRANCH': str(self.vcs.branch),
            'VCSINFO_NUMBER': str(self.vcs.number),
            'VCSINFO_ID': str(self.vcs.id),
            'VCSINFO_SHORT_ID': str(self.vcs.id)[:7],
            'VCSINFO_MODIFIED': str(self.vcs.modified),
            'BUILDRUNNER_STEPS': self.steps_to_run,
        }

        if ctx:
            context.update(ctx)

        for env_name, env_value in os.environ.items():
            for prefix in self.CONTEXT_ENV_PREFIXES:
                if env_name.startswith(prefix):
                    context[env_name] = env_value

        return context

    @staticmethod
    def _raise_exception_jinja(message):
        """
        Raises an exception from a jinja template.
        """
        raise Exception(message)

    def _log_generated_file(self, file_name, file_contents):
        '''
        Conditionally log the contents of a generated file.
        '''
        if self.log_generated_files:
            self.log.write(f'Generated contents of {file_name}:\n')
            for line in file_contents.splitlines():
                self.log.write(f'{line}\n')

    def _read_yaml_file(self, filename):
        """
        Reads a file in the local workspace as Jinja-templated
        YAML and returns the contents.
        Throws an error on failure.
        """
        with codecs.open(filename, 'r', encoding='utf-8') as _file:
            jtemplate = jinja2.Template(_file.read())
        context = copy.deepcopy(self.env)
        file_contents = jtemplate.render(context)
        self._log_generated_file(filename, file_contents)
        return load_config(StringIO(file_contents), filename)

    def _load_config_files(self, cfg_files=None, ctx=None, log_file=True):
        """
        Load config files templating them with Jinja and parsing the YAML.

        Args:
            cfg_files (list):  List of configuration files
            ctx (dict): context object to load into config_context
            log_file (boolean): will write out the generated config to log(s)
                Default: True

        Returns:
          multi-structure: configuration keys and values
        """

        cfg_files = cfg_files or []

        username = getpass.getuser()
        homedir = os.path.expanduser('~')

        context = ctx or {}
        for cfg in cfg_files:
            cfg_path = os.path.realpath(os.path.expanduser(cfg))
            if os.path.exists(cfg_path):
                ctx = self._load_config(cfg_path, context, log_file=log_file)
                if ctx is None:
                    # Empty config file
                    continue

                # Only allow MASTER_GLOBAL_CONFIG_FILE to specify arbitrary local-files for mounting
                # - all other local-files get scrubbed for specific requirements and non-matches
                # are dropped.
                if cfg_path != MASTER_GLOBAL_CONFIG_FILE:
                    scrubbed_local_files = {}
                    for fname, fpath in list(ctx.get('local-files', {}).items()):
                        if not isinstance(fpath, str):
                            self.log.write(
                                f'Bad "local-files" entry in {cfg_path!r}:\n'
                                f'    {fname!r}: {fpath!r}\n'
                            )
                            continue
                        resolved_path = os.path.realpath(os.path.expanduser(fpath))
                        # pylint: disable=too-many-boolean-expressions
                        if (
                                username == 'root'
                                or resolved_path == homedir
                                or resolved_path.startswith(homedir + os.path.sep)
                                or os.stat(resolved_path).st_uid == os.getuid()
                                or (
                                    not os.path.isdir(resolved_path)
                                    and os.access(resolved_path, os.R_OK | os.W_OK)
                                )
                        ):
                            scrubbed_local_files[fname] = resolved_path
                        else:
                            self.log.write(
                                f'Bad "local-files" entry in {cfg_path!r}:\n'
                                f'    User {username!r} is not allowed to mount {resolved_path!r}.\n'
                                f'    You may need an entry in {MASTER_GLOBAL_CONFIG_FILE!r}.\n'
                            )
                    ctx['local-files'] = scrubbed_local_files

                context.update(ctx)

        context.update({'CONFIG_FILES': cfg_files})

        return context

    def _strftime(self, _format="%Y-%m-%d", _ts=None):
        """
        Format the provided timestamp. If no timestamp is provided, build_time is used
        :param _format: Format string - default "%Y-%m-%d"
        :param _ts: Timestamp to format - default self.build_time
        :return: Formatted date/time string
        """
        if _ts is None:
            _ts = self.build_time
        _date = datetime.datetime.fromtimestamp(_ts)
        return _date.strftime(_format)

    @staticmethod
    def _re_sub_filter(text, pattern, replace, count=0, flags=0):
        '''
        Filter for regular expression replacement.
        :param text: The string being examined for ``pattern``
        :param pattern: The pattern to find in ``text``
        :param replace: The replacement for ``pattern``
        :param count: How many matches of ``pattern`` to replace with ``replace`` (0=all)
        :param flags: Regular expression flags
        '''
        return re.sub(pattern, replace, text, count=count, flags=flags)

    @staticmethod
    def _re_split_filter(text, pattern, maxsplit=0, flags=0):
        '''
        Filter for regular expression replacement.
        :param text: The string being examined for ``pattern``
        :param pattern: The pattern used to split ``text``
        :param maxsplit: How many instances of ``pattern`` to split (0=all)
        :param flags: Regular expression flags
        '''
        return re.split(pattern, text, maxsplit=maxsplit, flags=flags)

    @staticmethod
    def _reorder_dependency_steps(config):
        """
        Reorders the steps based on the dependencies that are outlined in the config
        """
        # Defines configuration keywords, should add to a config validation class
        keyword_version = 'version'
        keyword_steps = 'steps'
        keyword_depends =   'depends'
        supported_version = 2.0

        if keyword_version not in config.keys() \
                or config[keyword_version] < supported_version:
            return config

        ordered_steps = OrderedDict()
        if keyword_steps in config.keys():
            topo_sorter = TopologicalSorter()
            for name, instructions in config[keyword_steps].items():
                if keyword_depends in instructions.keys():
                    for depend in instructions[keyword_depends]:
                        topo_sorter.add(name, depend)
                else:
                    topo_sorter.add(name)
            for step in topo_sorter.static_order():
                if step not in config[keyword_steps]:
                    raise KeyError(f"Step '{step}' is not defined and is listed as a step dependency in "
                                   f"the configuration. "
                                   f"Please correct the typo or define step '{step}' in the configuration.")

                if keyword_depends in config[keyword_steps][step].keys():
                    del config[keyword_steps][step][keyword_depends]

                ordered_steps[step] = config[keyword_steps][step]

            config[keyword_steps] = ordered_steps

        return config


    @staticmethod
    def _validate_version(config: OrderedDict, version_file_path: str):
        """
        Compares that the version in the config is less than or equal to the current version of
        buildrunner. If the config version is greater than the buildrunner version or any parsing error occurs
        it will raise a buildrunner exception.
        """
        buildrunner_version = None

        if not os.path.exists(version_file_path):
            print(f"WARNING: File {version_file_path} does not exist. This could indicate an error with "
                  f"the buildrunner installation. Unable to validate version.")
            return

        with open(version_file_path, 'r') as version_file:
            for line in version_file.readlines():
                if '__version__' in line:
                    try:
                        version_values = line.split('=')[1].strip().replace("'","").split('.')
                        buildrunner_version = f"{version_values[0]}.{version_values[1]}"
                    except IndexError as exception:
                        raise ConfigVersionFormatError(f"couldn't parse version from \"{line}\"") from exception

        if not buildrunner_version:
            raise BuildRunnerVersionError("unable to determine buildrunner version")

        config_version = None

        # version is optional and is valid to not have it in the config
        if 'version' not in config.keys():
            return

        config_version = config['version']

        try:
            if float(config_version) > float(buildrunner_version):
                raise ConfigVersionFormatError(f"configuration version {config_version} is higher than "
                                         f"buildrunner version {buildrunner_version}")
        except ValueError as exception:
            raise ConfigVersionTypeError(f"unable to convert config version \"{config_version}\" "
                                         f"or buildrunner version \"{buildrunner_version}\" "
                                         f"to a float") from exception


    def _load_config(self, cfg_file, ctx=None, log_file=True):
        """
        Load a config file templating it with Jinja and parsing the YAML.

        Returns:
          multi-structure: configuration keys and values
        """

        config = None
        fetch_file = cfg_file
        visited = set()

        while True:
            visited.add(fetch_file)
            contents = fetch.fetch_file(fetch_file, self.global_config)
            jenv = jinja2.Environment(loader=jinja2.FileSystemLoader('.'), extensions=['jinja2.ext.do'])
            jenv.filters['hash_sha1'] = hash_sha1
            jenv.filters['base64encode'] = base64.encode
            jenv.filters['base64decode'] = base64.decode
            jenv.filters['re_sub'] = self._re_sub_filter
            jenv.filters['re_split'] = self._re_split_filter

            jenv.globals.update(checksum=checksum)
            jtemplate = jenv.from_string(contents)

            config_context = copy.deepcopy(self.env)
            config_context.update({
                'CONFIG_FILE': cfg_file,
                'CONFIG_DIR': os.path.dirname(cfg_file),
                # This is stored after the initial env is set
                'DOCKER_REGISTRY': self.get_docker_registry(),
                'read_yaml_file': self._read_yaml_file,
                'raise': self._raise_exception_jinja,
                'strftime': self._strftime,
            })

            if ctx:
                config_context.update(ctx)

            config_contents = jtemplate.render(config_context)
            if log_file:
                self._log_generated_file(cfg_file, config_contents)
            config = load_config(StringIO(config_contents), cfg_file)

            if not config:
                break

            redirect = config.get('redirect')
            if redirect is None:
                break

            fetch_file = redirect
            if fetch_file in visited:
                raise BuildRunnerConfigurationError(
                    f"Redirect loop visiting previously visited file: {fetch_file}"
                )

        self._validate_version(config=config,
                               version_file_path=f"{os.path.dirname(os.path.realpath(__file__))}/version.py")

        config = self._reorder_dependency_steps(config)

        return config

    def __init__(
            self,
            build_dir,
            build_results_dir=None,
            global_config_file=None,
            run_config_file=None,
            run_config=None,
            build_number=None,
            push=False,
            colorize_log=True,
            cleanup_images=False,
            cleanup_step_artifacts=False,
            steps_to_run=None,
            publish_ports=False,
            disable_timestamps=False,
            log_generated_files=False,
            docker_timeout=None,
            local_images=False,
            platform=None,
    ):  # pylint: disable=too-many-statements,too-many-branches,too-many-locals,too-many-arguments
        """
        """
        self.build_dir = build_dir
        if build_results_dir:
            self.build_results_dir = build_results_dir
        else:
            self.build_results_dir = os.path.join(self.build_dir, RESULTS_DIR)
        self.push = push
        self.cleanup_images = cleanup_images
        self.cleanup_step_artifacts = cleanup_step_artifacts
        self.generated_images = []
        # The set of images (including tag) that were committed as part of this build
        # This is used to check if images should be pulled by default or not
        self.committed_images = set()
        self.repo_tags_to_push = []
        self.colorize_log = colorize_log
        self.steps_to_run = steps_to_run
        self.publish_ports = publish_ports
        self.disable_timestamps = disable_timestamps
        self.log_generated_files = log_generated_files
        self.docker_timeout = docker_timeout
        self.local_images = local_images
        self.platform = platform

        self.tmp_files = []
        self.artifacts = OrderedDict()
        self.pypi_packages = OrderedDict()

        self.exit_code = None
        self._source_image = None
        self._source_archive = None
        self._log_file = None
        self._log = None

        # set build time
        self.build_time = epoch_time()

        # set build number
        self.build_number = build_number
        if not self.build_number:
            self.build_number = self.build_time

        try:
            self.vcs = detect_vcs(self.build_dir)
            self.build_id = f"{self.vcs.id_string}-{self.build_number}"
        except VCSUnsupported as err:
            self.log.write(f'{err}\nPlease verify you have a VCS set up for this project.\n')
            sys.exit()
        except VCSMissingRevision as err:
            self.log.write(f'{err}\nMake sure you have at least one commit.\n')
            sys.exit()

        # cleanup existing results dir (if needed)
        if self.cleanup_step_artifacts and os.path.exists(self.build_results_dir):
            shutil.rmtree(self.build_results_dir)
            self.log.write(f'Cleaned existing results directory "{RESULTS_DIR}"')

        # default environment - must come *after* VCS detection
        base_context = {}
        if push:
            base_context['BUILDRUNNER_DO_PUSH'] = 1
        self.env = self._get_config_context(base_context)
        # pylint: disable=consider-iterating-dictionary
        key_len = max([len(key) for key in self.env.keys()])
        for key in sorted(self.env.keys()):
            val = self.env[key]
            LOGGER.debug(f'Environment: {key!s:>{key_len}}: {val}')

        # load global configuration
        _gc_files = DEFAULT_GLOBAL_CONFIG_FILES[:]
        _gc_files.append(global_config_file or f'{self.build_dir}/.buildrunner.yaml')

        _global_config_files = self.to_abs_path(
            _gc_files, return_list=True
        )

        self.log.write(f"\nGlobal configuration is from: {', '.join(_global_config_files)}\n")
        self.global_config = {}
        self.global_config = self._load_config_files(_global_config_files, log_file=False)

        # load run configuration
        _run_config_file = None
        if run_config:
            self.run_config = run_config
        else:
            if run_config_file:
                _run_config_file = self.to_abs_path(run_config_file)
            else:
                self.log.write("looking for run configuration\n")
                for name_to_try in DEFAULT_RUN_CONFIG_FILES:
                    _to_try = self.to_abs_path(name_to_try)
                    if os.path.exists(_to_try):
                        _run_config_file = _to_try
                        break

            if not _run_config_file or not os.path.exists(_run_config_file):
                raise BuildRunnerConfigurationError(
                    'Cannot find build configuration file'
                )

            self.run_config = self._load_config(_run_config_file)

        if not isinstance(self.run_config, dict) or 'steps' not in self.run_config:
            cfg_file = _run_config_file if _run_config_file else 'provided config'
            raise BuildRunnerConfigurationError(f'Could not find a "steps" attribute in {cfg_file}')
        if not self.run_config['steps'] or not isinstance(self.run_config['steps'], dict):
            cfg_file = _run_config_file if _run_config_file else 'provided config'
            raise BuildRunnerConfigurationError(
                f'The "steps" attribute is not a non-empty dictionary in {cfg_file}'
            )

    def get_docker_registry(self):
        """
        Default to docker.io if none is configured
        """
        return self.global_config.get('docker-registry', 'docker.io')

    def get_temp_dir(self):
        """
        Get temp dir in the following priorities:
        * Environment variable
        * Global configuration property
        * Configured system temp directory
        """
        return os.getenv('BUILDRUNNER_TEMPDIR', self.global_config.get('temp-dir', tempfile.gettempdir()))

    def get_build_server_from_alias(self, host):
        """
        Given a host alias string determine the actual build server host value
        to use by checking the global configuration.
        """
        # if no build servers configuration in global config just return host
        if 'build-servers' not in self.global_config:
            return host

        build_servers = self.global_config['build-servers']
        for _host, _host_aliases in build_servers.items():
            if host in _host_aliases:
                return _host

        return host

    def get_ssh_keys_from_aliases(self, key_aliases):  # pylint: disable=too-many-branches
        """
        Given a list of key aliases return Paramiko key objects based on keys
        registered in the global config.
        """
        ssh_keys = []
        if not key_aliases:
            return ssh_keys
        if 'ssh-keys' not in self.global_config:
            raise BuildRunnerConfigurationError(
                "SSH key aliases specified but no 'ssh-keys' "
                "configuration in global build runner config"
            )

        ssh_keys = self.global_config['ssh-keys']
        _keys = []
        _matched_aliases = []
        for key_info in ssh_keys:
            if 'aliases' not in key_info or not key_info['aliases']:
                continue

            _password = None
            _prompt_for_password = False
            if 'password' in key_info:
                _password = key_info['password']
            else:
                _prompt_for_password = key_info.get('prompt-password', False)

            for alias in key_aliases:
                if alias in key_info['aliases']:
                    _matched_aliases.append(alias)

                    # Prompt for password if necessary.  Only once per key
                    if _prompt_for_password:
                        _password = getpass.getpass(f"Password for SSH Key ({alias}): ")
                        _prompt_for_password = False

                    if 'file' in key_info:
                        _key_file = os.path.realpath(
                            os.path.expanduser(
                                os.path.expandvars(key_info['file'])
                            )
                        )

                        _keys.append(
                            load_ssh_key_from_file(_key_file, _password)
                        )
                    elif 'key' in key_info:
                        _keys.append(
                            load_ssh_key_from_str(key_info['key'], _password)
                        )

        for alias in key_aliases:
            if alias not in _matched_aliases:
                raise BuildRunnerConfigurationError(
                    f"Could not find valid SSH key matching alias '{alias}'"
                )

        return _keys

    def get_local_files_from_alias(self, file_alias):
        """
        Given a file alias lookup the local file path from the global config.
        """
        if not file_alias:
            return None
        if 'local-files' not in self.global_config:
            self.log.write("No 'local-files' configuration in global build runner config")
            return None

        local_files = self.global_config['local-files']
        for local_alias, local_file in local_files.items():
            if file_alias == local_alias:
                local_path = os.path.realpath(
                    os.path.expanduser(os.path.expandvars(local_file))
                )
                if os.path.exists(local_path):
                    return local_path

                # need to put the contents in a tmp file and return the path
                _fileobj = tempfile.NamedTemporaryFile(
                    delete=False,
                    dir=self.get_temp_dir(),
                )
                _fileobj.write(local_file)
                tmp_path = os.path.realpath(_fileobj.name)
                _fileobj.close()
                self.tmp_files.append(tmp_path)
                return tmp_path

        return None

    @staticmethod
    def get_cache_archive_ext():
        """
        Returns the archive file extension used for cache archive files
        """
        return "tar"

    def get_cache_archive_file(self, cache_name, project_name=""):
        """
        Given a cache name determine the local file path.
        """
        caches_root = self.global_config.get('caches-root', DEFAULT_CACHES_ROOT)
        build_path = os.path.splitdrive(self.build_dir)[1]
        if os.path.isabs(build_path):
            build_path = build_path[1:]

        cache_name = f"{cache_name}.{self.get_cache_archive_ext()}"
        if project_name != "":
            cache_name = f"{project_name}-{cache_name}"

        local_cache_archive_file = os.path.expanduser(
            os.path.join(caches_root, cache_name)
        )
        cache_dir = os.path.dirname(local_cache_archive_file)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        return local_cache_archive_file

    def to_abs_path(self, path, return_list=False):
        """
        Convert a path to an absolute path (if it isn't one already).
        """

        paths = path
        if not isinstance(path, list):
            paths = [path]

        for index, _ in enumerate(paths):
            _path = os.path.expanduser(paths[index])
            if os.path.isabs(_path):
                paths[index] = os.path.realpath(_path)
            else:
                paths[index] = os.path.realpath(os.path.join(self.build_dir, _path))
        if return_list:
            return paths
        return paths[0]

    def add_artifact(self, artifact_file, properties):
        """
        Register a build artifact to be included in the artifacts manifest.
        """
        self.artifacts[artifact_file] = properties

    def get_source_archive_path(self):
        """
        Create the source archive for use in remote builds or to build the
        source image.
        """
        if not self._source_archive:
            buildignore = os.path.join(self.build_dir, '.buildignore')
            excludes = []
            if os.path.exists(buildignore):
                with open(buildignore, 'r') as _file:
                    excludes = _file.read().splitlines()

            def _exclude_working_dir(tarinfo):
                """
                Filter to exclude results dir from source archive.
                """
                if tarinfo.name == os.path.basename(self.build_results_dir):
                    return None
                for _ex in excludes:
                    if fnmatch.fnmatch(tarinfo.name, _ex):
                        return None
                return tarinfo

            self.log.write('Creating source archive\n')
            _fileobj = None
            try:
                _fileobj = tempfile.NamedTemporaryFile(
                    delete=False,
                    dir=self.get_temp_dir(),
                )
                with tarfile.open(mode='w', fileobj=_fileobj) as tfile:
                    tfile.add(
                        self.build_dir,
                        arcname='',
                        filter=_exclude_working_dir
                    )
                self._source_archive = _fileobj.name
            finally:
                if _fileobj:
                    _fileobj.close()
        return self._source_archive

    def get_source_image(self):
        """
        Get and/or create the base image source containers will be created
        from.
        """
        if not self._source_image:
            self.log.write('Creating source image\n')
            source_archive_path = self.get_source_archive_path()
            inject = {
                source_archive_path: 'source.tar',
                SOURCE_DOCKERFILE: "Dockerfile",
            }
            source_builder = DockerBuilder(
                temp_dir=self.get_temp_dir(),
                inject=inject,
                timeout=self.docker_timeout,
                docker_registry=self.get_docker_registry(),
            )
            exit_code = source_builder.build(
                nocache=True,
                pull=False,
            )
            if exit_code != 0 or not source_builder.image:
                raise BuildRunnerProcessingError(
                    f'Error building source image ({exit_code}), this may be a transient docker'
                    ' error if no output is available above'
                )
            self._source_image = source_builder.image
        return self._source_image

    @property
    def log(self):
        """
        create the log file and open for writing
        """
        if self._log is None:
            try:
                os.makedirs(self.build_results_dir)
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    sys.stderr.write(f'ERROR: {str(exc)}\n')
                    sys.exit(os.EX_UNAVAILABLE)

            try:
                log_file_path = os.path.join(self.build_results_dir, 'build.log')
                self._log_file = open(log_file_path, 'w')
                self._log = ConsoleLogger(self.colorize_log, self._log_file)

                self.add_artifact(
                    os.path.basename(log_file_path),
                    {'type': 'log'},
                )
            except Exception as exc:  # pylint: disable=broad-except
                sys.stderr.write(f'ERROR: failed to initialize ConsoleLogger: {str(exc)}\n')
                self._log = sys.stderr

        return self._log

    def _write_artifact_manifest(self):
        """
        If we have registered artifacts write the files and associated metadata
        to the artifacts manifest.
        """
        if self.artifacts:
            self.log.write('\nWriting artifact properties\n')
            artifact_manifest = os.path.join(
                self.build_results_dir,
                'artifacts.json',
            )
            # preserve contents of artifacts.json between steps run separately
            if os.path.exists(artifact_manifest):
                with open(artifact_manifest, 'r') as _af:
                    data = json.load(_af, object_pairs_hook=OrderedDict)
                    artifacts = OrderedDict(list(data.items()) + list(self.artifacts.items()))
            else:
                artifacts = self.artifacts

            with open(artifact_manifest, 'w') as _af:
                json.dump(artifacts, _af, indent=2)

    def _exit_message_and_close_log(self, exit_explanation):
        """
        Determine the exit message, output to the log or stdout, close log if
        open.
        """
        if self.exit_code:
            exit_message = '\nBuild ERROR.'
        else:
            exit_message = '\nBuild SUCCESS.'

        if self._log_file:
            try:
                if exit_explanation:
                    self.log.write('\n' + exit_explanation + '\n')
                self.log.write(exit_message + '\n')
            finally:
                # close the log_file
                self._log_file.close()
        else:
            if exit_explanation:
                print(f'\n{exit_explanation}')
            print(exit_message)

    def run(self):  # pylint: disable=too-many-statements,too-many-branches,too-many-locals
        """
        Run the build.
        """
        # reset the exit_code
        self.exit_code = None

        exit_explanation = None
        try:  # pylint: disable=too-many-nested-blocks

            if not os.path.exists(self.build_results_dir):
                # create a new results dir
                os.mkdir(self.build_results_dir)

            self.get_source_archive_path()

            # run each step
            for step_name, step_config in self.run_config['steps'].items():
                if not self.steps_to_run or step_name in self.steps_to_run:
                    image_config = BuildStepRunner.ImageConfig(
                        self.local_images,
                        self.platform
                    )
                    build_step_runner = BuildStepRunner(
                        self,
                        step_name,
                        step_config,
                        image_config
                    )
                    build_step_runner.run()

            self.log.write(
                "\nFinalizing build\n________________________________________\n"
            )

            # see if we should push registered tags to remote registries/repositories
            if self.push:
                self.log.write(
                    'Push requested--pushing generated images/packages to remote registries/repositories\n'
                )
                _docker_client = docker.new_client(timeout=self.docker_timeout)
                for _repo_tag, _insecure_registry in self.repo_tags_to_push:
                    self.log.write(
                        f'\nPushing {_repo_tag}\n'
                    )

                    # Newer Python Docker bindings drop support for the insecure_registry
                    # option.  This test will optionally use it when it's available.
                    push_kwargs = {
                        'stream': True,
                    }
                    if 'insecure_registry' in inspect.getfullargspec(_docker_client.push).args:
                        push_kwargs['insecure_registry'] = _insecure_registry

                    stream = _docker_client.push(_repo_tag, **push_kwargs)
                    previous_status = None
                    for msg_str in stream:
                        for msg in msg_str.decode('utf-8').split("\n"):
                            if not msg:
                                continue
                            msg = json.loads(msg)
                            if 'status' in msg:
                                if msg['status'] == previous_status:
                                    continue
                                self.log.write(msg['status'] + '\n')
                                previous_status = msg['status']
                            elif 'errorDetail' in msg:
                                error_detail = f"Error pushing image: {msg['errorDetail']}\n"
                                self.log.write("\n" + error_detail)
                                self.log.write((
                                    "This could be because you are not "
                                    "authenticated with the given Docker "
                                    "registry (try 'docker login "
                                    "<registry>')\n\n"
                                ))
                                raise BuildRunnerProcessingError(error_detail)
                            else:
                                self.log.write(str(msg) + '\n')

                # Push to pypi repositories
                # Placing the import here avoids the dependency when pypi is not needed
                import twine.commands.upload  # pylint: disable=import-outside-toplevel
                for _, _items in self.pypi_packages.items():
                    twine.commands.upload.upload(_items['upload_settings'], _items['packages'])
            else:
                self.log.write(
                    '\nPush not requested\n'
                )

        except BuildRunnerConfigurationError as brce:
            print('config error')
            exit_explanation = str(brce)
            self.exit_code = os.EX_CONFIG
        except BuildRunnerProcessingError as brpe:
            print('processing error')
            exit_explanation = str(brpe)
            self.exit_code = 1
        except requests.exceptions.ConnectionError as rce:
            print('connection error')
            print(str(rce))
            exit_explanation = (
                "Error communicating with the remote host.\n\tCheck that the "
                "remote docker Daemon is running and/or that the DOCKER_* "
                "environment variables are set correctly.\n\tCheck that the "
                "remote PyPi server information is set correctly."
            )
            self.exit_code = 1

        finally:
            self._write_artifact_manifest()

            _docker_client = docker.new_client(timeout=self.docker_timeout)
            if self.cleanup_images:
                self.log.write(
                    'Removing local copy of generated images\n'
                )
                # cleanup all registered docker images
                # reverse the order of the images since child images would likely come after parent images
                for _image in self.generated_images[::-1]:
                    try:
                        _docker_client.remove_image(
                            _image,
                            noprune=False,
                            force=True,
                        )
                    except Exception as _ex:  # pylint: disable=broad-except
                        self.log.write(
                            f'Error removing image {_image}: {str(_ex)}'
                        )
            else:
                self.log.write(
                    'Keeping generated images\n'
                )

            # cleanup the source image
            if self._source_image:
                self.log.write(
                    f"Destroying source image {self._source_image}\n"
                )
                _docker_client.remove_image(
                    self._source_image,
                    noprune=False,
                    force=True,
                )
            if self._source_archive:
                self.log.write(
                    "Destroying source archive\n"
                )
                os.remove(self._source_archive)

            # remove any temporary files that we created
            for tmp_file in self.tmp_files:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)

            self._exit_message_and_close_log(exit_explanation)

# Local Variables:
# fill-column: 100
# End:
