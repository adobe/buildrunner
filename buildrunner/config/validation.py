"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import os
from typing import Dict, List, Optional, Set, Union

from pydantic import ValidationError

from .models_step import Step, StepPushCommit


RETAG_ERROR_MESSAGE = "Multi-platform build steps cannot re-tag images. The following images are re-tagged:"
RUN_MP_ERROR_MESSAGE = "run is not allowed in the same step as a multi-platform build"
BUILD_MP_CACHE_ERROR_MESSAGE = (
    "cache_from must be a dict or list(dict) in the multi-platform build step"
)


class StepImagesInfo:
    def __init__(
        self, source_image: str, dest_images: List[str], is_multi_platform: bool
    ) -> None:
        self._is_multi_platform = is_multi_platform
        self._source_image = source_image
        self._dest_images = dest_images

    @property
    def is_multi_platform(self) -> bool:
        return self._is_multi_platform

    @property
    def source_image(self) -> str:
        return self._source_image

    @property
    def dest_images(self) -> list:
        return self._dest_images


def get_validation_errors(exc: ValidationError) -> List[str]:
    """Get validation errors to an Errors object"""
    errors = []
    for error in exc.errors():
        field = ".".join(str(item) for item in error["loc"])
        if error["type"] == "value_error.extra":
            errors.append(
                f"  {field}:  not a valid field, please check the spelling and documentation"
            )
        else:
            errors.append(f"  {field}:  {error['msg']} ({error['type']})")
    return errors


def validate_push(
    push: List[Union[str, StepPushCommit]],
    mp_push_tags: Set[str],
    step_name: str,
    update_mp_push_tags: bool = True,
) -> None:
    """
    Validate push step to ensure duplicate MP image tags are not used.

    Args:
        push (List[StepPushDict]): Push step
        mp_push_tags (Set[str]): Set of all tags used in multi-platform build steps
        step_name (str): Name of the step
        update_mp_push_tags (bool, optional): Whether to update the set of tags used in multi-platform steps.

    Raises:
        ValueError: If the config file is invalid
    """
    if not push:
        return
    for push_config in push:
        if not push_config.tags:
            tags = [push_config.repository]
        else:
            tags = [f"{push_config.repository}:{tag}" for tag in push_config.tags]
        for tag in tags:
            if tag in mp_push_tags:
                raise ValueError(
                    f"Cannot specify duplicate tag {tag} in build step {step_name}"
                )
            if update_mp_push_tags:
                mp_push_tags.add(tag)


def _get_base_image_from_dockerfile(dockerfile: str) -> str:
    """
    Get the base image from a dockerfile

    Args:
        dockerfile (str): Dockerfile

    Returns:
        str: Base image
    """
    dockerfile_text = None
    src_image = None
    if dockerfile:
        if os.path.exists(dockerfile):
            with open(dockerfile, "r") as file:
                dockerfile_text = file.read()
        else:
            # Dockerfile is defined as a string in the config file
            dockerfile_text = dockerfile

    if not isinstance(dockerfile_text, str):
        raise ValueError(f"There is an issue with the dockerfile {dockerfile}")

    for line in dockerfile_text.lower().strip().splitlines():
        if line.startswith("from"):
            image_name = line.replace("from", "").strip()
            if ":" not in image_name:
                image_name = f"{image_name}:latest"
            src_image = image_name

    if not src_image:
        raise ValueError(f"There is an issue with the dockerfile {dockerfile}")

    return src_image.lower()


def _get_source_image(step: Step) -> str:
    """
    Get the source image from the step.build or step.run.image

    Args:
        step (Step): Build step

    Returns:
        Optional[str]: source image
    """

    src_image = None

    # Gets the source image from build.dockerfile
    if step.build:
        dockerfile = step.build.dockerfile
        if not dockerfile and step.build.path:
            dockerfile = f"{step.build.path}/Dockerfile"
        src_image = _get_base_image_from_dockerfile(dockerfile)

    # Get the source image from step.run.image if build.dockerfile is not defined
    elif step.run and step.run.image:
        src_image = step.run.image
        if ":" not in src_image:
            src_image = f"{src_image}:latest"

    return src_image


def _get_destination_images(step: Step) -> List[str]:
    """
    Get the destination images from step.push or step.commit

    Args:
        step (Step): Build step

    Returns:
        List[str]: List of destination images
    """

    def _get_images(
        push_commit: List[StepPushCommit],
    ) -> List[str]:
        if not push_commit:
            return []
        current_images = []
        for item in push_commit:
            if item.tags:
                for tag in item.tags:
                    current_images.append(f"{item.repository}:{tag}")
            else:
                current_images.append(item.repository)
        return current_images

    images = _get_images(step.push)
    images.extend(_get_images(step.commit))
    return images


def validate_multiplatform_are_not_retagged(steps: Dict[str, Step]):
    """
    Validate multi-platform are not re-tagged

    Raises:
        ValueError: If the config file is invalid
    """
    step_images = {}

    # Iterate through each step and get information about the images
    for step_name, step in steps.items():
        source_image = _get_source_image(step)
        dest_images = _get_destination_images(step)
        step_images[step_name] = StepImagesInfo(
            source_image=source_image,
            dest_images=dest_images,
            is_multi_platform=step.is_multi_platform(),
        )

    # Iterate through each step images and check for multi-platform re-tagging
    retagged_images = []
    for step_name, step_images_info in step_images.items():
        if (
            # Ignore steps that do not push images
            not step_images_info.dest_images
            # Ignore steps that are also multi-platform, as re-tagging will work in this case
            or step_images_info.is_multi_platform
        ):
            continue

        other_steps_images_infos = [
            curr_step_images_info
            for curr_step_name, curr_step_images_info in step_images.items()
            if curr_step_name != step_name
        ]
        for other_step_info in other_steps_images_infos:
            if (
                step_images_info.source_image in other_step_info.dest_images
                and other_step_info.is_multi_platform
            ):
                retagged_images.append(step_images_info.source_image)

    if retagged_images:
        raise ValueError(f"{RETAG_ERROR_MESSAGE} {retagged_images}")


def validate_multiplatform_build(
    steps: Optional[Dict[str, Step]], mp_push_tags: Set[str]
):
    """
    Validate multi-platform build steps

    Args:
        steps (Optional[Dict[str]]): The steps to validate
        mp_push_tags (Set[str]): Set of all tags used in multi-platform build steps

    Raises:
        ValueError: If the config file is invalid
    """
    # Iterate through each step and validate multi-platform multi-platform steps
    for step_name, step in steps.items():
        if step.is_multi_platform():
            if step.build.platform is not None:
                raise ValueError(
                    f"Cannot specify both platform ({step.build.platform}) and "
                    f"platforms ({step.build.platforms}) in build step {step_name}"
                )

            if not isinstance(step.build.platforms, list):
                raise ValueError(f"platforms must be a list in build step {step_name}")

            if (
                step.build.platforms
                and isinstance(step.build.cache_from, list)
                and all(isinstance(x, str) for x in step.build.cache_from)
            ):
                raise ValueError(
                    f"{BUILD_MP_CACHE_ERROR_MESSAGE} {step_name} cannot be a list(str) for multiplatform images {type(step.build.cache_from)}]"
                )

            if step.build.import_param:
                raise ValueError(
                    f"import is not allowed in multi-platform build step {step_name}"
                )

            if step.run:
                raise ValueError(f"{RUN_MP_ERROR_MESSAGE} step {step_name}")

            # Check for valid push section, duplicate mp tags are not allowed
            validate_push(step.push, mp_push_tags, step_name)
