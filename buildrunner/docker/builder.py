"""
Copyright (C) 2015 Adobe
"""
from __future__ import absolute_import
import json
import re
import tarfile
import tempfile

import docker

from buildrunner.docker import new_client


class DockerBuilder(object):
    """
    An object that manages and orchestrates building a Docker image from
    a Dockerfile.
    """


    def __init__(
            self,
            path=None,
            inject=None,
            dockerd_url=None,
    ):
        self.path = path
        self.inject = inject
        self.docker_client = new_client(
            dockerd_url=dockerd_url,
        )
        self.image = None
        self.intermediate_containers = []


    def build(self, console=None, nocache=False, rm=True):
        """
        Run a docker build using the configured context, constructing the
        context tar file if necessary.
        """
        _path = None
        _custom_context = False
        _fileobj = None

        if self.inject:
            # need to create our own tar file, injecting the appropriate paths
            _custom_context = True
            _fileobj = tempfile.NamedTemporaryFile()
            tfile = tarfile.open(mode='w', fileobj=_fileobj)
            if self.path:
                tfile.add(self.path, arcname='.')
            for to_inject, dest in self.inject.iteritems():
                tfile.add(to_inject, arcname=dest)
            tfile.close()
            _fileobj.seek(0)
        else:
            _path = self.path

        stream = self.docker_client.build(
            path=_path,
            nocache=nocache,
            custom_context=_custom_context,
            fileobj=_fileobj,
            rm=rm,
        )

        # monitor output for logs and status
        exit_code = 0
        for msg_str in stream:
            msg = json.loads(msg_str)
            if 'stream' in msg:
                # capture intermediate containers for cleanup later
                # the command line 'docker build' has a '--force-rm' option,
                # but that isn't available in the python client
                container_match = re.search(
                    r' ---> Running in ([0-9a-f]+)',
                    msg['stream'],
                )
                if container_match:
                    self.intermediate_containers.append(
                        container_match.group(1)
                    )

                # capture the resulting image
                image_match = re.search(
                    r'Successfully built ([0-9a-f]+)',
                    msg['stream'],
                )
                if image_match:
                    self.image = image_match.group(1)

                if console:
                    console.write(msg['stream'])
            if 'error' in msg:
                exit_code = 1
                if 'errorDetail' in msg:
                    if 'message' in msg['errorDetail'] and console:
                        console.write(msg['errorDetail']['message'])
                        console.write('\n')

        return exit_code


    def cleanup(self):
        """
        Cleanup the docker build environment.
        """
        # iterate through and destory intermediate containers
        for container in self.intermediate_containers:
            try:
                self.docker_client.remove_container(
                    container,
                    force=True,
                    v=True,
                )
            except docker.errors.APIError:
                pass
