"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import os
from typing import Any, Dict, List, Optional, Set, Union

# pylint: disable=no-name-in-module
from pydantic import BaseModel, Field, field_validator, ValidationError

from buildrunner.docker import multiplatform_image_builder
from buildrunner.validation.errors import Errors, get_validation_errors
from buildrunner.validation.step import Step, StepPushCommitDict
from buildrunner.validation.step_images_info import StepImagesInfo

RETAG_ERROR_MESSAGE = "Multi-platform build steps cannot re-tag images. The following images are re-tagged:"


class Config(BaseModel, extra="forbid"):
    """Top level config model"""

    # Unclear if this is actively used
    class GithubModel(BaseModel, extra="forbid"):
        """Github model"""

        endpoint: str
        version: str
        username: str
        app_token: str

    class SSHKey(BaseModel, extra="forbid"):
        """SSH key model"""

        file: Optional[str] = None
        key: Optional[str] = None
        password: Optional[str] = None
        prompt_password: Optional[bool] = Field(alias="prompt-password", default=None)
        aliases: Optional[List[str]] = None

    class DockerBuildCacheConfig(BaseModel, extra="forbid"):
        builders: Optional[List[str]] = None
        from_config: Optional[Union[dict, str]] = Field(None, alias="from")
        to_config: Optional[Union[dict, str]] = Field(None, alias="to")

    version: Optional[float] = None
    steps: Optional[Dict[str, Step]] = None

    github: Optional[Dict[str, GithubModel]] = None
    # Global config attributes
    env: Optional[Dict[str, Any]] = None
    build_servers: Optional[Dict[str, Union[str, List[str]]]] = Field(
        alias="build-servers", default=None
    )
    #  Intentionally has loose restrictions on ssh-keys since documentation isn't clear
    ssh_keys: Optional[Union[SSHKey, List[SSHKey]]] = Field(
        alias="ssh-keys", default=None
    )
    local_files: Optional[Dict[str, str]] = Field(alias="local-files", default=None)
    docker_build_cache: Optional[DockerBuildCacheConfig] = Field(
        None, alias="docker-build-cache"
    )
    caches_root: Optional[str] = Field(alias="caches-root", default=None)
    docker_registry: Optional[str] = Field(alias="docker-registry", default=None)
    temp_dir: Optional[str] = Field(alias="temp-dir", default=None)
    disable_multi_platform: Optional[bool] = Field(
        alias="disable-multi-platform", default=None
    )
    build_registry: Optional[str] = Field(
        alias="build-registry", default=multiplatform_image_builder.LOCAL_REGISTRY
    )
    platform_builders: Optional[Dict[str, str]] = Field(
        alias="platform-builders", default=None
    )

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, vals) -> None:
        """
        Validate the config file

        Raises:
            ValueError | pydantic.ValidationError : If the config file is invalid
        """

        def validate_push(
            push: Union[StepPushCommitDict, str, List[Union[str, StepPushCommitDict]]],
            mp_push_tags: Set[str],
            step_name: str,
            update_mp_push_tags: bool = True,
        ):
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
                        name = f"{name}:latest"

                if isinstance(push, StepPushCommitDict):
                    if not push.tags:
                        name = f"{push.repository}:latest"
                    else:
                        names = [f"{push.repository}:{tag}" for tag in push.tags]

                if names is not None:
                    for current_name in names:
                        if current_name in mp_push_tags:
                            raise ValueError(
                                f"Cannot specify duplicate tag {current_name} in build step {step_name}"
                            )

                if name is not None and name in mp_push_tags:
                    raise ValueError(
                        f"Cannot specify duplicate tag {name} in build step {step_name}"
                    )

                if update_mp_push_tags and names is not None:
                    mp_push_tags.update(names)

                if update_mp_push_tags and name is not None:
                    mp_push_tags.add(name)

        def get_source_image(step: Step) -> Optional[List[str]]:
            """
            Get the source image from the step.build and/or step.run.image

            Args:
                step (Step): Build step

            Returns:
                Optional[str]: Source images
            """
            dockerfile_text = None
            src_image = []
            is_multi_platform = False

            # Gets the source image from build.dockerfile
            if step.build and step.build.dockerfile:
                if os.path.exists(step.build.dockerfile):
                    with open(step.build.dockerfile, "r") as dockerfile:
                        dockerfile_text = dockerfile.read()
                else:
                    # Dockerfile is defined as a string in the config file
                    dockerfile_text = step.build.dockerfile

                if not dockerfile_text:
                    raise ValueError(
                        f"There is an issue with the dockerfile {step.build.dockerfile}"
                    )

                for line in dockerfile_text.splitlines():
                    if line.startswith("FROM"):
                        image_name = line.replace("FROM ", "").strip()
                        if ":" not in image_name:
                            image_name = f"{image_name}:latest"
                        src_image.append(image_name)

                if not src_image:
                    raise ValueError(
                        f"There is an issue with the dockerfile {step.build.dockerfile}"
                    )

            # Get the source image from step.run.image
            if step.run and step.run.image:
                if ":" not in step.run.image:
                    src_image.append(f"{step.run.image}:latest")
                else:
                    src_image.append(step.run.image)

            if step.build and step.build.platforms:
                is_multi_platform = True

            return src_image, is_multi_platform

        def get_destination_images(step: Step) -> Optional[List[str]]:
            """
            Get the destination images from step.push or step.commit

            Args:
                step (Step): Build step

            Returns:
                Optional[List[str]]: List of destination images
            """

            def get_images(
                pushcommmit: Union[
                    StepPushCommitDict, str, List[Union[str, StepPushCommitDict]]
                ],
            ) -> List[str]:
                images = []
                if isinstance(pushcommmit, StepPushCommitDict):
                    if pushcommmit.tags:
                        for tag in pushcommmit.tags:
                            images.append(f"{pushcommmit.repository}:{tag}")
                    else:
                        images.append(f"{pushcommmit.repository}:latest")
                elif isinstance(pushcommmit, str):
                    if ":" not in pushcommmit:
                        images.append(f"{pushcommmit}:latest")
                    else:
                        images.append(pushcommmit)
                elif isinstance(pushcommmit, list):
                    for item in pushcommmit:
                        if isinstance(item, str):
                            images.append(item)
                        elif isinstance(item, StepPushCommitDict):
                            if item.tags:
                                for tag in item.tags:
                                    images.append(f"{item.repository}:{tag}")
                            else:
                                images.append(f"{item.repository}:latest")
                        else:
                            raise ValueError(
                                f"Unknown type for step.push: {type(step.push)}"
                            )
                return images

            images = []
            images.extend(get_images(step.push))
            images.extend(get_images(step.commit))
            return images

        def validate_multiplatform_are_not_retagged():
            """
            Validate multi-platform are not re-tagged

            Args:
                mp_push_tags (Set[str]): Set of all tags used in multi-platform build steps

            Raises:
                ValueError | pydantic.ValidationError: If the config file is invalid
            """
            step_images = {}

            # Iterate through each step and get information about the images
            for step_name, step in vals.items():
                src_image, is_multi_platform = get_source_image(step)
                dst_images = get_destination_images(step)
                step_images[step_name] = StepImagesInfo(
                    source_image=src_image,
                    dest_images=dst_images,
                    is_multi_platform=is_multi_platform,
                )

            # Iterate through each step images and check for multi-platform re-tagging
            retagged_images = []
            for step_name, step_images_info in step_images.items():
                other_steps_images_infos = [
                    curr_step_images_info
                    for curr_step_name, curr_step_images_info in step_images.items()
                    if curr_step_name != step_name
                ]
                for other_step_info in other_steps_images_infos:
                    for src_image in step_images_info.source_image:
                        if (
                            src_image in other_step_info.dest_images
                            and other_step_info.is_multi_platform
                        ):
                            retagged_images.append(src_image)

            if retagged_images:
                raise ValueError(f"{RETAG_ERROR_MESSAGE} {retagged_images}")

        def validate_multi_platform_build(mp_push_tags: Set[str]):
            """
            Validate multi-platform build steps

            Args:
                mp_push_tags (Set[str]): Set of all tags used in multi-platform build steps

            Raises:
                ValueError | pydantic.ValidationError: If the config file is invalid
            """
            # Iterate through each step and validate multi-platform multi-platform steps
            for step_name, step in vals.items():
                if step.is_multi_platform():
                    if step.build.platform is not None:
                        raise ValueError(
                            f"Cannot specify both platform ({step.build.platform}) and "
                            f"platforms ({step.build.platforms}) in build step {step_name}"
                        )

                    if not isinstance(step.build.platforms, list):
                        raise ValueError(
                            f"platforms must be a list in build step {step_name}"
                        )

                    if step.build.cache_from:
                        raise ValueError(
                            f"cache_from is not allowed in multi-platform build step {step_name}"
                        )

                    if step.build.import_param:
                        raise ValueError(
                            f"import is not allowed in multi-platform build step {step_name}"
                        )

                    if step.run:
                        raise ValueError(
                            f"run is not allowed with multi-platform build step {step_name}"
                        )

                    # Check for valid push section, duplicate mp tags are not allowed
                    validate_push(step.push, mp_push_tags, step_name)

            validate_multiplatform_are_not_retagged()

        # Checks to see if there is a mutli-platform build step in the config
        has_multi_platform_build = False
        for step in vals.values():
            has_multi_platform_build = (
                has_multi_platform_build or step.is_multi_platform()
            )

        if has_multi_platform_build:
            mp_push_tags = set()
            validate_multi_platform_build(mp_push_tags)

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
