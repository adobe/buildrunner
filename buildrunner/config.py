"""
Copyright 2022 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import base64
import codecs
from collections import OrderedDict
import copy
import datetime
import getpass
from graphlib import TopologicalSorter
from io import StringIO
import os
import re
import sys
import tempfile

import jinja2

from pydantic import ValidationError

from buildrunner.errors import (
    BuildRunnerConfigurationError,
    BuildRunnerVersionError,
    ConfigVersionFormatError,
    ConfigVersionTypeError,
)
from buildrunner.utils import (
    checksum,
    epoch_time,
    hash_sha1,
    load_config,
)

from buildrunner import config_model

from . import fetch

MASTER_GLOBAL_CONFIG_FILE = '/etc/buildrunner/buildrunner.yaml'
DEFAULT_GLOBAL_CONFIG_FILES = [
    MASTER_GLOBAL_CONFIG_FILE,
    '~/.buildrunner.yaml',
]
RESULTS_DIR = 'buildrunner.results'


class BuildRunnerConfig:  # pylint: disable=too-many-instance-attributes
    """
    Class used to manage buildrunner config.
    """

    @staticmethod
    def _raise_exception_jinja(message):
        """
        Raises an exception from a jinja template.
        """
        # pylint: disable=broad-exception-raised
        raise Exception(message)

    @staticmethod
    def _re_sub_filter(text, pattern, replace, count=0, flags=0):
        """
        Filter for regular expression replacement.
        :param text: The string being examined for ``pattern``
        :param pattern: The pattern to find in ``text``
        :param replace: The replacement for ``pattern``
        :param count: How many matches of ``pattern`` to replace with ``replace`` (0=all)
        :param flags: Regular expression flags
        """
        return re.sub(pattern, replace, text, count=count, flags=flags)

    @staticmethod
    def _re_split_filter(text, pattern, maxsplit=0, flags=0):
        """
        Filter for regular expression replacement.
        :param text: The string being examined for ``pattern``
        :param pattern: The pattern used to split ``text``
        :param maxsplit: How many instances of ``pattern`` to split (0=all)
        :param flags: Regular expression flags
        """
        return re.split(pattern, text, maxsplit=maxsplit, flags=flags)

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

        with open(version_file_path, 'r', encoding='utf-8') as version_file:
            for line in version_file.readlines():
                if '__version__' in line:
                    try:
                        version_values = line.split('=')[1].strip().replace("'", "").split('.')
                        buildrunner_version = f"{version_values[0]}.{version_values[1]}"
                    except IndexError as exception:
                        raise ConfigVersionFormatError(f"couldn't parse version from \"{line}\"") from exception

        if not buildrunner_version:
            raise BuildRunnerVersionError("unable to determine buildrunner version")

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

    @staticmethod
    def _reorder_dependency_steps(config):
        """
        Reorders the steps based on the dependencies that are outlined in the config
        """
        # Defines configuration keywords, should add to a config validation class
        keyword_version = 'version'
        keyword_steps = 'steps'
        keyword_depends = 'depends'
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

    def __init__(
            self,
            build_dir=None,
            build_results_dir=None,
            global_config_file=None,
            log_generated_files=False,
            build_time=None,
            env=None,
            log=None,
    ):  # pylint: disable=too-many-arguments
        self.build_dir = build_dir
        if build_results_dir:
            self.build_results_dir = build_results_dir
        else:
            self.build_results_dir = os.path.join(self.build_dir, RESULTS_DIR)
        self.log_generated_files = log_generated_files
        self.build_time = build_time
        if not self.build_time:
            self.build_time = epoch_time()
        self.env = env
        if not self.env:
            self.env = {}

        self.tmp_files = []

        self.log = log
        if self.log is None:
            # initialize log to stdout
            self.log = sys.stdout

        # load global configuration
        _gc_files = DEFAULT_GLOBAL_CONFIG_FILES[:]
        _gc_files.append(global_config_file or f'{self.build_dir}/.buildrunner.yaml')

        _global_config_files = self.to_abs_path(
            _gc_files, return_list=True
        )

        self.log.write(f"\nGlobal configuration is from: {', '.join(_global_config_files)}\n")
        self.global_config = {}
        self.global_config = self._load_config_files(_global_config_files, log_file=False)

    def get(self, name, default=None):
        """
        Get method
        """
        return self.global_config.get(name, default)

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

    def _log_generated_file(self, file_name, file_contents):
        """
        Conditionally log the contents of a generated file.
        """
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
                ctx = self.load_config(cfg_path, context, log_file=log_file)
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

    def load_config(self, cfg_file, ctx=None, log_file=True):
        """
        Load a config file templating it with Jinja and parsing the YAML.

        Returns:
          multi-structure: configuration keys and values
        """

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

        # Validate the config
        try:
            config_model.Config(**config)
        except (ValidationError, ValueError) as err:
            raise BuildRunnerConfigurationError(f"Invalid configuration: {err}")    # pylint: disable=raise-missing-from

        return config

    def get_temp_dir(self):
        """
        Get temp dir in the following priorities:
        * Environment variable
        * Global configuration property
        * Configured system temp directory
        """
        return os.getenv('BUILDRUNNER_TEMPDIR', self.global_config.get('temp-dir', tempfile.gettempdir()))

    def get_docker_registry(self):
        """
        Default to docker.io if none is configured
        """
        return self.global_config.get('docker-registry', 'docker.io')

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
