"""
Copyright (C) 2014 Adobe
"""
from __future__ import absolute_import
from collections import OrderedDict
import glob
import json
import os
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


from buildrunner import docker
from buildrunner.docker.builder import DockerBuilder
from buildrunner.docker.runner import DockerRunner
from buildrunner.provisioners import create_provisioners
from buildrunner.utils import (
    ContainerLogger,
    ConsoleLogger,
    epoch_time,
    is_dict,
    ordered_load,
)
from vcsinfo import detect_vcs


DEFAULT_CONFIG_FILES = ['buildrunner.yaml', 'gauntlet.yaml']
RESULTS_DIR = 'buildrunner.results'
DEFAULT_SHELL = '/bin/sh'
SOURCE_VOLUME_MOUNT = '/source'
ARTIFACTS_VOLUME_MOUNT = '/artifacts'


class BuildRunnerConfigurationError(BuildRunnerError):
    """Error indicating an issue with the build configuration"""
    pass


class BuildRunnerProcessingError(BuildRunnerError):
    """Error indicating the build should be 'failed'"""
    pass


SOURCE_DOCKERFILE = os.path.join(os.path.dirname(__file__), 'SourceDockerfile')
class BuildRunner(object):
    """
    Class used to manage running a build.
    """


    def __init__(
        self,
        build_dir,
        config_file=None,
        build_number=None,
        push=False,
    ):
        """
        """
        self.build_dir = build_dir
        self.build_results_dir = os.path.join(self.build_dir, RESULTS_DIR)
        self.push = push

        run_config_file = None
        if config_file:
            run_config_file = self.to_abs_path(config_file)
        else:
            for name_to_try in DEFAULT_CONFIG_FILES:
                _to_try = self.to_abs_path(name_to_try)
                if os.path.exists(_to_try):
                    run_config_file = _to_try
                    break

        if not run_config_file or not os.path.exists(run_config_file):
            raise BuildRunnerConfigurationError(
                'Cannot find build configuration file'
            )
        self.run_config = None
        with open(run_config_file) as _file:
            self.run_config = ordered_load(_file)

        self.build_number = build_number
        if not self.build_number:
            self.build_number = epoch_time()

        self.log = None

        self.vcs = detect_vcs(self.build_dir)
        self.build_id = "%s-%s" % (self.vcs.id_string, self.build_number)

        # default environment
        self.env = {
            'BUILDRUNNER_BUILD_NUMBER': str(self.build_number),
            'BUILDRUNNER_BUILD_ID': str(self.build_id),
            'VCSINFO_BRANCH': str(self.vcs.branch),
            'VCSINFO_NUMBER': str(self.vcs.number),
            'VCSINFO_ID': str(self.vcs.id),
            'VCSINFO_MODIFIED': str(self.vcs.modified),
        }

        if 'steps' not in self.run_config:
            raise BuildRunnerConfigurationError(
                'Could not find a "steps" attribute in config'
            )

        self.artifacts = OrderedDict()

        self.exit_code = None
        self.source_image = None
        self.log_file = None


    def to_abs_path(self, path):
        """
        Convert a path to an absolute path (if it isn't on already).
        """
        if os.path.isabs(path):
            return path
        return os.path.join(
            self.build_dir,
            path,
        )


    def add_artifact(self, artifact_file, properties):
        """
        Register a build artifact to be included in the artifacts manifest.
        """
        self.artifacts[artifact_file] = properties


    def _create_source_image(self):
        """
        Create the base image source containers will be created from.
        """
        self.log.write('Creating source image\n')
        source_builder = DockerBuilder(
            inject={
                self.build_dir: SOURCE_VOLUME_MOUNT,
                SOURCE_DOCKERFILE: "Dockerfile",
            },
        )
        exit_code = source_builder.build(
            nocache=True,
        )
        if exit_code != 0 or not source_builder.image:
            raise BuildRunnerProcessingError('Error building source image')
        self.source_image = source_builder.image
        return self.source_image


    def _init_log(self):
        """
        create the log file and open for writing
        """
        log_file_path = os.path.join(self.build_results_dir, 'build.log')
        self.log_file = open(log_file_path, 'w')
        self.log = ConsoleLogger(self.log_file)
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

        source_builder = None
        exit_explanation = None
        try:
            # cleanup existing results dir (if needed)
            if os.path.exists(self.build_results_dir):
                print 'Cleaning existing results directory "%s"' % RESULTS_DIR
                shutil.rmtree(self.build_results_dir)

            #create a new results dir
            os.mkdir(self.build_results_dir)

            self._init_log()

            self._create_source_image()

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

        finally:
            self._write_artifact_manifest()

            # cleanup the source image
            if source_builder:
                source_builder.cleanup()
            if self.source_image:
                self.log.write(
                    "Destroying source image %s\n" % self.source_image
                )
                docker.new_client().remove_image(
                    self.source_image,
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

        # service runner collections
        self.service_runners = OrderedDict()
        self.service_links = {}


    def run(self):
        """
        Run the build step.
        """
        # validate the configuration
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

        # create the step results dir
        self.log.write('\nRunning step "%s"\n' % self.name)
        self.log.write('________________________________________\n')

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
                    self.build_runner.source_image,
                    command='/bin/sh',
                )['Id']
                self.docker_client.start(
                    self.source_container,
                )
                self.log.write(
                    'Created source container "%.10s"\n' % (
                        self.source_container,
                    )
                )

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
            artifact_lister = DockerRunner('busybox')
            artifact_lister.start(
                volumes_from=[self.source_container],
                volumes={
                    self.results_dir: '/stepresults',
                },
                working_dir=SOURCE_VOLUME_MOUNT,
                shell='/bin/sh',
            )

            for pattern, properties in patterns.iteritems():
                # query files for each artifacts pattern, capturing the output
                # for parsing
                output = StringIO()
                exit_code = artifact_lister.run(
                    'ls -A1 ' + pattern,
                    console=output,
                )

                # if the command was succssful we found something
                if 0 == exit_code:
                    artifact_files = output.getvalue().split('\n')
                    for artifact_file in artifact_files:
                        if artifact_file:
                            # copy artifact file to step dir
                            filename = os.path.basename(artifact_file)
                            self.log.write('- found %s\n' % filename)
                            new_artifact_file = '/stepresults/' + filename
                            copy_exit = artifact_lister.run(
                                'cp ' + artifact_file + ' ' + new_artifact_file,
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

                            # register the artifact with the run controller
                            self.build_runner.add_artifact(
                                os.path.join(self.name, filename),
                                properties or dict(),
                            )

        finally:
            if artifact_lister:
                artifact_lister.cleanup()


    def _run_container(self, image):
        """
        Run the main step container.
        """
        runner = None
        container_id = None
        try:
            self.log.write('Creating build container from image "%s"\n' % (
                image,
            ))
            container_logger = ContainerLogger.for_build_container(
                self.log,
                self.name,
            )

            # default to a container that runs the default image command
            _shell = None

            # determine if there is a command to run
            _cmd = None
            if 'cmd' in self.config['run']:
                _shell = DEFAULT_SHELL
                _cmd = self.config['run']['cmd']

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

            # set step specific environment variables
            _env = dict(self.build_runner.env)
            if 'env' in self.config['run']:
                for key, value in self.config['run']['env'].iteritems():
                    _env[key] = value

            # create and start runner, linking any service containers
            runner = DockerRunner(image)
            container_id = runner.start(
                volumes={
                    self.build_runner.build_results_dir: \
                        ARTIFACTS_VOLUME_MOUNT + ':ro',
                },
                volumes_from=[self.source_container],
                links=self.service_links,
                shell=_shell,
                provisioners=_provisioners,
                environment=_env,
                user=_user,
            )
            self.log.write(
                'Started build container %.10s\n' % container_id
            )

            exit_code = None
            if _cmd:
                # run the cmd
                container_logger.write(
                    "cmd> %s\n" % _cmd
                )
                exit_code = runner.run(
                    _cmd,
                    console=container_logger,
                    cwd=_cwd,
                )
            else:
                runner.attach_until_finished(container_logger)
                exit_code = runner.exit_code

            if 0 != exit_code:
                if _cmd:
                    container_logger.write(
                        'Command "%s" exited with code %s\n' % (
                            _cmd,
                            exit_code,
                        )
                    )
                else:
                    container_logger.write(
                        'Container exited with code %s\n' % (
                            exit_code,
                        )
                    )
                return runner, 1

        finally:
            if runner:
                runner.stop()

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

        # set service specific environment variables
        if 'env' in service_config:
            for key, value in service_config['env'].iteritems():
                _env[key] = value

        # instantiate and start the runner
        service_runner = DockerRunner(
            _image,
        )
        self.service_runners[service_name] = service_runner
        cont_name = self.id + '-' + service_name
        self.service_links[cont_name] = service_name
        service_container_id = service_runner.start(
            name=cont_name,
            volumes={
                self.build_runner.build_results_dir: \
                    ARTIFACTS_VOLUME_MOUNT + ':ro',
            },
            volumes_from=[self.source_container],
            ports=_ports,
            shell=_shell,
            provisioners=_provisioners,
            environment=_env,
            user=_user,
        )

        def attach_to_service():
            """Function to attach to service in a separate thread."""
            # if specified, run a command
            if 'cmd' in service_config:
                exit_code = service_runner.run(
                    service_config['cmd'],
                    console=service_logger,
                    cwd=_cwd,
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
        else:
            repository = push_config

        self.log.write(
            'Pushing resulting image to "%s".' % repository
        )

        # if we have a container_id then we create an image based on
        # the end state of the container, otherwise we use the image id
        image_to_use = image
        if container_id:
            self.log.write(
                'Committing build container %s as an image for tagging' % (
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
                'Tagging image "%s" with repository:tag "%s:%s"' % (
                    image_to_use,
                    repository,
                    _tag,
                )
            )
            self.docker_client.tag(image_to_use, repository, tag=_tag)

        # see if we should push the image to a remote repository
        if self.build_runner.push:
            # push the image
            stream = self.docker_client.push(repository, stream=True)
            previous_status = None
            for msg_str in stream:
                msg = json.loads(msg_str)
                if 'status' in msg:
                    if msg['status'] == previous_status:
                        continue
                    self.log.write(msg['status'])
                    previous_status = msg['status']
                else:
                    self.log.write(str(msg))

            # cleanup the image and tag
            self.docker_client.remove_image(image_to_use, noprune=True)
        else:
            self.log.write('push not requested--not cleaning up image locally')

        # add image as artifact
        self.build_runner.add_artifact(
            os.path.join(self.name, image_to_use),
            {
                'type': 'docker-image',
                'image': image_to_use,
                'repository': repository,
                'tags': tags,
            },
        )
