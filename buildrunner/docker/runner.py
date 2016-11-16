"""
Copyright (C) 2015 Adobe
"""
from __future__ import absolute_import
import base64
import socket
import ssl

import docker
import six

from docker.utils import compare_version

from buildrunner.docker import (
    new_client,
    BuildRunnerContainerError,
)
from buildrunner.utils import tempfile

class DockerRunner(object):
    """
    An object that manages and orchestrates the lifecycle and execution of a
    Docker container.
    """


    def __init__(self, image_name, dockerd_url=None, pull_image=True):
        self.image_name = image_name
        self.docker_client = new_client(
            dockerd_url=dockerd_url,
        )
        self.container = None
        self.shell = None
        self.committed_image = None
        self.containers = []

        # By default, pull the image.  If the pull_image parameter is
        # set to False, only pull the image if it can't be found locally
        found_image = False
        for image in self.docker_client.images():
            for tag in image['RepoTags'] or []:
                if tag == self.image_name:
                    found_image = True
                    break

        if pull_image or not found_image:
            self.docker_client.pull(self.image_name)


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
            containers=None,
    ): #pylint: disable=too-many-arguments
        """
        Kwargs:
          volumes (dict): mount the local dir (key) to the given container
                          path (value)
        """
        if self.container:
            raise BuildRunnerContainerError('Container already started')
        self.shell = shell

        # save any spawned containers
        if containers:
            self.containers = containers

        # prepare volumes
        _volumes = []
        _binds = {}
        if volumes:
            for key, value in volumes.iteritems():
                to_bind = value
                _ro = False
                if to_bind.rfind(':') > 0:
                    tokens = to_bind.rsplit(':', 1)
                    to_bind = tokens[0]
                    _ro = tokens[1] == 'ro'
                _volumes.append(to_bind)
                _binds[key] = {
                    'bind': to_bind,
                    'ro': _ro,
                }

        # prepare ports
        _port_list = None
        if ports:
            _port_list = list(ports.keys())

        # check args
        if dns_search and isinstance(dns_search, six.string_types):
            dns_search = dns_search.split(',')

        create_dns = dns
        if compare_version('1.10', self.docker_client.api_version) >= 0:
            create_dns = None

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
            dns=create_dns,
            host_config=docker.utils.create_host_config(binds=_binds),
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
                timeout=0,
            )


    def cleanup(self):
        """
        Cleanup the backing Docker container, stopping it if necessary.
        """
        if self.container:
            self.docker_client.remove_container(
                self.container['Id'],
                force=True,
                v=True,
            )
            for c in self.containers:
                try:
                    self.docker_client.remove_container(
                        c,
                        force=True,
                        v=True,
                    )
                except docker.errors.NotFound, e:
                    print str(e)

        self.container = None


    def run(self, cmd, console=None, stream=True):
        """
        Run the given command in the container.
        """
        if not self.container:
            raise BuildRunnerContainerError('Container has not been started')
        if not self.shell:
            raise BuildRunnerContainerError(
                'Cannot call run if container cmd not shell'
            )

        create_res = self.docker_client.exec_create(
            self.container['Id'],
            [self.shell, '-c', cmd],
            tty=True,
        )
        output_buffer = self.docker_client.exec_start(
            create_res,
            stream=stream,
        )
        for line in output_buffer:
            if console:
                console.write(line)
        inspect_res = self.docker_client.exec_inspect(create_res)
        if 'ExitCode' in inspect_res:
            return inspect_res['ExitCode']
        raise BuildRunnerContainerError('Error running cmd: no exit code')


    def run_script(
            self,
            script,
            args='',
            console=None,
    ):
        """
        Run the given script within the container.
        """
        # write temp file with script contents
        script_file_path = tempfile()
        self.run('mkdir -p $(dirname %s)' % script_file_path, console=console)
        self.write_to_container_file(script, script_file_path)
        self.run('chmod +x %s' % script_file_path, console=console)

        # execute the script
        return self.run(
            '%s %s' % (
                script_file_path,
                args,
            ),
            console=console,
        )


    def write_to_container_file(self, content, path):
        """
        Writes contents to the given path within the container.
        """
        # for now, we just take a str
        buf_size = 1024
        for index in range(0, len(content), buf_size):
            self.run(
                'printf -- "%s" | base64 --decode >> %s' % (
                    base64.standard_b64encode(content[index:index + buf_size]),
                    path,
                ),
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


    def commit(self, stream):
        """
        Commit the ending state of the container as an image, returning the
        image id.
        """
        if self.committed_image:
            return self.committed_image
        if not self.container:
            raise BuildRunnerContainerError('Container not started')
        if self.is_running():
            raise BuildRunnerContainerError('Container is still running')
        stream.write(
            'Committing build container %.10s as an image...\n' % (
                self.container['Id'],
            )
        )
        self.committed_image = self.docker_client.commit(
            self.container['Id'],
        )['Id']
        stream.write(
            'Resulting build container image: %.10s\n' % (
                self.committed_image,
            )
        )
        return self.committed_image
