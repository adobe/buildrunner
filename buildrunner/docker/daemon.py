"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import os

from buildrunner.docker import DOCKER_DEFAULT_DOCKERD_URL


class DockerDaemonProxy:
    """
    Class used to encapsulate Docker daemon information within a container.
    """

    def __init__(self, docker_client, log, docker_registry):
        """
        """
        self.docker_client = docker_client
        self.docker_registry = docker_registry
        self.log = log
        self._daemon_container = None
        self._env = {
            'DOCKER_HOST': DOCKER_DEFAULT_DOCKERD_URL,
        }

    def get_info(self):
        """
        Return a tuple where the first item is the daemon container id and
        the second is a dict of environment variables to be injected into other
        containers providing settings for docker clients to connect to the
        encapsulated daemon.
        """
        return self._daemon_container, self._env

    def start(self):
        """
        Starts a Docker container encapsulating information to connect to the
        current docker daemon.
        """
        _volumes = []
        _binds = {}

        # setup docker env and mounts so that the docker daemon is accessible
        # from within the run container
        for env_name, env_value in os.environ.items():
            if env_name == 'DOCKER_HOST':
                self._env['DOCKER_HOST'] = env_value
            if env_name == 'DOCKER_TLS_VERIFY' and env_value:
                self._env['DOCKER_TLS_VERIFY'] = '1'
            if env_name == 'DOCKER_CERT_PATH':
                if os.path.exists(env_value):
                    _volumes.append('/dockerdaemon/certs')
                    _binds[env_value] = {
                        'bind': '/dockerdaemon/certs',
                        'ro': True,
                    }
                    self._env['DOCKER_CERT_PATH'] = '/dockerdaemon/certs'

        # if DOCKER_HOST is a unix socket we need to mount the socket in the
        # container and adjust the DOCKER_HOST variable accordingly
        docker_host = self._env['DOCKER_HOST']
        if docker_host.startswith('unix://'):
            # need to map the socket as a volume
            local_socket = docker_host.replace('unix://', '')
            if os.path.exists(local_socket):
                _volumes.append('/dockerdaemon/docker.sock')
                _binds[local_socket] = {
                    'bind': '/dockerdaemon/docker.sock',
                    'ro': False,
                }
                self._env['DOCKER_HOST'] = 'unix:///dockerdaemon/docker.sock'

        # create and start the Docker container
        self._daemon_container = self.docker_client.create_container(
            f'{self.docker_registry}/busybox:latest',
            command='/bin/sh',
            volumes=_volumes,
            host_config=self.docker_client.create_host_config(
                binds=_binds
            )
        )['Id']
        self.docker_client.start(self._daemon_container)
        self.log.write(
            f"Created Docker daemon container {self._daemon_container:.10}\n"
        )

    def stop(self):
        """
        Stops the Docker daemon container.
        """
        # kill container
        self.log.write(
            f"Destroying Docker daemon container {self._daemon_container:.10}\n"
        )
        if self._daemon_container:
            self.docker_client.remove_container(
                self._daemon_container,
                force=True,
                v=True,
            )
