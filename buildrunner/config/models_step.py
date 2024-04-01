"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from typing_extensions import Annotated


def _validate_artifact_type(value) -> Any:
    if value and not Artifact.model_validate(value):
        raise ValueError(f"Invalid artifact type: {value}")
    return value


AnnotatedArtifact = Annotated[Any, BeforeValidator(_validate_artifact_type)]


class StepPushSecurityScanConfig(BaseModel, extra="forbid"):
    enabled: Optional[bool] = None
    scanner: Optional[str] = None
    version: Optional[str] = None
    config: Optional[dict] = None
    max_score_threshold: Optional[float] = Field(None, alias="max-score-threshold")


class StepTask(BaseModel, extra="forbid"):
    """
    Used for type checking.
    """


class StepPypiPush(StepTask):
    """Step pypi push model"""

    repository: str
    username: Optional[str] = None
    password: Optional[str] = None
    skip_existing: bool = False


class Artifact(BaseModel):
    """Artifact model"""

    # Intentionally loose restrictions
    format: Optional[str] = None
    type: Optional[Any] = None
    compression: Optional[str] = None
    push: Optional[bool] = None


class StepBuild(StepTask):
    """Build model within a step"""

    path: Optional[str] = None
    dockerfile: Optional[str] = None
    target: Optional[str] = None
    pull: Optional[bool] = None
    platform: Optional[str] = None
    platforms: Optional[List[str]] = None
    inject: Optional[Dict[str, Optional[str]]] = None
    no_cache: Optional[bool] = Field(alias="no-cache", default=None)
    buildargs: Optional[Dict[str, Any]] = None
    cache_from: Optional[List[str]] = None
    # import is a python reserved keyword so we need to alias it
    import_param: Optional[str] = Field(alias="import", default=None)


class RunAndServicesBase(StepTask):
    """
    Base model for Run and Service which has several common fields
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
    ports: Optional[Dict[int, Optional[int]]] = None
    pull: Optional[bool] = None
    systemd: Optional[bool] = None
    containers: Optional[List[str]] = None
    caches: Optional[Dict[str, Union[str, List[str]]]] = None


class Service(RunAndServicesBase):
    build: Optional[StepBuild] = None
    wait_for: Optional[List[Any]] = None
    inject_ssh_agent: Optional[bool] = Field(alias="inject-ssh-agent", default=None)
    # Not sure if this is valid, but it is in a test file
    # Didn't use StepRun because of the potential to have a infinitely nested model
    run: Optional[Any] = None

    @field_validator("build", mode="before")
    @classmethod
    def transform_build(cls, val) -> Optional[dict]:
        if not isinstance(val, str):
            return val
        return {
            "path": val,
        }

    @model_validator(mode="after")
    def validate_image_or_build(self):
        if not self.build and not self.image:
            raise ValueError("Service must specify an image or docker build context")
        if self.build and self.image:
            raise ValueError(
                "Service must specify either an image or docker build context, not both"
            )
        return self


class StepRun(RunAndServicesBase):
    """Run model within a step"""

    xfail: Optional[bool] = None
    services: Optional[Dict[str, Service]] = None
    cmds: Optional[List[str]] = None
    ssh_keys: Optional[List[str]] = Field(alias="ssh-keys", default=None)
    artifacts: Optional[Dict[str, Optional[AnnotatedArtifact]]] = None
    platform: Optional[str] = None
    cap_add: Optional[List[str]] = None
    privileged: Optional[bool] = None
    post_build: Optional[StepBuild] = Field(alias="post-build", default=None)
    no_cache: Optional[bool] = Field(alias="no-cache", default=None)

    @field_validator("post_build", mode="before")
    @classmethod
    def transform_post_build(cls, val) -> Optional[dict]:
        if not isinstance(val, str):
            return val
        return {
            "path": val,
        }

    @field_validator("cap_add", mode="before")
    @classmethod
    def transform_cap_add(cls, val) -> Optional[List[str]]:
        if not isinstance(val, str):
            return val
        return [val]


class StepRemote(StepTask):
    """Remote model within a step"""

    host: str
    cmd: str
    artifacts: Optional[Dict[str, Optional[AnnotatedArtifact]]] = None


class StepPushCommit(StepTask):
    """Push model within a step"""

    repository: str
    add_build_tag: bool = True
    tags: Optional[List[str]] = Field(
        None,
        min_length=1,
    )
    push: bool
    security_scan: Optional[StepPushSecurityScanConfig] = Field(
        None, alias="security-scan"
    )


class Step(BaseModel, extra="forbid"):
    """Step model"""

    # A build specified as a string is handled in the field validator
    build: Optional[StepBuild] = None
    push: Optional[List[StepPushCommit]] = None
    commit: Optional[List[StepPushCommit]] = None
    remote: Optional[StepRemote] = None
    run: Optional[StepRun] = None
    depends: Optional[List[str]] = None
    pypi_push: Optional[StepPypiPush] = Field(alias="pypi-push", default=None)

    @field_validator("build", mode="before")
    @classmethod
    def transform_build(cls, val) -> Optional[dict]:
        if not isinstance(val, str):
            return val
        return {
            "path": val,
        }

    @field_validator("pypi_push", mode="before")
    @classmethod
    def transform_pypi_push(cls, val) -> Optional[dict]:
        if not isinstance(val, str):
            return val
        return {
            "repository": val,
        }

    @field_validator("commit", "push", mode="before")
    @classmethod
    def transform_commit_push(cls, vals, info: ValidationInfo) -> Optional[List[dict]]:
        if not vals:
            return vals
        if not isinstance(vals, list):
            vals = [vals]
        for index, val in enumerate(vals):
            if not val:
                raise ValueError(f"{info.field_name}.{index} must be a valid value")
            if isinstance(val, str):
                vals[index] = {"repository": val}
            # Set the push field dynamically based on the top level field name
            vals[index]["push"] = info.field_name == "push"
        return vals

    def is_multi_platform(self):
        """
        Check if the step is a multi-platform build step
        """
        return self.build and self.build.platforms is not None
