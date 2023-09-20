"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from typing import Any, Dict, List, Optional, Union

# pylint: disable=no-name-in-module
from pydantic import BaseModel, Field


class StepPypiPush(BaseModel, extra='forbid'):
    """ Step pypi push model"""
    repository: str
    username: str
    password: str


class Artifact(BaseModel):
    """ Artifact model """
    # Intentionally loose restrictions
    format: Optional[str]
    type: Optional[Any]
    compression: Optional[str]
    push: Optional[bool]


class StepBuild(BaseModel, extra='forbid'):
    """ Build model within a step """
    path: Optional[str]
    dockerfile: Optional[str]
    pull: Optional[bool]
    platform: Optional[str]
    platforms: Optional[List[str]]
    inject: Optional[Dict[str, Optional[str]]]
    no_cache: Optional[bool] = Field(alias='no-cache')
    buildargs: Optional[Dict[str, Any]]


class RunAndServicesBase(BaseModel):
    """
    Base model for Run and Service
    which has several common fields
    """
    image: Optional[str]
    cmd: Optional[str]
    # Intentionally loose restrictions
    provisioners: Optional[Dict[str, str]]
    shell: Optional[str]
    cwd: Optional[str]
    user: Optional[str]
    hostname: Optional[str]
    dns: Optional[List[str]]
    dns_search: Optional[str]
    extra_hosts: Optional[Dict[str, str]]
    env: Optional[Dict[str, Optional[str]]]
    files: Optional[Dict[str, str]]
    volumes_from: Optional[List[str]]
    ports: Optional[Dict[int, Optional[Union[int, None]]]]
    pull: Optional[bool]
    systemd: Optional[bool]
    containers: Optional[List[str]]
    caches: Optional[Dict[str, Union[str, List[str]]]]


class Service(RunAndServicesBase, extra='forbid'):
    """ Service model """
    build: Optional[Union[StepBuild, str]]
    wait_for: Optional[List[Any]]
    inject_ssh_agent: Optional[bool] = Field(alias='inject-ssh-agent')
    # Not sure if this is valid, but it is in a test file
    # Didn't use StepRun because of the potential to have a infinitely nested model
    run: Optional[Any]


class StepRun(RunAndServicesBase, extra='forbid'):
    """ Run model within a step """
    xfail: Optional[bool]
    services: Optional[Dict[str, Service]]
    cmds: Optional[List[str]]
    ssh_keys: Optional[List[str]] = Field(alias='ssh-keys')
    artifacts: Optional[Dict[str, Optional[Artifact]]]
    platform: Optional[str]
    cap_add: Optional[Union[str, List[str]]]
    privileged: Optional[bool]
    post_build: Optional[Union[str, Dict[str, Any]]] = Field(alias='post-build')
    no_cache: Optional[bool] = Field(alias='no-cache')


class StepRemote(BaseModel, extra='forbid'):
    """ Remote model within a step """
    # Not sure if host is optional or required
    host: Optional[str]
    cmd: str
    artifacts: Optional[Dict[str, Union[Artifact, None]]]


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
