"""
Copyright (C) 2015 Adobe
"""
from __future__ import absolute_import
from collections import OrderedDict
import os
import threading
import uuid

import buildrunner.docker
from buildrunner.docker.daemon import DockerDaemonProxy
from buildrunner.docker.runner import DockerRunner
from buildrunner.errors import (
    BuildRunnerConfigurationError,
    BuildRunnerProcessingError,
)
from buildrunner.provisioners import create_provisioners
from buildrunner.sshagent import DockerSSHAgentProxy
from buildrunner.steprunner.tasks import BuildStepRunnerTask
from buildrunner.steprunner.tasks.build import BuildBuildStepRunnerTask
from buildrunner.utils import ContainerLogger, is_dict


DEFAULT_SHELL = '/bin/sh'
SOURCE_VOLUME_MOUNT = '/source'
ARTIFACTS_VOLUME_MOUNT = '/artifacts'
FILE_INFO_DELIMITER = '~!~'


class RunBuildStepRunnerTask(BuildStepRunnerTask):
    """
    Class used to manage "run" build tasks.
    """


    def __init__(self, step_runner, config):
        super(RunBuildStepRunnerTask, self).__init__(step_runner, config)
        self._docker_client = buildrunner.docker.new_client()
        self._source_container = None
        self._service_runners = OrderedDict()
        self._service_links = {}
        self._sshagent = None
        self._dockerdaemonproxy = None
        self.runner = None


    def _get_source_container(self):
        """
        Get (creating the container if necessary) the container id of the
        source container.
        """
        if not self._source_container:
            self._source_container = self._docker_client.create_container(
                self.step_runner.build_runner.get_source_image(),
                command='/bin/sh',
            )['Id']
            self._docker_client.start(
                self._source_container,
            )
            self.step_runner.log.write(
                'Created source container %.10s\n' % (
                    self._source_container,
                )
            )
        return self._source_container


    def _process_volumes_from(self, volumes_from):
        """
        Translate the volumes_from configuration to the appropriate service
        container ids.
        """
        _volumes_from = []
        for sc_vf in volumes_from:
            volumes_from_definition = sc_vf.rsplit(':')
            service_container = volumes_from_definition[0]
            volume_option = None
            if len(volumes_from_definition) > 1:
                volume_option = volumes_from_definition[1]
            if service_container not in self._service_links.values():
                raise BuildRunnerConfigurationError(
                    '"volumes_from" configuration "%s" does not '
                    'reference a valid service container\n' % sc_vf
                )
            for container, service in self._service_links.iteritems():
                if service == service_container:
                    if volume_option:
                        _volumes_from.append(
                            "%s:%s" % (container, volume_option),
                        )
                    else:
                        _volumes_from.append(container)
                    break
        return _volumes_from


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
        self.step_runner.log.write('Gathering artifacts\n')
        if not self.config['artifacts']:
            return

        # use a small busybox image to list the files matching the glob
        artifact_lister = None
        try:
            artifact_lister = DockerRunner(
                'busybox:ubuntu-14.04',
            )
            #TODO: see if we can use archive commands to eliminate the need for
            #the /stepresults volume when we can move to api v1.20
            artifact_lister.start(
                volumes_from=[self._get_source_container()],
                volumes={
                    self.step_runner.results_dir: '/stepresults',
                },
                working_dir=SOURCE_VOLUME_MOUNT,
                shell='/bin/sh',
            )

            for pattern, properties in self.config['artifacts'].iteritems():
                # query files for each artifacts pattern, capturing the output
                # for parsing
                stat_output_file = "%s.out" % str(uuid.uuid4())
                stat_output_file_local = os.path.join(
                    self.step_runner.results_dir,
                    stat_output_file,
                )
                exit_code = artifact_lister.run(
                    'stat -c "%%n%s%%F" %s > /stepresults/%s' % (
                        FILE_INFO_DELIMITER,
                        pattern,
                        stat_output_file,
                    ),
                    stream=False,
                )

                # if the command was successful we found something
                if exit_code == 0:
                    with open(stat_output_file_local, 'r') as output_fd:
                        output = output_fd.read()
                    artifact_files = [
                        af.strip() for af in output.split('\n')
                    ]
                    for art_info in artifact_files:
                        if not art_info or FILE_INFO_DELIMITER not in art_info:
                            continue
                        artifact_file, file_type = art_info.split(
                            FILE_INFO_DELIMITER,
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
                            new_artifact_file = (
                                '/stepresults/' +
                                output_file_name.replace('"', '\\"')
                            )
                            working_dir = ''
                            if os.path.dirname(artifact_file):
                                working_dir = (
                                    ' -C "%s"' % os.path.dirname(
                                        artifact_file,
                                    ).replace('"', '\\"')
                                )
                            archive_command = (
                                'tar -cvzf "' + new_artifact_file + '"' +
                                working_dir + ' "' +
                                filename.replace('"', '\\"') + '"'
                            )
                        else:
                            file_type = "file"
                            output_file_name = filename
                            new_artifact_file = (
                                '/stepresults/' +
                                output_file_name.replace('"', '\\"')
                            )
                            archive_command = (
                                'cp "' + artifact_file.replace('"', '\\"') +
                                '" "' + new_artifact_file +
                                '"'
                            )

                        self.step_runner.log.write(
                            '- found {type} {name}\n'.format(
                                type=file_type,
                                name=filename,
                            )
                        )

                        exit_code = artifact_lister.run(
                            archive_command,
                        )
                        if exit_code != 0:
                            raise Exception(
                                "Error gathering artifact %s" % (
                                    artifact_file,
                                ),
                            )

                        # make sure the current user/group ids of our
                        # process are set as the owner of the files
                        exit_code = artifact_lister.run(
                            'chown %d:%d "%s"' % (
                                os.getuid(),
                                os.getgid(),
                                new_artifact_file,
                            ),
                        )
                        if exit_code != 0:
                            raise Exception(
                                "Error gathering artifact %s" % (
                                    artifact_file,
                                ),
                            )

                        # add properties if directory
                        new_properties = properties or dict()
                        if is_dir:
                            new_properties[
                                'buildrunner.compressed.directory'
                            ] = 'true'

                        # register the artifact with the run controller
                        self.step_runner.build_runner.add_artifact(
                            os.path.join(
                                self.step_runner.name,
                                output_file_name,
                            ),
                            new_properties,
                        )

                #remove the stat output file
                if os.path.exists(stat_output_file_local):
                    os.remove(stat_output_file_local)

        finally:
            if artifact_lister:
                artifact_lister.cleanup()


    def _start_service_container(self, name, config):
        """
        Start a service container.
        """
        # validate that we have an 'image' or 'build' config
        if not ('image' in config or 'build' in config):
            raise BuildRunnerConfigurationError(
                (
                    'Step "%s", service "%s" must specify an '
                    'image or docker build context'
                ) % (self.step_runner.name, name)
            )
        if 'image' in config and 'build' in config:
            raise BuildRunnerConfigurationError(
                (
                    'Step "%s", service "%s" must specify either '
                    'an image or docker build context, not both'
                ) % (self.step_runner.name, name)
            )

        _image = None
        # see if we need to build an image
        if 'build' in config:
            build_image_task = BuildBuildStepRunnerTask(
                self.step_runner,
                config['build'],
            )
            _build_context = {}
            build_image_task.run(_build_context)
            _image = _build_context.get('image', None)

        if 'image' in config:
            _image = config['image']
        assert _image

        self.step_runner.log.write(
            'Creating service container "%s" from image "%s"\n' % (
                name,
                _image,
            )
        )
        service_logger = ContainerLogger.for_service_container(
            self.step_runner.log,
            name,
        )

        # setup custom env variables
        _env = dict(self.step_runner.build_runner.env)

        # do we need to change to a given dir when running
        # a cmd or script?
        _cwd = None
        if 'cwd' in config:
            _cwd = config['cwd']

        # need to expose any ports?
        _ports = None
        if 'ports' in config:
            _ports = config['ports']

        # default to a container that runs the default
        # image command
        _shell = None

        # do we need to run an explicit cmd?
        if 'cmd' in config:
            # if so we need to run the cmd within a default
            # shell--specify it here
            _shell = DEFAULT_SHELL

        # if a shell is specified use it
        if 'shell' in config:
            _shell = config['shell']

        # see if there are any provisioners defined
        _provisioners = None
        if 'provisioners' in config:
            _provisioners = create_provisioners(
                config['provisioners'],
                service_logger,
            )

        # determine if a user is specified
        _user = None
        if 'user' in config:
            _user = config['user']

        # determine if a hostname is specified
        _hostname = None
        if 'hostname' in config:
            _hostname = config['hostname']

        # determine if a dns host is specified
        _dns = None
        if 'dns' in config:
            _dns = config['dns']

        # determine if a dns_search domain is specified
        _dns_search = None
        if 'dns_search' in config:
            _dns_search = config['dns_search']

        # set service specific environment variables
        if 'env' in config:
            for key, value in config['env'].iteritems():
                _env[key] = value

        _volumes_from = [self._get_source_container()]

        # see if we need to map any service container volumes
        if 'volumes_from' in config:
            _volumes_from.extend(self._process_volumes_from(
                config['volumes_from'],
            ))

        _volumes = {
            self.step_runner.build_runner.build_results_dir: \
                ARTIFACTS_VOLUME_MOUNT + ':ro',
        }
        if 'files' in config:
            for f_alias, f_path in config['files'].iteritems():
                # lookup file from alias
                f_local = self.step_runner.build_runner.get_local_files_from_alias( #pylint: disable=line-too-long
                    f_alias,
                )
                if not f_local or not os.path.exists(f_local):
                    raise BuildRunnerConfigurationError(
                        "Cannot find valid local file for alias '%s'" % (
                            f_alias,
                        )
                    )

                if f_path[-3:] not in [':ro', ':rw']:
                    f_path = f_path + ':ro'

                _volumes[f_local] = f_path

                service_logger.write(
                    "Mounting %s -> %s\n" % (f_local, f_path)
                )

        # instantiate and start the runner
        service_runner = DockerRunner(
            _image,
            pull_image=config.get('pull', True),
        )
        self._service_runners[name] = service_runner
        cont_name = self.step_runner.id + '-' + name
        service_container_id = service_runner.start(
            name=cont_name,
            volumes=_volumes,
            volumes_from=_volumes_from,
            ports=_ports,
            links=self._service_links,
            shell=_shell,
            provisioners=_provisioners,
            environment=_env,
            user=_user,
            hostname=_hostname,
            dns=_dns,
            dns_search=_dns_search,
            working_dir=_cwd,
        )
        self._service_links[cont_name] = name

        def attach_to_service():
            """Function to attach to service in a separate thread."""
            # if specified, run a command
            if 'cmd' in config:
                exit_code = service_runner.run(
                    config['cmd'],
                    console=service_logger,
                )
                if exit_code != 0:
                    service_logger.write(
                        'Service command "%s" exited with code %s\n' % (
                            config['cmd'],
                            exit_code,
                        )
                    )
            else:
                service_runner.attach_until_finished(service_logger)
            service_logger.cleanup()

        # Attach to the container in a separate thread
        service_management_thread = threading.Thread(
            name="%s--%s" % (self.step_runner.name, name),
            target=attach_to_service,
        )
        service_management_thread.daemon = True
        service_management_thread.start()

        self.step_runner.log.write(
            'Started service container "%s" (%.10s)\n' % (
                name,
                service_container_id,
            )
        )


    def run(self, context):
        _run_image = self.config.get('image', context.get('image', None))
        if not _run_image:
            raise BuildRunnerConfigurationError(
                'Docker run context must specify a "image" attribute or '
                'be preceded by a build context'
            )

        self.step_runner.log.write(
            'Creating build container from image "%s"\n' % (
                _run_image,
            )
        )
        container_logger = ContainerLogger.for_build_container(
            self.step_runner.log,
            self.step_runner.name,
        )
        container_meta_logger = ContainerLogger.for_build_container(
            self.step_runner.log,
            self.step_runner.name,
        )

        # container defaults
        _source_container = self._get_source_container()
        _container_name = str(uuid.uuid4())
        _env_defaults = dict(self.step_runner.build_runner.env)
        _env_defaults.update({
            'BUILDRUNNER_SOURCE_CONTAINER': _source_container,
            'BUILDRUNNER_BUILD_CONTAINER': _container_name,
        })
        container_args = {
            'name': _container_name,
            'hostname': None,
            'working_dir': SOURCE_VOLUME_MOUNT,
            'shell': None,
            'user': None,
            'provisioners': None,
            'dns': None,
            'dns_search': None,
            'environment': _env_defaults,
            'volumes_from': [_source_container],
            'volumes': {
                self.step_runner.build_runner.build_results_dir: (
                    ARTIFACTS_VOLUME_MOUNT + ':ro'
                ),
            },
        }

        # see if we need to inject ssh keys
        if 'ssh-keys' in self.config:
            _keys = self.step_runner.build_runner.get_ssh_keys_from_aliases(
                self.config['ssh-keys'],
            )
            self._sshagent = DockerSSHAgentProxy(
                self._docker_client,
                self.step_runner.log,
            )
            self._sshagent.start(_keys)

        # start any service containers
        if 'services' in self.config:
            for _name, _config in self.config['services'].iteritems():
                self._start_service_container(_name, _config)

        # determine if there is a command to run
        _cmds = []
        if 'cmd' in self.config:
            container_args['shell'] = DEFAULT_SHELL
            _cmds.append(self.config['cmd'])
        if 'cmds' in self.config:
            container_args['shell'] = DEFAULT_SHELL
            _cmds.extend(self.config['cmds'])

        if 'provisioners' in self.config:
            container_args['shell'] = DEFAULT_SHELL
            container_args['provisioners'] = create_provisioners(
                self.config['provisioners'],
                container_logger,
            )

        # if a shell is specified use it
        if 'shell' in self.config:
            container_args['shell'] = self.config['shell']

        # determine the working dir the build should be run in
        if 'cwd' in self.config:
            container_args['working_dir'] = self.config['cwd']

        # determine if a user is specified
        if 'user' in self.config:
            container_args['user'] = self.config['user']

        # determine if a hostname is specified
        if 'hostname' in self.config:
            container_args['hostname'] = self.config['hostname']

        # determine if a dns host is specified
        if 'dns' in self.config:
            container_args['dns'] = self.config['dns']

        # determine if a dns_search domain is specified
        if 'dns_search' in self.config:
            container_args['dns_search'] = self.config['dns_search']

        # set step specific environment variables
        if 'env' in self.config:
            for key, value in self.config['env'].iteritems():
                container_args['environment'][key] = value

        # see if we need to map any service container volumes
        if 'volumes_from' in self.config:
            container_args['volumes_from'].extend(self._process_volumes_from(
                self.config['volumes_from'],
            ))

        # see if we need to attach to a sshagent container
        if self._sshagent:
            ssh_container, ssh_env = self._sshagent.get_info()
            if ssh_container:
                container_args['volumes_from'].append(ssh_container)
            if ssh_env:
                for _var, _val in ssh_env.iteritems():
                    container_args['environment'][_var] = _val

        # attach the docker daemon container
        self._dockerdaemonproxy = DockerDaemonProxy(
            self._docker_client,
            self.step_runner.log,
        )
        self._dockerdaemonproxy.start()
        daemon_container, daemon_env = self._dockerdaemonproxy.get_info()
        if daemon_container:
            container_args['volumes_from'].append(daemon_container)
        if daemon_env:
            for _var, _val in daemon_env.iteritems():
                container_args['environment'][_var] = _val

        # see if we need to inject any files
        if 'files' in self.config:
            for f_alias, f_path in self.config['files'].iteritems():
                # lookup file from alias
                f_local = self.step_runner.build_runner.get_local_files_from_alias( #pylint: disable=line-too-long
                    f_alias,
                )
                if not f_local or not os.path.exists(f_local):
                    raise BuildRunnerConfigurationError(
                        "Cannot find valid local file for alias '%s'" % (
                            f_alias,
                        )
                    )

                if f_path[-3:] not in [':ro', ':rw']:
                    f_path = f_path + ':ro'

                container_args['volumes'][f_local] = f_path

                container_meta_logger.write(
                    "Mounting %s -> %s\n" % (f_local, f_path)
                )

        # see if we need to mount any caches
        if 'caches' in self.config:
            for cache_name, cache_path in self.config['caches'].iteritems():
                # get the cache location from the main BuildRunner class
                cache_local_path = self.step_runner.build_runner.get_cache_path(
                    cache_name,
                )
                container_args['volumes'][cache_local_path] = cache_path + ':rw'
                container_meta_logger.write(
                    "Mounting cache dir %s -> %s\n" % (cache_name, cache_path)
                )

        exit_code = None
        try:
            # create and start runner, linking any service containers
            self.runner = DockerRunner(
                _run_image,
                pull_image=self.config.get('pull', True),
            )
            container_id = self.runner.start(
                links=self._service_links,
                **container_args
            )
            self.step_runner.log.write(
                'Started build container %.10s\n' % container_id
            )

            if _cmds:
                # run each cmd
                for _cmd in _cmds:
                    container_meta_logger.write(
                        "cmd> %s\n" % _cmd
                    )
                    exit_code = self.runner.run(
                        _cmd,
                        console=container_logger,
                    )
                    container_meta_logger.write(
                        'Command "%s" exited with code %s\n' % (
                            _cmd,
                            exit_code,
                        )
                    )

                    if exit_code != 0:
                        break
            else:
                self.runner.attach_until_finished(container_logger)
                exit_code = self.runner.exit_code
                container_meta_logger.write(
                    'Container exited with code %s\n' % (
                        exit_code,
                    )
                )

        finally:
            if self.runner:
                self.runner.stop()
            if container_logger:
                container_logger.cleanup()
            if container_meta_logger:
                container_meta_logger.cleanup()

        # gather artifacts to results dir even if run has bad exit code
        if 'artifacts' in self.config:
            self._retrieve_artifacts()

        # if we have an unsuccessful exit code abort
        if exit_code != 0:
            raise BuildRunnerProcessingError(
                "Error running build container"
            )

        context['run_runner'] = self.runner

        if 'post-build' in self.config:
            self._run_post_build(context)


    def _run_post_build(self, context):
        """
        Commit the run image and perform a docker build, prepending the run
        image to the Dockerfile.
        """
        self.step_runner.log.write(
            'Running post-build processing\n'
        )
        config = self.config['post-build']
        # post build always uses the image hash--can't pull
        if not is_dict(config):
            config = {'path': config}
        config['pull'] = False
        build_image_task = BuildBuildStepRunnerTask(
            self.step_runner,
            config,
            image_to_prepend_to_dockerfile=self.runner.commit(
                self.step_runner.log,
            )
        )
        _build_context = {}
        build_image_task.run(_build_context)
        context['run-image'] = _build_context.get('image', None)


    def cleanup(self, context): #pylint: disable=unused-argument
        if self.runner:
            if self.runner.container:
                self.step_runner.log.write(
                    'Destroying build container %.10s\n' % (
                        self.runner.container['Id'],
                    )
                )
            self.runner.cleanup()

        if self._service_runners:
            for (_sname, _srun) in reversed(self._service_runners.items()):
                self.step_runner.log.write(
                    'Destroying service container "%s"\n' % _sname
                )
                _srun.cleanup()

        if self._dockerdaemonproxy:
            self._dockerdaemonproxy.stop()

        if self._sshagent:
            self._sshagent.stop()

        if self._source_container:
            self.step_runner.log.write(
                'Destroying source container %.10s\n' % (
                    self._source_container,
                )
            )
            self._docker_client.remove_container(
                self._source_container,
                force=True,
                v=True,
            )
