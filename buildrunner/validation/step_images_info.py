"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
from typing import List


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
