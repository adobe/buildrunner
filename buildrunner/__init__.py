"""
Copyright (C) 2014 Adobe
"""
from __future__ import absolute_import
import codecs
from collections import OrderedDict
import copy
import errno
import fnmatch
import imp
import json
import os
import shutil
from StringIO import StringIO
import sys
import tarfile
import tempfile
import threading
import uuid
import getpass

import jinja2
import requests


from buildrunner import docker
from buildrunner.docker.builder import DockerBuilder
from buildrunner.errors import (
    BuildRunnerConfigurationError,
    BuildRunnerProcessingError,
)
from buildrunner.sshagent import load_ssh_key_from_file, load_ssh_key_from_str
from buildrunner.steprunner import BuildStepRunner
from buildrunner.utils import (
    ConsoleLogger,
    epoch_time,
    load_config,
    hash_sha1
)
from vcsinfo import detect_vcs


__version__ = 'DEVELOPMENT'
try:
    _VERSION_FILE = os.path.join(os.path.dirname(__file__), 'version.py')
    if os.path.exists(_VERSION_FILE):
        _VERSION_MOD = imp.load_source('buildrunnerversion', _VERSION_FILE)
        __version__ = _VERSION_MOD.__version__
except:  # pylint: disable=bare-except
    pass


DEFAULT_GLOBAL_CONFIG_FILE = '~/.buildrunner.yaml'
DEFAULT_CACHES_ROOT = '~/.buildrunner/caches'
DEFAULT_RUN_CONFIG_FILES = ['buildrunner.yaml', 'gauntlet.yaml']
RESULTS_DIR = 'buildrunner.results'


SOURCE_DOCKERFILE = os.path.join(os.path.dirname(__file__), 'SourceDockerfile')


class BuildRunner(object):
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
            'BUILDRUNNER_BUILD_TIME': str(self.build_time),
            'VCSINFO_NAME': str(self.vcs.name),
            'VCSINFO_BRANCH': str(self.vcs.branch),
            'VCSINFO_NUMBER': str(self.vcs.number),
            'VCSINFO_ID': str(self.vcs.id),
            'VCSINFO_SHORT_ID': str(self.vcs.id)[:7],
            'VCSINFO_MODIFIED': str(self.vcs.modified),
        }

        if ctx:
            context.update(ctx)

        for env_name, env_value in os.environ.iteritems():
            for prefix in self.CONTEXT_ENV_PREFIXES:
                if env_name.startswith(prefix):
                    context[env_name] = env_value

        return context

    def _raise_exception_jinja(self, message):
        """
        Raises an exception from a jinja template.
        """
        raise Exception(message)

    def _log_generated_file(self, file_name, file_contents):
        if self.log_generated_files:
            self.log.write('Generated contents of {}:\n'.format(file_name))
            for line in file_contents.splitlines():
                self.log.write('{}\n'.format(line))

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

    def _load_config(self, cfg_file, ctx=None, log_file=True):
        """
        Load a config file templating it with Jinja and parsing the YAML.

        Returns:
          multi-structure: configuration keys and values
        """

        with codecs.open(cfg_file, 'r', encoding='utf-8') as _file:
            jenv = jinja2.Environment(loader=jinja2.FileSystemLoader('.'), extensions=['jinja2.ext.do'])
            jenv.filters['hash_sha1'] = hash_sha1
            jtemplate = jenv.from_string(_file.read())

        config_context = copy.deepcopy(self.env)
        config_context.update({
            'CONFIG_FILE': cfg_file,
            'CONFIG_DIR': os.path.dirname(cfg_file),
            'read_yaml_file': self._read_yaml_file,
            'raise': self._raise_exception_jinja,
        })

        if ctx:
            config_context.update(ctx)

        config_contents = jtemplate.render(config_context)
        if log_file:
            self._log_generated_file(cfg_file, config_contents)
        config = load_config(StringIO(config_contents), cfg_file)

        return config

    def __init__(
            self,
            build_dir,
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
    ):
        """
        """
        self.build_dir = build_dir
        self.build_results_dir = os.path.join(self.build_dir, RESULTS_DIR)
        self.push = push
        self.cleanup_images = cleanup_images
        self.cleanup_step_artifacts = cleanup_step_artifacts
        self.generated_images = []
        self.repo_tags_to_push = []
        self.colorize_log = colorize_log
        self.steps_to_run = steps_to_run
        self.publish_ports = publish_ports
        self.disable_timestamps = disable_timestamps
        self.log_generated_files = log_generated_files

        self.tmp_files = []
        self.artifacts = OrderedDict()

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

        self.vcs = detect_vcs(self.build_dir)
        self.build_id = "%s-%s" % (self.vcs.id_string, self.build_number)

        # cleanup existing results dir (if needed)
        if self.cleanup_step_artifacts and os.path.exists(self.build_results_dir):
            shutil.rmtree(self.build_results_dir)
            self.log.write('Cleaned existing results directory "{}"'.format(RESULTS_DIR))

        # default environment - must come *after* VCS detection
        base_context = {}
        if push:
            base_context['BUILDRUNNER_DO_PUSH'] = 1
        self.env = self._get_config_context(base_context)

        # load global configuration
        _global_config_file = self.to_abs_path(
            global_config_file or DEFAULT_GLOBAL_CONFIG_FILE
        )
        self.log.write("Attempting to load global configuration from {}\n".format(_global_config_file))
        self.global_config = {}
        if _global_config_file and os.path.exists(_global_config_file):
            self.global_config = self._load_config(_global_config_file, log_file=False)

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
            raise BuildRunnerConfigurationError(
                'Could not find a "steps" attribute in {}'.format(
                    _run_config_file if _run_config_file else 'provided config'
                )
            )
        if not self.run_config['steps'] or not isinstance(self.run_config['steps'], dict):
            raise BuildRunnerConfigurationError(
                'The "steps" attribute is not a non-empty dictionary in {}'.format(
                    _run_config_file if _run_config_file else 'provided config'
                )
            )

    def get_build_server_from_alias(self, host):
        """
        Given a host alias string determine the actual build server host value
        to use by checking the global configuration.
        """
        # if no build servers configuration in global config just return host
        if 'build-servers' not in self.global_config:
            return host

        build_servers = self.global_config['build-servers']
        for _host, _host_aliases in build_servers.iteritems():
            if host in _host_aliases:
                return _host

        return host

    def get_ssh_keys_from_aliases(self, key_aliases):
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
                        _password = getpass.getpass("Password for SSH Key ({0}): ".format(alias))
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
                    "Could not find valid SSH key matching alias '%s'" % alias
                )

        return _keys

    def get_local_files_from_alias(self, file_alias):
        """
        Given a file alias lookup the local file path from the global config.
        """
        if not file_alias:
            return None
        if 'local-files' not in self.global_config:
            raise BuildRunnerConfigurationError(
                "File aliases specified but no 'local-files' "
                "configuration in global build runner config"
            )

        local_files = self.global_config['local-files']
        for local_alias, local_file in local_files.iteritems():
            if file_alias == local_alias:
                local_path = os.path.realpath(
                    os.path.expanduser(os.path.expandvars(local_file))
                )
                if os.path.exists(local_path):
                    return local_path

                # need to put the contents in a tmp file and return the path
                _fileobj = tempfile.NamedTemporaryFile(delete=False)
                _fileobj.write(local_file)
                tmp_path = os.path.realpath(_fileobj.name)
                _fileobj.close()
                self.tmp_files.append(tmp_path)
                return tmp_path

        return None

    def get_cache_path(self, cache_name):
        """
        Given a cache name determine the local file path.
        """
        caches_root = self.global_config.get('caches-root', DEFAULT_CACHES_ROOT)
        build_path = os.path.splitdrive(self.build_dir)[1]
        if os.path.isabs(build_path):
            build_path = build_path[1:]
        cache_dir = os.path.expanduser(
            os.path.join(caches_root, build_path, 'CACHES', cache_name)
        )
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        return cache_dir

    def to_abs_path(self, path):
        """
        Convert a path to an absolute path (if it isn't one already).
        """
        _path = os.path.expanduser(path)
        if os.path.isabs(_path):
            return _path
        return os.path.join(
            self.build_dir,
            _path,
        )

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
                    excludes = [_ex for _ex in _file.read().splitlines()]

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
                _fileobj = tempfile.NamedTemporaryFile(delete=False)
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
            source_builder = DockerBuilder(inject=inject)
            exit_code = source_builder.build(
                nocache=True,
            )
            if exit_code != 0 or not source_builder.image:
                raise BuildRunnerProcessingError((
                    'Error building source image ({0}), this may be a transient docker'
                    ' error if no output is available above'
                ).format(exit_code))
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
                    sys.stderr.write('ERROR: {0}\n'.format(str(exc)))
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
                sys.stderr.write('ERROR: failed to initialize ConsoleLogger: {0}\n'.format(str(exc)))
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
                    artifacts = OrderedDict(data.items() + self.artifacts.items())
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
                print('\n{}'.format(exit_explanation))
            print(exit_message)

    def run(self):
        """
        Run the build.
        """
        # reset the exit_code
        self.exit_code = None

        exit_explanation = None
        try:

            if not os.path.exists(self.build_results_dir):
                # create a new results dir
                os.mkdir(self.build_results_dir)

            self.get_source_archive_path()

            # run each step
            for step_name, step_config in self.run_config['steps'].iteritems():
                if not self.steps_to_run or step_name in self.steps_to_run:
                    build_step_runner = BuildStepRunner(
                        self,
                        step_name,
                        step_config,
                    )
                    build_step_runner.run()

            self.log.write(
                "\nFinalizing build\n________________________________________\n"
            )

            # see if we should push registered tags to remote registries
            if self.push:
                self.log.write(
                    'Push requested--pushing generated images to remote '
                    'registries\n'
                )
                _docker_client = docker.new_client()
                for _repo_tag, _insecure_registry in self.repo_tags_to_push:
                    self.log.write(
                        '\nPushing %s\n' % _repo_tag
                    )
                    stream = _docker_client.push(
                        _repo_tag,
                        stream=True,
                        insecure_registry=_insecure_registry,
                    )
                    previous_status = None
                    for msg_str in stream:
                        for msg in msg_str.split("\n"):
                            if not msg:
                                continue
                            msg = json.loads(msg)
                            if 'status' in msg:
                                if msg['status'] == previous_status:
                                    continue
                                self.log.write(msg['status'] + '\n')
                                previous_status = msg['status']
                            elif 'errorDetail' in msg:
                                error_detail = "Error pushing image: %s\n" % (
                                    msg['errorDetail']
                                )
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
            else:
                self.log.write(
                    '\nPush not requested\n'
                )

        except BuildRunnerConfigurationError as brce:
            print 'config error'
            exit_explanation = str(brce)
            self.exit_code = os.EX_CONFIG
        except BuildRunnerProcessingError as brpe:
            print 'processing error'
            exit_explanation = str(brpe)
            self.exit_code = 1
        except requests.exceptions.ConnectionError:
            print 'connection error'
            exit_explanation = (
                "Error communicating with the remote Docker daemon.\nCheck "
                "that it is running and/or that the DOCKER_* environment "
                "variables are set correctly."
            )
            self.exit_code = 1

        finally:
            self._write_artifact_manifest()

            _docker_client = docker.new_client()
            if self.cleanup_images:
                self.log.write(
                    'Removing local copy of generated images\n'
                )
                # cleanup all registered docker images
                for _image in self.generated_images:
                    try:
                        _docker_client.remove_image(
                            _image,
                            noprune=False,
                            force=True,
                        )
                    except Exception as _ex:  # pylint: disable=broad-except
                        self.log.write(
                            'Error removing image %s: %s' % (
                                _image,
                                str(_ex),
                            )
                        )
            else:
                self.log.write(
                    'Keeping generated images\n'
                )

            # cleanup the source image
            if self._source_image:
                self.log.write(
                    "Destroying source image %s\n" % self._source_image
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
