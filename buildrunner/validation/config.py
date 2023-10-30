"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from typing import Any, Dict, List, Optional, Set, Union

# pylint: disable=no-name-in-module
from pydantic import BaseModel, Field, field_validator, ValidationError

from buildrunner.validation.errors import Errors, get_validation_errors
from buildrunner.validation.step import Step, StepPushCommitDict


class Config(BaseModel, extra='forbid'):
    """ Top level config model """

    # Unclear if this is actively used
    class GithubModel(BaseModel, extra='forbid'):
        """ Github model """
        endpoint: str
        version: str
        username: str
        app_token: str

    class SSHKey(BaseModel, extra='forbid'):
        """ SSH key model """
        file: Optional[str] = None
        key: Optional[str] = None
        password: Optional[str] = None
        prompt_password: Optional[bool] = Field(alias='prompt-password', default=None)
        aliases: Optional[List[str]] = None

    version: Optional[float] = None
    steps: Optional[Dict[str, Step]] = None

    github: Optional[Dict[str, GithubModel]] = None
    # Global config attributes
    env: Optional[Dict[str, Any]] = None
    build_servers: Optional[Dict[str, Union[str, List[str]]]] = Field(alias='build-servers', default=None)
    #  Intentionally has loose restrictions on ssh-keys since documentation isn't clear
    ssh_keys: Optional[Union[SSHKey, List[SSHKey]]] = Field(alias='ssh-keys', default=None)
    local_files: Optional[Dict[str, str]] = Field(alias='local-files', default=None)
    caches_root: Optional[str] = Field(alias='caches-root', default=None)
    docker_registry: Optional[str] = Field(alias='docker-registry', default=None)
    temp_dir: Optional[str] = Field(alias='temp-dir', default=None)
    disable_multi_platform: Optional[bool] = Field(alias='disable-multi-platform', default=None)

    @field_validator('steps')
    @classmethod
    def validate_steps(cls, vals) -> None:
        """
        Validate the config file

        Raises:
            ValueError | pydantic.ValidationError : If the config file is invalid
        """

        def validate_push(push: Union[StepPushCommitDict, str, List[Union[str, StepPushCommitDict]]],
                          mp_push_tags: Set[str],
                          step_name: str,
                          update_mp_push_tags: bool = True):
            """
            Validate push step

            Args:
                push (StepPushDict | list[str | StepPushDict] | str): Push step
                mp_push_tags (Set[str]): Set of all tags used in multi-platform build steps
                step_name (str): Name of the step
                update_mp_push_tags (bool, optional): Whether to update the set of tags used in multi-platform steps.

            Raises:
                ValueError: If the config file is invalid
            """
            # Check for valid push section, duplicate mp tags are not allowed
            if push is not None:
                name = None
                names = None
                if isinstance(push, str):
                    name = push
                    if ":" not in name:
                        name = f'{name}:latest'

                if isinstance(push, StepPushCommitDict):
                    names = [f"{push.repository}:{tag}" for tag in push.tags]

                if names is not None:
                    for current_name in names:
                        if current_name in mp_push_tags:
                            # raise ValueError(f'Cannot specify duplicate tag {current_name} in build step {step_name}')
                            raise ValueError(f'Cannot specify duplicate tag {current_name} in build step {step_name}')

                if name is not None and name in mp_push_tags:
                    # raise ValueError(f'Cannot specify duplicate tag {name} in build step {step_name}')
                    raise ValueError(f'Cannot specify duplicate tag {name} in build step {step_name}')

                if update_mp_push_tags and names is not None:
                    mp_push_tags.update(names)

                if update_mp_push_tags and name is not None:
                    mp_push_tags.add(name)

        def validate_multi_platform_build(mp_push_tags: Set[str]):
            """
            Validate multi-platform build steps

            Args:
                mp_push_tags (Set[str]): Set of all tags used in multi-platform build steps

            Raises:
                ValueError | pydantic.ValidationError: If the config file is invalid
            """
            # Iterate through each step
            for step_name, step in vals.items():
                if step.is_multi_platform():
                    if step.build.platform is not None:
                        raise ValueError(f'Cannot specify both platform ({step.build.platform}) and '
                                         f'platforms ({step.build.platforms}) in build step {step_name}')

                    if not isinstance(step.build.platforms, list):
                        raise ValueError(f'platforms must be a list in build step {step_name}')

                    # Check for valid push section, duplicate mp tags are not allowed
                    validate_push(step.push, mp_push_tags, step_name)

        has_multi_platform_build = False
        for step in vals.values():
            has_multi_platform_build = has_multi_platform_build or step.is_multi_platform()

        if has_multi_platform_build:
            mp_push_tags = set()
            validate_multi_platform_build(mp_push_tags)

            # Validate that all tags are unique across all multi-platform step
            for step_name, step in vals.items():
                # Check that there are no single platform tags that match multi-platform tags
                if not step.is_multi_platform():
                    if step.push is not None:
                        validate_push(push=step.push,
                                      mp_push_tags=mp_push_tags,
                                      step_name=step_name,
                                      update_mp_push_tags=False)
        return vals


def validate_config(**kwargs) -> Errors:
    """
    Check if the config file is valid

    Raises:
        ValueError | pydantic.ValidationError : If the config file is invalid
    """
    errors = None
    try:
        Config(**kwargs)
    except ValidationError as exc:
        errors = get_validation_errors(exc)
    return errors
