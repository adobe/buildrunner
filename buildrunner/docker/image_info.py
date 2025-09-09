"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import logging
import platform as python_platform
from typing import Dict, List, Optional

from pydantic import BaseModel


LOGGER = logging.getLogger(__name__)

# Maps from lower-case platform.system() result to platform prefix in docker
PLATFORM_SYSTEM_MAPPINGS = {"darwin": "linux"}
PLATFORM_MACHINE_MAPPINGS = {
    "aarch64": "arm",
    "x86_64": "amd",
}


class TaggedImageInfo(BaseModel):
    # The image repo with no tag (e.g. repo/image-name)
    repo: str
    # All tags for this image
    tags: List[str]

    @property
    def image_refs(self) -> List[str]:
        """Returns a list of image names with tags"""
        return [f"{self.repo}:{tag}" for tag in self.tags]

    def __str__(self) -> str:
        return f"{self.repo}:{','.join(self.tags)}"


class BuiltTaggedImage(BaseModel):
    # The image repo with no tag (e.g. repo/image-name)
    repo: str
    # The single tag for this image
    tag: str
    # Digest for the image
    digest: str
    # Platform for the image
    platform: str

    @property
    def trunc_digest(self) -> str:
        return self.digest.replace("sha256:", "")[:12]

    @property
    def image_ref(self) -> str:
        """Returns an image name with the tag"""
        return f"{self.repo}:{self.tag}"


class BuiltImageInfo(BaseModel):
    """
    Contains information about images created during the build,
    including the final tagged image name and any tags (once generated).
    """

    # A unique ID for this built image
    id: str
    # The built images by each platform
    images_by_platform: Dict[str, BuiltTaggedImage] = {}
    # The images that should be created from the built images referenced in each instance
    tagged_images: List[TaggedImageInfo] = []

    @property
    def platforms(self) -> List[str]:
        return list(self.images_by_platform.keys())

    @property
    def built_images(self) -> List[BuiltTaggedImage]:
        return list(self.images_by_platform.values())

    def image_for_platform(self, platform: str) -> Optional[BuiltTaggedImage]:
        """Retrieves the built image for the given platform."""
        return self.images_by_platform.get(platform)

    def add_platform_image(self, platform: str, image_info: BuiltTaggedImage) -> None:
        if platform in self.images_by_platform:
            raise ValueError(
                f"Cannot add image {image_info} for platform {platform} since it already exists in this built image info"
            )
        self.images_by_platform[platform] = image_info

    def add_tagged_image(self, repo: str, tags: List[str]) -> TaggedImageInfo:
        """
        Creates a tagged image instance, adds it to the final image tags, then returns it.
        :arg repo: The image repo without the tag
        :arg tags: The tags to use when tagging the image
        """
        tagged_image = TaggedImageInfo(
            repo=repo,
            tags=tags,
        )
        self.tagged_images.append(tagged_image)
        return tagged_image

    @property
    def native_platform_image(self) -> BuiltTaggedImage:
        """
        Returns the built native platform image(s) matching the current machine's platform or the first built
        image if none matches.

        Args:
            name (str): The name of the image to find

        Returns:
            str: The name of the native platform image
        """
        # Converts the python platform results to docker-equivalents, and then matches based on the prefix
        # e.g. Darwin/aarch64 would become linux/arm which would then match linux/arm64/v7, etc
        native_system = python_platform.system().lower()
        native_machine = python_platform.machine()
        native_system = PLATFORM_SYSTEM_MAPPINGS.get(native_system, native_system)
        native_machine = PLATFORM_MACHINE_MAPPINGS.get(native_machine, native_machine)
        LOGGER.debug(
            f"Finding native platform for {self} for {native_system}/{native_machine}"
        )

        # Search for the image matching the native platform
        # Uses dash since this is matching on tag names which do not support forward slashes
        pattern = f"{native_system}-{native_machine}"
        matched_image = None
        for image in self.images_by_platform.values():
            if image.tag.replace(f"{self.id}-", "").startswith(pattern):
                matched_image = image

        # Still no matches found, get the first image and log a warning
        if not matched_image:
            platform = self.platforms[0]
            LOGGER.warning(
                f"Could not find image matching native platform {pattern} for {self}, using platform {platform} instead locally"
            )
            return self.images_by_platform[platform]

        return matched_image

    def __str__(self):
        num_platforms = len(self.platforms)
        if num_platforms == 0:
            return f"<{self.id}>"
        elif num_platforms == 1:
            return f"<{self.images_by_platform[self.platforms[0]]} ({self.id})>"
        image_strs = [
            f"{platform}: {image}"
            for platform, image in self.images_by_platform.items()
        ]
        return f"<{', '.join(image_strs)} ({self.id})>"

    def __repr__(self):
        return self.__str__()
