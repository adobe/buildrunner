"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import os
import tempfile
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, field_validator, ValidationError

from .models_step import Step, StepPushSecurityScanConfig
from .validation import (
    get_validation_errors,
    validate_multiplatform_build,
    validate_multiplatform_are_not_retagged,
    validate_push,
)


DEFAULT_CACHES_ROOT = "~/.buildrunner/caches"
# Marker for using the local registry instead of an upstream registry
MP_LOCAL_REGISTRY = "local"


class GithubModel(BaseModel, extra="forbid"):
    endpoint: str
    version: str
    username: str = os.getenv("USER", os.getenv("LOGNAME"))
    app_token: str = ""


class SSHKey(BaseModel, extra="forbid"):
    file: Optional[str] = None
    key: Optional[str] = None
    password: Optional[str] = None
    prompt_password: Optional[bool] = Field(alias="prompt-password", default=None)
    aliases: Optional[List[str]] = None


class DockerBuildCacheConfig(BaseModel, extra="forbid"):
    builders: Optional[List[str]] = None
    from_config: Optional[Union[dict, str]] = Field(None, alias="from")
    to_config: Optional[Union[dict, str]] = Field(None, alias="to")


class GlobalSecurityScanConfig(BaseModel, extra="forbid"):
    """
    The global config version of security scan configuration has default values.
    """

    enabled: bool = False
    scanner: str = "trivy"
    version: str = "latest"
    # The local cache directory for the scanner (used if supported by the scanner)
    cache_dir: Optional[str] = Field(None, alias="cache-dir")
    config: dict = {
        "timeout": "20m",
        # Do not error on vulnerabilities by default
        "exit-code": 0,
    }
    max_score_threshold: Optional[float] = Field(None, alias="max-score-threshold")

    def merge_scan_config(
        self, push_config: Optional[StepPushSecurityScanConfig]
    ) -> "GlobalSecurityScanConfig":
        """
        Merges the push security scanning config with the global security config
        and returns a merged config without modifying the global configuration.
        :param push_config: the step push security scan config
        :return: a merged scan config
        """
        if not push_config:
            return self
        new_model = {
            field: getattr(push_config, field)
            for field, value in self.model_fields.items()
            if getattr(push_config, field, None) is not None
        }
        # model_copy does not handle actually copying the config dict, so copy this manually and update with
        # the step config once the model copy is done
        config_value = new_model.pop("config", None)
        new_model["config"] = deepcopy(self.config)
        cloned_config = self.model_copy(update=new_model)
        if config_value:
            cloned_config.config.update(config_value)
        return cloned_config


class GlobalConfig(BaseModel, extra="forbid"):
    """Top level global config model"""

    github: Optional[Dict[str, GithubModel]] = None
    env: Optional[Dict[str, Any]] = None
    build_servers: Optional[Dict[str, List[str]]] = Field(
        alias="build-servers", default=None
    )
    ssh_keys: Optional[List[SSHKey]] = Field(alias="ssh-keys", default=None)
    local_files: Optional[Dict[str, str]] = Field(alias="local-files", default=None)
    docker_build_cache: Optional[DockerBuildCacheConfig] = Field(
        alias="docker-build-cache", default=DockerBuildCacheConfig()
    )
    caches_root: Optional[str] = Field(alias="caches-root", default=DEFAULT_CACHES_ROOT)
    # Default to docker.io if none is configured
    docker_registry: Optional[str] = Field(alias="docker-registry", default="docker.io")
    """
    Get temp dir in the following priorities:
    * Environment variable
    * Global configuration property
    * Configured system temp directory
    """
    temp_dir: Optional[str] = Field(
        alias="temp-dir",
        default=os.getenv("BUILDRUNNER_TEMPDIR", tempfile.gettempdir()),
    )
    disable_multi_platform: Optional[bool] = Field(
        alias="disable-multi-platform", default=None
    )
    build_registry: Optional[str] = Field(
        alias="build-registry", default=MP_LOCAL_REGISTRY
    )
    platform_builders: Optional[Dict[str, str]] = Field(
        alias="platform-builders", default=None
    )
    security_scan: GlobalSecurityScanConfig = Field(
        GlobalSecurityScanConfig(), alias="security-scan"
    )

    @field_validator("ssh_keys", mode="before")
    @classmethod
    def transform_ssh_keys(cls, val) -> Optional[List[dict]]:
        if not isinstance(val, dict):
            return val
        return [val]


class Config(BaseModel, extra="forbid"):
    """Top level config model"""

    version: Optional[float] = None
    steps: Dict[str, Step]

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, vals) -> None:
        """
        Validate the config file

        Raises:
            ValueError : If the config file is invalid
        """

        if not vals:
            raise ValueError('The "steps" configuration was not provided')

        # Checks to see if there is a mutli-platform build step in the config
        has_multi_platform_build = False
        for step in vals.values():
            has_multi_platform_build = (
                has_multi_platform_build or step.is_multi_platform()
            )

        if has_multi_platform_build:
            mp_push_tags = set()
            validate_multiplatform_build(vals, mp_push_tags)
            validate_multiplatform_are_not_retagged(vals)

            # Validate that all tags are unique across all multi-platform step
            for step_name, step in vals.items():
                # Check that there are no single platform tags that match multi-platform tags
                if not step.is_multi_platform():
                    if step.push is not None:
                        validate_push(
                            push=step.push,
                            mp_push_tags=mp_push_tags,
                            step_name=step_name,
                            update_mp_push_tags=False,
                        )
        return vals


def generate_and_validate_config(
    **kwargs,
) -> Tuple[Optional[Config], Optional[List[str]]]:
    try:
        return Config(**kwargs), None
    except ValidationError as exc:
        return None, get_validation_errors(exc)


def generate_and_validate_global_config(
    **kwargs,
) -> Tuple[Optional[GlobalConfig], Optional[List[str]]]:
    try:
        return GlobalConfig(**kwargs), None
    except ValidationError as exc:
        return None, get_validation_errors(exc)
