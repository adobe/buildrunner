"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

# pylint: disable=no-name-in-module
from pydantic import BaseModel, Field


class StepPypiPush(BaseModel):
    """ Step pypi push model"""
    repository: str
    username: str
    password: str


class Artifact(BaseModel):
    """ Artifact model """

    class FormatTypes(Enum):
        """ Format types """
        #  pylint: disable=invalid-name
        uncompressed = 'uncompressed'

    class CompressionTypes(Enum):
        """ Compression types """
        # [compression: gz|bz2|xz|lzma|lzip|lzop|z]
        #  pylint: disable=invalid-name
        gz = 'gz'
        bz2 = 'bz2'
        xz = 'xz'
        lzma = 'lzma'
        lzip = 'lzip'
        lzop = 'lzop'
        z = 'z'

    format: Optional[FormatTypes]
    type: Optional[Any]
    compression: Optional[CompressionTypes]
    push: Optional[bool]


class StepRun(BaseModel, extra='forbid'):
    """ Run model within a step """

    class ProvisionerTypes(Enum):
        """ Provisioner types """
        #  pylint: disable=invalid-name
        shell: str = 'shell'
        salt: str = 'salt'

    xfail: Optional[bool]
    services: Optional[Dict[str, str]]
    image: Optional[str]
    cmd: Optional[str]
    cmds: Optional[List[str]]
    provisioners: Optional[Dict[ProvisionerTypes, str]]
    shell: Optional[str]
    cwd: Optional[str]
    user: Optional[str]
    hostname: Optional[str]
    dns: Optional[List[str]]
    dns_search: Optional[str]
    extra_hosts: Optional[Dict[str, str]]
    env: Optional[Dict[str, str]]
    files: Optional[Dict[str, str]]
    caches: Optional[Dict[str, Union[str, List[str]]]]
    ports: Optional[Dict[str, str]]
    volumes_from: Optional[List[str]]
    ssh_keys: Optional[List[str]] = Field(alias='ssh-keys')
    artifacts: Optional[Dict[str, Union[Artifact, None]]]
    pull: Optional[bool]
    platform: Optional[str]
    systemd: Optional[bool]
    cap_add: Optional[Union[str, List[str]]]
    privileged: Optional[bool]
    post_build: Optional[Union[str, Dict[str, str]]] = Field(alias='post-build')
    containers: Optional[List[str]]


class StepRemote(BaseModel, extra='forbid'):
    """ Remote model within a step """
    # Not sure if host is optional or required
    host: Optional[str]
    cmd: str
    artifacts: Optional[Dict[str, Union[Artifact, None]]]


class StepBuild(BaseModel, extra='forbid'):
    """ Build model within a step """
    path: Optional[str]
    dockerfile: Optional[str]
    pull: Optional[bool]
    platform: Optional[str]
    platforms: Optional[List[str]]
    inject: Optional[Dict[str, str]]


class StepPushCommitDict(BaseModel, extra='forbid'):
    """ Push model within a step """
    repository: str
    tags: Optional[List[str]]


class Step(BaseModel, extra='forbid'):
    """ Step model """
    build: Optional[Union[StepBuild, str]]
    push: Optional[Union[StepPushCommitDict, List[Union[str, StepPushCommitDict]], str]]
    commit: Optional[Union[StepPushCommitDict, List[Union[str, StepPushCommitDict]], str]]
    remote: Optional[StepRemote]
    run: Optional[StepRun]
    depends: Optional[List[str]]
    pypi_push: Optional[Union[StepPypiPush, str]] = Field(alias='pypi-push')

    def is_multi_platform(self):
        """
        Check if the step is a multi-platform build step
        """
        return isinstance(self.build, StepBuild) and \
            self.build.platforms is not None
