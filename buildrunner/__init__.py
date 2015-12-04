"""
Copyright (C) 2014 Adobe
"""
from __future__ import absolute_import
import codecs
from collections import OrderedDict
import copy
import fabric.tasks
from fabric.api import hide, env, run, put, get
from fabric.context_managers import settings
import glob
import jinja2
import json
import os
import requests
import shutil
from StringIO import StringIO
import sys
import tarfile
import tempfile
import threading
import uuid


class BuildRunnerError(Exception):
    """Base BuildRunner Exception"""
    pass


class BuildRunnerConfigurationError(BuildRunnerError):
    """Error indicating an issue with the build configuration"""
    pass


class BuildRunnerProcessingError(BuildRunnerError):
    """Error indicating the build should be 'failed'"""
    pass


from buildrunner import docker
from buildrunner.docker.builder import DockerBuilder
from buildrunner.docker.importer import DockerImporter
from buildrunner.docker.runner import DockerRunner
from buildrunner.provisioners import create_provisioners
from buildrunner.sshagent import DockerSSHAgentProxy
from buildrunner.utils import (
    ContainerLogger,
    ConsoleLogger,
    epoch_time,
    is_dict,
    ordered_load,
)
from vcsinfo import detect_vcs


DEFAULT_GLOBAL_CONFIG_FILE = '~/.buildrunner.yaml'
DEFAULT_RUN_CONFIG_FILES = ['buildrunner.yaml', 'gauntlet.yaml']
RESULTS_DIR = 'buildrunner.results'
DEFAULT_SHELL = '/bin/sh'
SOURCE_VOLUME_MOUNT = '/source'
ARTIFACTS_VOLUME_MOUNT = '/artifacts'


SOURCE_DOCKERFILE = os.path.join(os.path.dirname(__file__), 'SourceDockerfile')
class BuildRunner(object):
    """
    Class used to manage running a build.
    """

    CONTEXT_ENV_PREFIXES = ['BUILDRUNNER_', 'VCSINFO_', 'PACKAGER_']


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

        with open(cfg_file) as _file:
            jtemplate = jinja2.Template(_file.read())

        config_context = copy.deepcopy(self.env)
        config_context.update({
            'CONFIG_FILE': cfg_file,
            'CONFIG_DIR': os.path.dirname(cfg_file),
        })

        if ctx:
            config_context.update(ctx)

        config_contents = jtemplate.render(config_context)
        config = ordered_load(StringIO(config_contents))

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

        # set build number
        self.build_number = build_number
        if not self.build_number:
            self.build_number = epoch_time()

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


    def to_abs_path(self, path):
        """
        Convert a path to an absolute path (if it isn't on already).
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
        self.log_file = codecs.open(log_file_path, 'w', 'utf-8')
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
        except requests.exceptions.ConnectionError as rece:
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
                )

            self._exit_message_and_close_log(exit_explanation)


class BuildStepRunner(object):
    """
    Class used to manage running a build step.
    """


    def __init__(self, build_runner, step_name, step_config):
        """
        Constructor.
        """
        self.name = step_name
        self.config = step_config

        self.build_runner = build_runner
        self.src_dir = self.build_runner.build_dir
        self.results_dir = os.path.join(
            self.build_runner.build_results_dir,
            self.name,
        )
        os.mkdir(self.results_dir)
        self.log = self.build_runner.log

        # generate a unique step id
        self.id = str(uuid.uuid4())

        self.docker_client = docker.new_client()
        self.source_container = None
        self.sshagent = None

        # service runner collections
        self.service_runners = OrderedDict()
        self.service_links = {}


    def _validate_configuration(self):
        """
        Validate the step configuration, reporting any errors by raising
        BuildRunnerConfigurationErrors.
        """
        # 'remote' config trumps others--if passes return
        if 'remote' in self.config:
            r_config = self.config['remote']
            # must have a 'host' or 'platform' attribute
            if 'host' not in r_config:
                raise BuildRunnerConfigurationError(
                    'Step "%s" has a "remote" configuration without '
                    'a "host" attribute\n' % self.name
                )

            # must specify the cmd to run
            if 'cmd' not in self.config['remote']:
                raise BuildRunnerConfigurationError(
                    'Step "%s" has a "remote" configuration without a'
                    '"cmd" attribute\n' % self.name
                )

            # 'remote' build checks out, and since it overrides a Docker one we
            # return here
            return

        # no remote config, must be a docker based build
        if not ('build' in self.config or 'run' in self.config):
            raise BuildRunnerConfigurationError(
                (
                    'Step "%s" must specify a docker build context or '
                    'run configuration\n'
                ) % self.name
            )
        if 'build' not in self.config and 'image' not in self.config['run']:
            raise BuildRunnerConfigurationError(
                (
                    'Step "%s" must specify an image in run configuration '
                    'since there is no docker build context defined\n'
                ) % self.name
            )


    def _run_docker_build(self):
        """
        Run a Docker based build.
        """
        _image = None
        _runner = None
        try:
            # see if we need to build an image
            if 'build' in self.config:
                self.log.write('Running docker build\n')
                _image = self._build_image(self.config['build'])

            # see if we need to run the image
            if 'run' in self.config:
                # create a new source container from the source image
                self.source_container = self.docker_client.create_container(
                    self.build_runner.get_source_image(),
                    command='/bin/sh',
                )['Id']
                self.docker_client.start(
                    self.source_container,
                )
                self.log.write(
                    'Created source container %.10s\n' % (
                        self.source_container,
                    )
                )

                # see if we need to inject ssh keys
                if 'ssh-keys' in self.config['run']:
                    _keys = self._get_ssh_keys(self.config['run']['ssh-keys'])
                    self.sshagent = DockerSSHAgentProxy(
                        self.docker_client,
                        self.log,
                    )
                    self.sshagent.start(_keys)

                # need to run--config defined image overrides the built one
                if 'image' in self.config['run']:
                    _image = self.config['run']['image']
                assert _image != None

                # instantiate any defined service containers
                if 'services' in self.config['run']:
                    _services = self.config['run']['services']
                    for _name, _config in _services.iteritems():
                        self._start_service_container(_name, _config)

                # run the build container
                _runner, _exit = self._run_container(_image)

                # gather artifacts to results dir even if run has bad exit code
                if 'artifacts' in self.config['run']:
                    self._retrieve_artifacts()

                # if we have an exit code abort
                if _exit:
                    raise BuildRunnerProcessingError(
                        "Error running build container"
                    )

            # see if we need to tag/push the resulting image.
            if 'push' in self.config:
                _container_id = None
                if _runner:
                    _container_id = _runner.container['Id']
                self._push_image(self.config['push'], _image, _container_id)

        finally:
            if _runner:
                self.log.write(
                    'Destroying build container %.10s\n' % (
                        _runner.container['Id'],
                    )
                )
                _runner.cleanup()

            if self.service_runners:
                for (_sname, _srun) in reversed(self.service_runners.items()):
                    self.log.write(
                        'Destroying service container "%s"\n' % _sname
                    )
                    _srun.cleanup()

            if self.sshagent:
                self.sshagent.stop()
                self.sshagent = None

            if self.source_container:
                self.log.write(
                    'Destroying source container %.10s\n' % (
                        self.source_container,
                    )
                )
                self.docker_client.remove_container(
                    self.source_container,
                    force=True,
                )


    def _dereference_host(self, host):
        """
        Given a host string determine the actual host value to use by checking
        the global configuration.
        """
        # if no build servers configuration in global config just return host
        if 'build-servers' not in self.build_runner.global_config:
            return host

        build_servers = self.build_runner.global_config['build-servers']
        for _host, _host_aliases in build_servers.iteritems():
            if host in _host_aliases:
                return _host

        return host


    def _get_ssh_keys(self, key_aliases):
        """
        Given a key alias lookup the private key file and passphrase from the
        global config.
        """
        ssh_keys = []
        if not key_aliases:
            return ssh_keys
        if 'ssh-keys' not in self.build_runner.global_config:
            raise BuildRunnerConfigurationError(
                "SSH key aliases specified but no 'ssh-keys' "
                "configuration in global build runner config"
            )

        ssh_keys = self.build_runner.global_config['ssh-keys']
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


    def _resolve_file_alias(self, file_alias):
        """
        Given a file alias lookup the local file path from the global config.
        """
        if not file_alias:
            return None
        if 'local-files' not in self.build_runner.global_config:
            raise BuildRunnerConfigurationError(
                "File aliases specified but no 'local-files' "
                "configuration in global build runner config"
            )

        local_files = self.build_runner.global_config['local-files']
        for local_alias, local_file in local_files.iteritems():
            if file_alias == local_alias:
                return os.path.realpath(os.path.expanduser(os.path.expandvars(local_file)))

        return None


    def _run_remote_build(self):
        """
        Run a remote build.
        """
        host = self._dereference_host(self.config['remote']['host'])
        cmd = self.config['remote']['cmd']

        artifacts = None
        if 'artifacts' in self.config['remote']:
            artifacts = self.config['remote']['artifacts']

        def _run():
            """
            Routine run by fabric.
            """
            # call remote functions to copy tar and build remotely

            remote_build_dir = '/tmp/buildrunner/%s-%s' % (
                self.build_runner.build_id,
                self.name,
            )
            remote_archive_filepath = remote_build_dir + '/source.tar'
            self.log.write(
                "[%s] Creating temporary remote directory '%s'\n" % (
                    host,
                    remote_build_dir,
                )
            )

            mkdir_result = run(
                "mkdir -p %s" % remote_build_dir,
                warn_only=True,
                stdout=self.log,
                stderr=self.log,
            )
            if mkdir_result.return_code:
                raise BuildRunnerProcessingError(
                    "Error creating remote directory"
                )
            else:
                try:
                    self.log.write(
                        "[%s] Pushing archive file to remote directory\n" % (
                            host,
                        )
                    )
                    files = put(
                        self.build_runner.get_source_archive_path(),
                        remote_archive_filepath,
                    )
                    if files:
                        self.log.write(
                            "[%s] Extracting source tree archive on "
                            "remote host:\n" % host
                        )
                        extract_result = run(
                            "(cd %s; tar -xvf source.tar && "
                            "rm -f source.tar)" % (
                                remote_build_dir,
                            ),
                            warn_only=True,
                            stdout=self.log,
                            stderr=self.log,
                        )
                        if extract_result.return_code:
                            raise BuildRunnerProcessingError(
                                "Error extracting archive file"
                            )
                        else:
                            self.log.write("[%s] Running command '%s'\n" % (
                                host,
                                cmd,
                            ))
                            package_result = run(
                                "(cd %s; %s)" % (
                                    remote_build_dir,
                                    cmd,
                                ),
                                warn_only=True,
                                stdout=self.log,
                                stderr=self.log,
                            )

                            if artifacts:
                                _arts = []
                                for _art, _props in artifacts.iteritems():
                                    # check to see if there are artifacts
                                    # that match the pattern
                                    with hide('everything'):
                                        dummy_out = StringIO()
                                        art_result = run(
                                            'ls -A1 %s/%s' % (
                                                remote_build_dir,
                                                _art,
                                            ),
                                            warn_only=True,
                                            stdout=dummy_out,
                                            stderr=dummy_out,
                                        )
                                        if art_result.return_code:
                                            continue

                                    # we have at least one match--run the get
                                    with settings(warn_only=True):
                                        for _ca in get(
                                                "%s/%s" % (
                                                    remote_build_dir,
                                                    _art,
                                                ),
                                                "%s/%%(basename)s" % (
                                                    self.results_dir,
                                                )
                                        ):
                                            _arts.append(_ca)
                                            self.build_runner.add_artifact(
                                                os.path.join(
                                                    self.name,
                                                    os.path.basename(_ca),
                                                ),
                                                _props,
                                            )
                                self.log.write("\nGathered artifacts:\n")
                                for _art in _arts:
                                    self.log.write(
                                        '- found %s\n' % os.path.basename(_art),
                                    )
                                self.log.write("\n")


                            if package_result.return_code:
                                raise BuildRunnerProcessingError(
                                    "Error running remote build"
                                )

                    else:
                        raise BuildRunnerProcessingError(
                            "Error uploading source archive to host"
                        )
                finally:
                    self.log.write(
                        "[%s] Cleaning up remote temp directory %s\n" % (
                            host,
                            remote_build_dir,
                        )
                    )
                    cleanup_result = run(
                        "rm -Rf %s" % remote_build_dir,
                        stdout=self.log,
                        stderr=self.log,
                    )
                    if cleanup_result.return_code:
                        raise BuildRunnerProcessingError(
                            "Error cleaning up remote directory"
                        )

        self.log.write("Building on remote host %s\n\n" % host)
        fabric.tasks.execute(
            fabric.tasks.WrappedCallableTask(_run),
            hosts=[host],
        )


    def run(self):
        """
        Run the build step.
        """
        # validate the configuration
        self._validate_configuration()

        # create the step results dir
        self.log.write('\nRunning step "%s"\n' % self.name)
        self.log.write('________________________________________\n')

        if 'remote' in self.config:
            self._run_remote_build()
        else:
            self._run_docker_build()


    def _retrieve_artifacts(self):
        """
        Gather artifacts from the build container and place in the
        step-specific results dir.

        This function actually spins up a separate docker container that mounts
        the build container's source directory, queries for artifact patterns,
        then copies to the step-specific results directory (which is mounted as
        a host volume). It also appropriately sets file ownership of the
        archived artifacts to the user running the buildrunner process.
        """
        self.log.write('Gathering artifacts\n')
        patterns = self.config['run']['artifacts']
        if not patterns:
            return

        # get the current user/group ids of our process so we can set them via
        # the busybox container
        cur_user = os.getuid()
        cur_group = os.getgid()

        # use a small busybox image to list the files matching the glob
        artifact_lister = None
        try:
            artifact_lister = DockerRunner(
                'busybox:ubuntu-14.04',
            )
            #TODO: see if we can use archive commands to eliminate the need for
            #the /stepresults volume when we can move to api v1.20
            artifact_lister.start(
                volumes_from=[self.source_container],
                volumes={
                    self.results_dir: '/stepresults',
                },
                working_dir=SOURCE_VOLUME_MOUNT,
                shell='/bin/sh',
            )

            file_info_delimiter = '~!~'
            for pattern, properties in patterns.iteritems():
                # query files for each artifacts pattern, capturing the output
                # for parsing
                stat_output_file = "%s.out" % str(uuid.uuid4())
                stat_output_file_local = os.path.join(
                    self.results_dir,
                    stat_output_file,
                )
                exit_code = artifact_lister.run(
                    'stat -c "%%n%s%%F" %s > /stepresults/%s' % (
                        file_info_delimiter,
                        pattern,
                        stat_output_file,
                    ),
                    stream=False,
                )

                # if the command was successful we found something
                if 0 == exit_code:
                    with open(stat_output_file_local, 'r') as output_fd:
                        output = output_fd.read()
                    artifact_files = [
                        af.strip() for af in output.split('\n')
                    ]
                    for artifact_info in artifact_files:
                        if artifact_info and file_info_delimiter in artifact_info:
                            artifact_file, file_type = artifact_info.split(
                                file_info_delimiter,
                            )

                            # check if the file is directory, to copy recursive
                            is_dir = file_type.strip() == 'directory'

                            file_type = ''
                            archive_command = ''
                            new_artifact_file = ''

                            filename = os.path.basename(artifact_file)

                            if is_dir:
                                file_type = "directory"
                                output_file_name = filename + '.tar.gz'
                                new_artifact_file = '/stepresults/' + output_file_name
                                working_dir = ''
                                if os.path.dirname(artifact_file):
                                    working_dir = ' -C %s' % os.path.dirname(artifact_file)
                                archive_command = 'tar -cvzf ' + new_artifact_file + working_dir + ' ' + filename
                            else:
                                file_type = "file"
                                output_file_name = filename
                                new_artifact_file = '/stepresults/' + output_file_name
                                archive_command = 'cp ' + artifact_file + ' ' + new_artifact_file

                            self.log.write('- found {type} {name}\n'.format(type=file_type, name=filename))

                            copy_exit = artifact_lister.run(
                                archive_command,
                            )
                            if 0 != copy_exit:
                                raise Exception(
                                    "Error gathering artifact %s" % (
                                        artifact_file,
                                    ),
                                )

                            # make sure the current user is the owner
                            chown_exit = artifact_lister.run(
                                'chown %d:%d %s' % (
                                    cur_user,
                                    cur_group,
                                    new_artifact_file,
                                ),
                            )
                            if 0 != chown_exit:
                                raise Exception(
                                    "Error gathering artifact %s" % (
                                        artifact_file,
                                    ),
                                )

                            # add properties if directory
                            new_properties = properties or dict()
                            if is_dir:
                                new_properties['buildrunner.compressed.directory'] = 'true'

                            # register the artifact with the run controller
                            self.build_runner.add_artifact(
                                os.path.join(self.name, output_file_name),
                                new_properties,
                            )

                #remove the stat output file
                os.remove(stat_output_file_local)

        finally:
            if artifact_lister:
                artifact_lister.cleanup()


    def _process_volumes_from(self, volumes_from):
        _volumes_from = []
        for sc_vf in volumes_from:
            volumes_from_definition = sc_vf.rsplit(':')
            service_container = volumes_from_definition[0]
            volume_option = None
            if len(volumes_from_definition) > 1:
                volume_option = volumes_from_definition[1]
            if service_container not in self.service_links.values():
                raise BuildRunnerConfigurationError(
                    '"volumes_from" configuration "%s" does not '
                    'reference a valid service container\n' % sc_vf
                )
            for container, service in self.service_links.iteritems():
                if service == service_container:
                    if volume_option:
                        _volumes_from.append(
                            "%s:%s" % (container, volume_option),
                        )
                    else:
                        _volumes_from.append(container)
                    break
        return _volumes_from


    def _run_container(self, image):
        """
        Run the main step container.
        """
        runner = None
        container_id = None
        container_logger = None
        container_meta_logger = None
        try:
            self.log.write('Creating build container from image "%s"\n' % (
                image,
            ))
            container_logger = ContainerLogger.for_build_container(
                self.log,
                self.name,
            )
            container_meta_logger = ContainerLogger.for_build_container(
                self.log,
                self.name
            )

            # default to a container that runs the default image command
            _shell = None

            # determine if there is a command to run
            _cmds = []
            if 'cmd' in self.config['run']:
                _shell = DEFAULT_SHELL
                _cmds.append(self.config['run']['cmd'])
            if 'cmds' in self.config['run']:
                _shell = DEFAULT_SHELL
                _cmds.extend(self.config['run']['cmds'])

            # determine if there are any provisioners defined
            _provisioners = None
            if 'provisioners' in self.config['run']:
                _shell = DEFAULT_SHELL
                _provisioners = create_provisioners(
                    self.config['run']['provisioners'],
                    container_logger,
                )

            # if a shell is specified use it
            if 'shell' in self.config['run']:
                _shell = self.config['run']['shell']

            # determine the working dir the build should be run in
            _cwd = SOURCE_VOLUME_MOUNT
            if 'cwd' in self.config['run']:
                _cwd = self.config['run']['cwd']

            # determine if a user is specified
            _user = None
            if 'user' in self.config['run']:
                _user = self.config['run']['user']

            # determine if a hostname is specified
            _hostname = None
            if 'hostname' in self.config['run']:
                _hostname = self.config['run']['hostname']

            # determine if a dns host is specified
            _dns = None
            if 'dns' in self.config['run']:
                _dns = self.config['run']['dns']

            # determine if a dns_search domain is specified
            _dns_search = None
            if 'dns_search' in self.config['run']:
                _dns_search = self.config['run']['dns_search']

            # set step specific environment variables
            _env = dict(self.build_runner.env)
            if 'env' in self.config['run']:
                for key, value in self.config['run']['env'].iteritems():
                    _env[key] = value

            _volumes_from = [self.source_container]

            # see if we need to map any service container volumes
            if 'volumes_from' in self.config['run']:
                _volumes_from.extend(self._process_volumes_from(
                    self.config['run']['volumes_from'],
                ))

            # see if we need to attach to a sshagent container
            if self.sshagent:
                ssh_container, ssh_env = self.sshagent.get_info()
                if ssh_container:
                    _volumes_from.append(ssh_container)
                if ssh_env:
                    for _var, _val in ssh_env.iteritems():
                        _env[_var] = _val

            _volumes = {
                self.build_runner.build_results_dir: \
                    ARTIFACTS_VOLUME_MOUNT + ':ro',
            }

            # see if we need to inject any files
            if 'files' in self.config['run']:
                for f_alias, f_path in self.config['run']['files'].iteritems():
                    # lookup file from alias
                    f_local = self._resolve_file_alias(f_alias)
                    if not f_local or not os.path.exists(f_local):
                        raise BuildRunnerConfigurationError(
                            "Cannot find valid local file for alias '%s'" % (
                                f_alias,
                            )
                        )

                    if f_path[-3:] not in [':ro', ':rw']:
                        f_path = f_path + ':ro'

                    _volumes[f_local] = f_path

                    container_meta_logger.write("Mounting %s -> %s\n" % (f_local, f_path))

            # create and start runner, linking any service containers
            runner = DockerRunner(
                image,
            )
            container_id = runner.start(
                volumes=_volumes,
                volumes_from=_volumes_from,
                links=self.service_links,
                shell=_shell,
                provisioners=_provisioners,
                environment=_env,
                user=_user,
                hostname=_hostname,
                dns=_dns,
                dns_search=_dns_search,
                working_dir=_cwd,
            )
            self.log.write(
                'Started build container %.10s\n' % container_id
            )

            exit_code = None
            if _cmds:
                # run each cmd
                for _cmd in _cmds:
                    container_meta_logger.write(
                        "cmd> %s\n" % _cmd
                    )
                    exit_code = runner.run(
                        _cmd,
                        console=container_logger,
                    )
                    container_meta_logger.write(
                        'Command "%s" exited with code %s\n' % (
                            _cmd,
                            exit_code,
                        )
                    )

                    if 0 != exit_code:
                        break
            else:
                runner.attach_until_finished(container_logger)
                exit_code = runner.exit_code
                container_meta_logger.write(
                    'Container exited with code %s\n' % (
                        exit_code,
                    )
                )

            if 0 != exit_code:
                return runner, 1

        finally:
            if runner:
                runner.stop()
            if container_logger:
                container_logger.cleanup()
            if container_meta_logger:
                container_meta_logger.cleanup()

        return runner, None


    def _build_image(self, build_context):
        """
        Build an image using the given build_context.

        The build_context can be either a path to a local directory that
        contains a Dockerfile or a dict containing configuration information.
        """
        path = None
        to_inject = []
        nocache = False
        if is_dict(build_context):
            if 'import' in build_context:
                # will override other configuration and perform a 'docker import'
                self.log.write('  Importing %s as a Docker image\n' % (
                    build_context['import']
                ))
                return DockerImporter(build_context['import']).import_image()

            if 'path' not in build_context and 'inject' not in build_context:
                raise BuildRunnerConfigurationError(
                    'Docker build context must specify a '
                    '"path" or "inject" attribute'
                )

            if 'path' in build_context:
                path = build_context['path']

            if 'no-cache' in build_context:
                nocache = build_context['no-cache']

            if 'inject' in build_context:
                to_inject = {}
                for src_glob, dest_dir in build_context['inject'].iteritems():
                    src_glob = self.build_runner.to_abs_path(src_glob)
                    for source_file in glob.glob(src_glob):
                        to_inject[source_file] = os.path.join(
                            '.',
                            dest_dir,
                            os.path.basename(source_file),
                        )
        else:
            path = build_context

        if path:
            path = self.build_runner.to_abs_path(path)

        if path and not os.path.exists(path):
            raise BuildRunnerConfigurationError(
                'Invalid build context path "%s"' % path
            )

        builder = DockerBuilder(
            path,
            inject=to_inject,
        )
        try:
            exit_code = builder.build(
                console=self.log,
                nocache=nocache,
            )
            if exit_code != 0 or not builder.image:
                raise BuildRunnerProcessingError('Error building image')
        finally:
            builder.cleanup()
        return builder.image


    def _start_service_container(self, service_name, service_config):
        """
        Start a service container.
        """
        # validate that we have an 'image' or 'build' config
        if not ('image' in service_config or 'build' in service_config):
            raise BuildRunnerConfigurationError(
                (
                    'Step "%s", service "%s" must specify an '
                    'image or docker build context'
                ) % (self.name, service_name)
            )
        if 'image' in service_config and 'build' in service_config:
            raise BuildRunnerConfigurationError(
                (
                    'Step "%s", service "%s" must specify either '
                    'an image or docker build context, not both'
                ) % (self.name, service_name)
            )

        _image = None
        # see if we need to build an image
        if 'build' in service_config:
            _image = self._build_image(service_config['build'])

        if 'image' in service_config:
            _image = service_config['image']
        assert _image

        self.log.write(
            'Creating service container "%s" from image "%s"\n' % (
                service_name,
                _image,
            )
        )
        service_logger = ContainerLogger.for_service_container(
            self.log,
            service_name,
        )

        # setup custom env variables
        _env = dict(self.build_runner.env)

        # do we need to change to a given dir when running
        # a cmd or script?
        _cwd = None
        if 'cwd' in service_config:
            _cwd = service_config['cwd']

        # need to expose any ports?
        _ports = None
        if 'ports' in service_config:
            _ports = service_config['ports']

        # default to a container that runs the default
        # image command
        _shell = None

        # do we need to run an explicit cmd?
        if 'cmd' in service_config:
            # if so we need to run the cmd within a default
            # shell--specify it here
            _shell = DEFAULT_SHELL

        # if a shell is specified use it
        if 'shell' in service_config:
            _shell = service_config['shell']

        # see if there are any provisioners defined
        _provisioners = None
        if 'provisioners' in service_config:
            _provisioners = create_provisioners(
                service_config['provisioners'],
                service_logger,
            )

        # determine if a user is specified
        _user = None
        if 'user' in service_config:
            _user = service_config['user']

        # determine if a hostname is specified
        _hostname = None
        if 'hostname' in service_config:
            _hostname = service_config['hostname']

        # determine if a dns host is specified
        _dns = None
        if 'dns' in service_config:
            _dns = service_config['dns']

        # determine if a dns_search domain is specified
        _dns_search = None
        if 'dns_search' in service_config:
            _dns_search = service_config['dns_search']

        # set service specific environment variables
        if 'env' in service_config:
            for key, value in service_config['env'].iteritems():
                _env[key] = value

        _volumes_from = [self.source_container]

        # see if we need to map any service container volumes
        if 'volumes_from' in service_config:
            _volumes_from.extend(self._process_volumes_from(
                service_config['volumes_from'],
            ))

        # instantiate and start the runner
        service_runner = DockerRunner(
            _image,
        )
        self.service_runners[service_name] = service_runner
        cont_name = self.id + '-' + service_name
        service_container_id = service_runner.start(
            name=cont_name,
            volumes={
                self.build_runner.build_results_dir: \
                    ARTIFACTS_VOLUME_MOUNT + ':ro',
            },
            volumes_from=_volumes_from,
            ports=_ports,
            links=self.service_links,
            shell=_shell,
            provisioners=_provisioners,
            environment=_env,
            user=_user,
            hostname=_hostname,
            dns=_dns,
            dns_search=_dns_search,
            working_dir=_cwd,
        )
        self.service_links[cont_name] = service_name

        def attach_to_service():
            """Function to attach to service in a separate thread."""
            # if specified, run a command
            if 'cmd' in service_config:
                exit_code = service_runner.run(
                    service_config['cmd'],
                    console=service_logger,
                )
                if 0 != exit_code:
                    service_logger.write(
                        'Service command "%s" exited with code %s\n' % (
                            service_config['cmd'],
                            exit_code,
                        )
                    )
            else:
                service_runner.attach_until_finished(service_logger)
            service_logger.cleanup()

        # Attach to the container in a separate thread
        service_management_thread = threading.Thread(
            name="%s--%s" % (self.name, service_name),
            target=attach_to_service,
        )
        service_management_thread.daemon = True
        service_management_thread.start()

        self.log.write('Started service container "%s" (%.10s)\n' % (
            service_name,
            service_container_id,
        ))


    def _push_image(self, push_config, image, container_id=None):
        """
        Push the resulting image (either from the build step, or if there is a
        run step, the snapshot of the resulting run container) to the given
        registry/repository.
        """
        repository = None
        insecure_registry = False
        tags = []
        if is_dict(push_config):
            if 'repository' not in push_config:
                self.log.write(
                    'Push configuration must at least specify a '
                    '"repository" attribute\n'
                )
                raise Exception(
                    'no "repository" attribute in push configuration'
                )
            repository = push_config['repository']

            if 'tags' in push_config:
                tags = push_config['tags']

            if 'insecure_registry' in push_config:
                insecure_registry = push_config['insecure_registry'] == True
        else:
            repository = push_config

        self.log.write(
            'Pushing resulting image to "%s".\n' % repository
        )

        # if we have a container_id then we create an image based on
        # the end state of the container, otherwise we use the image id
        image_to_use = image
        if container_id:
            self.log.write(
                'Committing build container %s as an image for tagging\n' % (
                    container_id,
                )
            )
            image_to_use = self.docker_client.commit(container_id)['Id']

        # determine internal tag based on source control information and build
        # number
        tags.append(self.build_runner.build_id)

        # tag the image
        for _tag in tags:
            self.log.write(
                'Tagging image "%s" with repository:tag "%s:%s"\n' % (
                    image_to_use,
                    repository,
                    _tag,
                )
            )
            self.docker_client.tag(
                image_to_use,
                repository,
                tag=_tag,
                force=True,
            )

        # see if we should push the image to a remote repository
        if self.build_runner.push:
            # push the image
            stream = self.docker_client.push(
                repository,
                stream=True,
                insecure_registry=insecure_registry,
            )
            previous_status = None
            for msg_str in stream:
                msg = json.loads(msg_str)
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
                        "This could be because you are not authenticated "
                        "with the given Docker registry (try 'docker login "
                        "<registry>')\n\n"
                    ))
                    raise BuildRunnerProcessingError(error_detail)
                else:
                    self.log.write(str(msg) + '\n')

            # cleanup the image and tag
            self.docker_client.remove_image(image_to_use, noprune=True)
        else:
            self.log.write(
                'push not requested--not cleaning up image locally\n'
            )

        # add image as artifact
        self.build_runner.add_artifact(
            os.path.join(self.name, image_to_use),
            {
                'type': 'docker-image',
                'docker:image': image_to_use,
                'docker:repository': repository,
                'docker:tags': tags,
            },
        )
