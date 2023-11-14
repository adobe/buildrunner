"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, BeforeValidator, Field
from typing_extensions import Annotated


def _validate_artifact_type(value) -> Any:
    if value and not Artifact.model_validate(value):
        raise ValueError(f'Invalid artifact type: {value}')
    return value


AnnotatedArtifact = Annotated[Any, BeforeValidator(_validate_artifact_type)]


class StepPypiPush(BaseModel, extra='forbid'):
    """ Step pypi push model"""
    repository: str
    username: str
    password: str


class Artifact(BaseModel):
    """ Artifact model """
    # Intentionally loose restrictions
    format: Optional[str] = None
    type: Optional[Any] = None
    compression: Optional[str] = None
    push: Optional[bool] = None


class StepBuild(BaseModel, extra='forbid'):
    """ Build model within a step """
    path: Optional[str] = None
    dockerfile: Optional[str] = None
    pull: Optional[bool] = None
    platform: Optional[str] = None
    platforms: Optional[List[str]] = None
    inject: Optional[Dict[str, Optional[str]]] = None
    no_cache: Optional[bool] = Field(alias='no-cache', default=None)
    buildargs: Optional[Dict[str, Any]] = None
    cache_from: Optional[List[str]] = None
    # import is a python reserved keyword so we need to alias it
    import_param: Optional[str] = Field(alias='import', default=None)


class RunAndServicesBase(BaseModel):
    """
    Base model for Run and Service
    which has several common fields
    """
    image: Optional[str] = None
    cmd: Optional[str] = None
    # Intentionally loose restrictions
    provisioners: Optional[Dict[str, str]] = None
    shell: Optional[str] = None
    cwd: Optional[str] = None
    user: Optional[str] = None
    hostname: Optional[str] = None
    dns: Optional[List[str]] = None
    dns_search: Optional[str] = None
    extra_hosts: Optional[Dict[str, str]] = None
    env: Optional[Dict[str, Optional[Any]]] = None
    files: Optional[Dict[str, str]] = None
    volumes_from: Optional[List[str]] = None
    ports:  Optional[Dict[int, Optional[int]]] = None
    pull: Optional[bool] = None
    systemd: Optional[bool] = None
    containers: Optional[List[str]] = None
    caches: Optional[Dict[str, Union[str, List[str]]]] = None


class Service(RunAndServicesBase, extra='forbid'):
    """ Service model """
    build: Optional[Union[StepBuild, str]] = None
    wait_for: Optional[List[Any]] = None
    inject_ssh_agent: Optional[bool] = Field(alias='inject-ssh-agent', default=None)
    # Not sure if this is valid, but it is in a test file
    # Didn't use StepRun because of the potential to have a infinitely nested model
    run: Optional[Any] = None


class StepRun(RunAndServicesBase, extra='forbid'):
    """ Run model within a step """
    xfail: Optional[bool] = None
    services: Optional[Dict[str, Service]] = None
    cmds: Optional[List[str]] = None
    ssh_keys: Optional[List[str]] = Field(alias='ssh-keys', default=None)
    artifacts: Optional[Dict[str, Optional[AnnotatedArtifact]]] = None
    platform: Optional[str] = None
    cap_add: Optional[Union[str, List[str]]] = None
    privileged: Optional[bool] = None
    post_build: Optional[Union[str, Dict[str, Any]]] = Field(alias='post-build', default=None)
    no_cache: Optional[bool] = Field(alias='no-cache', default=None)


class StepRemote(BaseModel, extra='forbid'):
    """ Remote model within a step """
    # Not sure if host is optional or required
    host: Optional[str] = None
    cmd: str
    artifacts: Optional[Dict[str, Optional[AnnotatedArtifact]]] = None


class StepPushCommitDict(BaseModel, extra='forbid'):
    """ Push model within a step """
    repository: str
    tags: Optional[List[str]] = None


class Step(BaseModel, extra='forbid'):
    """ Step model """
    build: Optional[Union[StepBuild, str]] = None
    push: Optional[Union[StepPushCommitDict, List[Union[str, StepPushCommitDict]], str]] = None
    commit: Optional[Union[StepPushCommitDict, List[Union[str, StepPushCommitDict]], str]] = None
    remote: Optional[StepRemote] = None
    run: Optional[StepRun] = None
    depends: Optional[List[str]] = None
    pypi_push: Optional[Union[StepPypiPush, str]] = Field(alias='pypi-push', default=None)

    def is_multi_platform(self):
        """
        Check if the step is a multi-platform build step
        """
        return isinstance(self.build, StepBuild) and \
            self.build.platforms is not None
