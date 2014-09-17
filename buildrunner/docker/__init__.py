"""
Copyright (C) 2014 Adobe
"""
from __future__ import absolute_import
import docker

from buildrunner import BuildRunnerError


DOCKER_API_VERSION = '1.12'
DOCKER_DEFAULT_DOCKERD_URL = 'unix:///var/run/docker.sock'


class BuildRunnerContainerError(BuildRunnerError):
    """Error indicating an issue managing a Docker container"""
    pass


def new_client(
    dockerd_url=DOCKER_DEFAULT_DOCKERD_URL,
):
    """
    Return a newly configured Docker client.
    """
    return docker.Client(
        base_url=dockerd_url,
        version=DOCKER_API_VERSION,
    )

