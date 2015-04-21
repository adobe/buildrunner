"""
Copyright (C) 2014 Adobe
"""
from __future__ import absolute_import
import docker
import os
import shutil
import socket
import ssl
import tempfile
import time
import uuid

from buildrunner.docker import (
    new_client,
    BuildRunnerContainerError,
    DOCKER_DEFAULT_DOCKERD_URL,
)


class DockerRunner(object):
    """
    An object that manages and orchestrates the lifecycle and execution of a
    Docker container.
    """


    def __init__(self, image_name, dockerd_url=None, temp_dir=None):
        self.dr_mount = '/dr'

        self.image_name = image_name
        self.docker_client = new_client(
            dockerd_url=dockerd_url,
        )
        self.container = None
        self.path_mappings = None
        self.dr_dir = None

        # check to see if we have the requested image locally and
        # pull it if we don't
        pull_image = True
        for image in self.docker_client.images():
            for tag in image['RepoTags']:
                if tag == self.image_name:
                    pull_image = False
                    break
        if pull_image:
            self.docker_client.pull(self.image_name)

        if temp_dir:
            self.dr_dir = temp_dir
        else:
            self.dr_dir = tempfile.mkdtemp(
                prefix='dr_',
            )


    def start(
        self,
        shell='/bin/sh',
        working_dir=None,
        name=None,
        volumes=None,
        volumes_from=None,
        links=None,
        ports=None,
        provisioners=None,
        environment=None,
        user=None,
        hostname=None,
        dns=None,
        dns_search=None,
    ):
        """
        Kwargs:
          volumes (dict): mount the local dir (key) to the given container
                          path (value)
        """
        if self.container:
            raise BuildRunnerContainerError('Container already started')

        self.path_mappings = {self.dr_dir: self.dr_mount}

        # prepare volumes
        _volumes = [self.dr_mount]
        _binds = {
            self.dr_dir: {
                'bind': self.dr_mount,
                'ro': False,
            },
        }
        if volumes:
            for key, value in volumes.iteritems():
                to_bind = value
                _ro = False
                if to_bind.rfind(':') > 0:
                    tokens = to_bind.rsplit(':', 1)
                    to_bind = tokens[0]
                    _ro = 'ro' == tokens[1]
                _volumes.append(to_bind)
                _binds[key] = {
                    'bind': to_bind,
                    'ro': _ro,
                }
                self.path_mappings[key] = to_bind

        # prepare ports
        _port_list = None
        if ports:
            _port_list = list(ports.keys())

        # start the container
        self.container = self.docker_client.create_container(
            self.image_name,
            name=name,
            command=shell,
            volumes=_volumes,
            ports=_port_list,
            stdin_open=True,
            tty=True,
            environment=environment,
            user=user,
            working_dir=working_dir,
            hostname=hostname,
            dns=dns,
        )
        self.docker_client.start(
            self.container['Id'],
            binds=_binds,
            links=links,
            port_bindings=ports,
            volumes_from=volumes_from,
            dns=dns,
            dns_search=dns_search,
        )

        # run any supplied provisioners
        if provisioners:
            for provisioner in provisioners:
                try:
                    provisioner.provision(self)
                except Exception as ex:
                    self.cleanup()
                    raise ex

        return self.container['Id']


    def stop(self):
        """
        Stop the backing Docker container.
        """
        if self.container:
            self.docker_client.stop(
                self.container['Id'],
            )


    def cleanup(self):
        """
        Cleanup the backing Docker container, stopping it if necessary.
        """
        if self.container:
            self.docker_client.remove_container(
                self.container['Id'],
                force=True,
            )
        self.container = None
        self.path_mappings = None


    def run(self, cmd, cwd=None, console=None):
        """
        Run the given command in the container.
        """
        # generate a unique id for the cmd
        if not self.container:
            raise BuildRunnerContainerError('Container has not been started')

        # create the socket to allow communication
        docksock = self.docker_client.attach_socket(
            self.container['Id'],
            params={
                'logs': 0,
                'stdin': 1,
                'stdout': 0,
                'stderr': 0,
                'stream': 1,
            }
        )

        # check to see if we need to change directories
        if cwd:
            cwd_exit_file = self.tempfile(suffix='.cwdexit')
            cwd_out_file = self.tempfile(suffix='.cwdout')
            container_cwd_exit_file = self.map_local_path(cwd_exit_file)
            container_cwd_out_file = self.map_local_path(cwd_out_file)
            cwd_script = 'cd %s >%s 2>&1; echo "$?" > %s_; mv %s_ %s\n' % (
                cwd,
                container_cwd_out_file,
                container_cwd_exit_file,
                container_cwd_exit_file,
                container_cwd_exit_file,
            )
            docksock.sendall(cwd_script)

            # wait for comfirmation of changed dir
            cwd_exit_code = -1
            while cwd_exit_code < 0:
                time.sleep(0.05)
                if os.path.exists(cwd_exit_file):
                    with open(cwd_exit_file, 'r') as cwd_exit_fd:
                        cwd_exit_code = int(cwd_exit_fd.read())
                    break
            if cwd_exit_code != 0:
                raise BuildRunnerContainerError(
                    'Unable to change directory to "%s"' % cwd
                )

        # send the command
        cmd_exit_file = self.tempfile(suffix='.exit')
        cmd_out_file = self.tempfile(suffix='.out')
        container_cmd_exit_file = self.map_local_path(cmd_exit_file)
        container_cmd_out_file = self.map_local_path(cmd_out_file)
        cmd_script = '%s >%s 2>&1; echo "$?" > %s_; mv %s_ %s\n' % (
            cmd,
            container_cmd_out_file,
            container_cmd_exit_file,
            container_cmd_exit_file,
            container_cmd_exit_file,
        )
        docksock.sendall(cmd_script)
        docksock.close()

        # wait for the command to finish, "tailing" the output file and
        # preparing the output string
        output_scope = {
            'output_file': None,
            'console': console,
        }

        def _tail_output():
            """
            Function to tail the output of the command.
            """
            if not output_scope['output_file'] and os.path.exists(cmd_out_file):
                output_scope['output_file'] = open(cmd_out_file, 'r')
            if output_scope['output_file']:
                while True:
                    where = output_scope['output_file'].tell()
                    line = output_scope['output_file'].readline()
                    if not line:
                        output_scope['output_file'].seek(where)
                        break
                    else:
                        if output_scope['console']:
                            output_scope['console'].write(line)

        while True:
            time.sleep(0.1)
            _tail_output()
            if os.path.exists(cmd_exit_file):
                # we have an exit file--the command is finished, but make sure
                # we've got all the output before closing the out file
                _tail_output()
                if output_scope['output_file']:
                    output_scope['output_file'].close()
                break

        # retrieve the exit code from the exit file
        exit_code = -1
        with open(cmd_exit_file, 'r') as exit_fd:
            exit_code = int(exit_fd.read())

        return exit_code


    def run_script(
        self,
        script,
        args='',
        shell='/bin/sh',
        cwd=None,
        console=None,
    ):
        """
        Run the given script within the container.
        """
        # write temp file with script contents
        script_file = self.tempfile()
        with open(script_file, 'w') as script_fd:
            script_fd.write(script)

        # execute the script
        return self.run(
            '%s %s %s' % (
                shell,
                self.map_local_path(script_file),
                args,
            ),
            cwd=cwd,
            console=console,
        )


    def _get_status(self):
        """
        Return the status dict for the container.
        """
        status = None
        try:
            status = self.docker_client.inspect_container(
                self.container['Id'],
            )
        except docker.errors.APIError:
            pass
        return status


    def is_running(self):
        """
        Return whether the container backed by this Runner is currently
        running.
        """
        status = self._get_status()
        if not status:
            return False
        if 'State' not in status or 'Running' not in status['State']:
            return False
        return status['State']['Running']


    @property
    def exit_code(self):
        """
        Return the exit code of the completed container, or None if it is still
        running.
        """
        status = self._get_status()
        if not status:
            return None
        if 'State' not in status or 'ExitCode' not in status['State']:
            return None
        return status['State']['ExitCode']


    def attach_until_finished(self, stream):
        """
        Attach to the container, writing output to the given log stream until
        the container exits.
        """
        docksock = self.docker_client.attach_socket(
            self.container['Id'],
        )
        docksock.settimeout(1)
        running = True
        while running:
            running = self.is_running()
            try:
                data = docksock.recv(4096)
                while data:
                    stream.write(data)
                    data = docksock.recv(4096)
            except socket.timeout:
                pass
            except ssl.SSLError as ssle:
                if ssle.message != 'The read operation timed out':
                    raise


    def tempfile(self, prefix=None, suffix=None, temp_dir=None):
        """
        Create a temporary file path within the container.
        """
        name = str(uuid.uuid4())
        if suffix:
            name = name + suffix
        if prefix:
            name = prefix + name

        _file = name
        if temp_dir:
            _file = os.path.join(temp_dir, name)
        elif self.dr_dir:
            _file = os.path.join(self.dr_dir, name)

        return _file


    def map_local_path(self, local_path):
        """
        Given a local path, return the path it is mapped to within the
        container (or None if it is not mapped).
        """
        artifacts_path = None
        if self.path_mappings:
            for _local, _container in self.path_mappings.iteritems():
                if local_path.startswith(_local):
                    if _container == '/artifacts':
                        artifacts_path = local_path.replace(
                            _local,
                            _container,
                            1,
                        )
                    else:
                        return local_path.replace(_local, _container, 1)
        return artifacts_path
