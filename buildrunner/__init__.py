"""
Copyright (C) 2014 Adobe
"""
from __future__ import absolute_import
import codecs
from collections import OrderedDict
import copy
import json
import os
import shutil
from StringIO import StringIO
import sys
import tarfile
import tempfile
import threading
import uuid

import jinja2
import requests


from buildrunner import docker
from buildrunner.docker.builder import DockerBuilder
from buildrunner.errors import (
    BuildRunnerConfigurationError,
    BuildRunnerProcessingError,
)
from buildrunner.steprunner import BuildStepRunner
from buildrunner.utils import (
    ConsoleLogger,
    epoch_time,
    load_config,
)
from vcsinfo import detect_vcs


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


    def _load_config(self, cfg_file, ctx=None):
        """
        Load a config file templating it with Jinja and parsing the YAML.

        Returns:
          multi-structure: configuration keys and values
        """

        with codecs.open(cfg_file, 'r', encoding='utf-8') as _file:
            jtemplate = jinja2.Template(_file.read())

        config_context = copy.deepcopy(self.env)
        config_context.update({
            'CONFIG_FILE': cfg_file,
            'CONFIG_DIR': os.path.dirname(cfg_file),
        })

        if ctx:
            config_context.update(ctx)

        config_contents = jtemplate.render(config_context)
        config = load_config(StringIO(config_contents))

        return config


    def __init__(
            self,
            build_dir,
            global_config_file=None,
            run_config_file=None,
            build_number=None,
            push=False,
            colorize_log=True,
    ):
        """
        """
        self.build_dir = build_dir
        self.build_results_dir = os.path.join(self.build_dir, RESULTS_DIR)
        self.working_dir = os.path.join(self.build_results_dir, '.working')
        self.push = push
        self.colorize_log = colorize_log

        # set build time
        self.build_time = epoch_time()

        # set build number
        self.build_number = build_number
        if not self.build_number:
            self.build_number = self.build_time

        self.log = None

        self.vcs = detect_vcs(self.build_dir)
        self.build_id = "%s-%s" % (self.vcs.id_string, self.build_number)

        # default environment - must come *after* VCS detection
        base_context = {}
        if push:
            base_context['BUILDRUNNER_DO_PUSH'] = 1
        self.env = self._get_config_context(base_context)

        # load global configuration
        _global_config_file = self.to_abs_path(
            global_config_file or DEFAULT_GLOBAL_CONFIG_FILE
        )
        self.global_config = {}
        if _global_config_file and os.path.exists(_global_config_file):
            self.global_config = self._load_config(_global_config_file)

        # load run configuration
        _run_config_file = None
        if run_config_file:
            _run_config_file = self.to_abs_path(run_config_file)
        else:
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

        if 'steps' not in self.run_config:
            raise BuildRunnerConfigurationError(
                'Could not find a "steps" attribute in config'
            )

        self.artifacts = OrderedDict()

        self.exit_code = None
        self._source_image = None
        self._source_archive = None
        self.log_file = None


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
        Given a list of key aliases lookup the private key file and passphrase
        from the global config.
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
        _key_files = {}
        _matched_aliases = []
        for key_info in ssh_keys:
            if 'file' not in key_info:
                continue
            _key_file = key_info['file']

            _password = None
            if 'password' in key_info:
                _password = key_info['password']

            if 'aliases' not in key_info and not key_info['aliases']:
                continue
            for alias in key_aliases:
                if alias in key_info['aliases']:
                    _matched_aliases.append(alias)
                    if _key_file not in _key_files:
                        _key_files[_key_file] = _password

        for alias in key_aliases:
            if alias not in _matched_aliases:
                raise BuildRunnerConfigurationError(
                    "Could not find SSH key matching alias '%s'" % alias
                )

        return _key_files


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
                return os.path.realpath(
                    os.path.expanduser(os.path.expandvars(local_file))
                )

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
            def _exclude_working_dir(tarinfo):
                """
                Filter to exclude results dir from source archive.
                """
                if tarinfo.name == os.path.basename(self.build_results_dir):
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
            source_builder = DockerBuilder(
                inject={
                    self.get_source_archive_path(): 'source.tar',
                    SOURCE_DOCKERFILE: "Dockerfile",
                },
            )
            exit_code = source_builder.build(
                nocache=True,
            )
            if exit_code != 0 or not source_builder.image:
                raise BuildRunnerProcessingError('Error building source image')
            self._source_image = source_builder.image
        return self._source_image


    def _init_log(self):
        """
        create the log file and open for writing
        """
        log_file_path = os.path.join(self.build_results_dir, 'build.log')
        self.log_file = open(log_file_path, 'w')
        self.log = ConsoleLogger(self.colorize_log, self.log_file)
        self.add_artifact(
            os.path.basename(log_file_path),
            {'type': 'log'},
        )


    def _write_artifact_manifest(self):
        """
        If we have registered artifacts write the files and associated metadata
        to the artifacts manifest.
        """
        if self.artifacts:
            if self.log:
                self.log.write('\nWriting artifact properties\n')
            artifact_manifest = os.path.join(
                self.build_results_dir,
                'artifacts.json',
            )
            with open(artifact_manifest, 'w') as _af:
                json.dump(self.artifacts, _af, indent=2)


    def _exit_message_and_close_log(self, exit_explanation):
        """
        Determine the exit message, output to the log or stdout, close log if
        open.
        """
        exit_message = None
        if self.exit_code:
            exit_message = '\nBuild ERROR.'
        else:
            exit_message = '\nBuild SUCCESS.'

        if self.log_file:
            try:
                if self.log:
                    if exit_explanation:
                        self.log.write('\n' + exit_explanation + '\n')
                    self.log.write(exit_message + '\n')
            finally:
                # close the log_file
                self.log_file.close()
        else:
            if exit_explanation:
                print '\n%s' % exit_explanation
            print exit_message


    def run(self):
        """
        Run the build.
        """
        # reset the exit_code
        self.exit_code = None

        exit_explanation = None
        try:
            # cleanup existing results dir (if needed)
            if os.path.exists(self.build_results_dir):
                print 'Cleaning existing results directory "%s"' % RESULTS_DIR
                shutil.rmtree(self.build_results_dir)

            #create a new results dir
            os.mkdir(self.build_results_dir)
            os.mkdir(self.working_dir)
            # the working directory needs open permissions in the case where it
            # is mounted on a vm filesystem with different user ids
            os.chmod(self.working_dir, 0777)

            self._init_log()

            self.get_source_archive_path()

            # run each step
            for step_name, step_config in self.run_config['steps'].iteritems():
                build_step_runner = BuildStepRunner(
                    self,
                    step_name,
                    step_config,
                )
                build_step_runner.run()

        except BuildRunnerConfigurationError as brce:
            exit_explanation = str(brce)
            self.exit_code = os.EX_CONFIG
        except BuildRunnerProcessingError as brpe:
            exit_explanation = str(brpe)
            self.exit_code = 1
        except requests.exceptions.ConnectionError:
            exit_explanation = (
                "Error communicating with the remote Docker daemon.\nCheck "
                "that it is running and/or that the DOCKER_* environment "
                "variables are set correctly."
            )
            self.exit_code = 1

        finally:
            self._write_artifact_manifest()

            # cleanup the source image
            if self._source_image:
                self.log.write(
                    "Destroying source image %s\n" % self._source_image
                )
                docker.new_client().remove_image(
                    self._source_image,
                    noprune=False,
                    force=True,
                )
            if self._source_archive:
                self.log.write(
                    "Destroying source archive\n"
                )
                os.remove(self._source_archive)

            self._exit_message_and_close_log(exit_explanation)
