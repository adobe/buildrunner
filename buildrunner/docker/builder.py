"""
Copyright (C) 2015 Adobe
"""
from __future__ import absolute_import
import json
import os
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
            dockerfile=None,
            dockerd_url=None,
            timeout=None,
    ):
        self.path = path
        self.inject = inject
        self.dockerfile = None
        self.cleanup_dockerfile = False
        if dockerfile:
            if os.path.exists(dockerfile):
                self.dockerfile = dockerfile
            else:
                df_file = tempfile.NamedTemporaryFile(delete=False)
                try:
                    df_file.write(dockerfile)
                    self.cleanup_dockerfile = True
                    self.dockerfile = df_file.name
                finally:
                    df_file.close()

        self.docker_client = new_client(
            dockerd_url=dockerd_url,
            timeout=timeout,
        )
        self.image = None
        self.intermediate_containers = []


    def build(self, console=None, nocache=False, cache_from=[], rm=True, pull=True, buildargs={}):
        """
        Run a docker build using the configured context, constructing the
        context tar file if necessary.
        """
        # create our own tar file, injecting the appropriate paths
        _fileobj = tempfile.NamedTemporaryFile()
        tfile = tarfile.open(mode='w', fileobj=_fileobj)
        if self.path:
            tfile.add(self.path, arcname='.')
        if self.inject:
            for to_inject, dest in self.inject.iteritems():
                tfile.add(to_inject, arcname=dest)
        if self.dockerfile:
            tfile.add(self.dockerfile, arcname='./Dockerfile')
        tfile.close()
        _fileobj.seek(0)

        stream = self.docker_client.build(
            path=None,
            nocache=nocache,
            cache_from=cache_from,
            custom_context=True,
            fileobj=_fileobj,
            rm=rm,
            pull=pull,
            buildargs=buildargs
        )

        # monitor output for logs and status
        exit_code = 0
        msg_buffer = ''
        for msg_str in stream:
            for msg in msg_str.split("\n"):
                if msg:
                    msg_buffer += msg
                    try:
                        # there is a limit on the chars returned in the stream
                        # generator, so if we don't have a valid json message
                        # here we get the next msg and append to the current
                        # one
                        json_msg = json.loads(msg_buffer)
                        msg_buffer = ''
                    except ValueError:
                        continue
                    if 'stream' in json_msg:
                        # capture intermediate containers for cleanup later
                        # the command line 'docker build' has a '--force-rm' option,
                        # but that isn't available in the python client
                        container_match = re.search(
                            r' ---> Running in ([0-9a-f]+)',
                            json_msg['stream'],
                        )
                        if container_match:
                            self.intermediate_containers.append(
                                container_match.group(1)
                            )

                        # capture the resulting image
                        image_match = re.search(
                            r'Successfully built ([0-9a-f]+)',
                            json_msg['stream'],
                        )
                        if image_match:
                            self.image = image_match.group(1)

                        if console:
                            console.write(json_msg['stream'])
                    if 'error' in json_msg:
                        exit_code = 1
                        if 'errorDetail' in json_msg:
                            if 'message' in json_msg['errorDetail'] and console:
                                console.write(json_msg['errorDetail']['message'])
                                console.write('\n')

        return exit_code


    def cleanup(self):
        """
        Cleanup the docker build environment.
        """
        # cleanup the generated dockerfile if present
        if self.cleanup_dockerfile:
            if self.dockerfile and os.path.exists(self.dockerfile):
                os.remove(self.dockerfile)

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
