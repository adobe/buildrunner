"""
Copyright (C) 2014 Adobe
"""
from __future__ import absolute_import
import docker
import os

from buildrunner import BuildRunnerError


DOCKER_API_VERSION = '1.12'
DOCKER_DEFAULT_DOCKERD_URL = 'unix:///var/run/docker.sock'


class BuildRunnerContainerError(BuildRunnerError):
    """Error indicating an issue managing a Docker container"""
    pass


def new_client(
    dockerd_url=None,
):
    """
    Return a newly configured Docker client.
    """
    _dockerd_url = dockerd_url
    if not _dockerd_url:
        _dockerd_url = os.getenv('DOCKER_HOST', DOCKER_DEFAULT_DOCKERD_URL)
    return docker.Client(
        base_url=_dockerd_url,
        version=DOCKER_API_VERSION,
    )

