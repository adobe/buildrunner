"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
import logging
import os
from multiprocessing import Process
from platform import machine, system
from typing import List

import python_on_whales
from python_on_whales import docker

LOGGER = logging.getLogger(__name__)


class ImageInfo:
    """Image information repo with associated tags"""
    def __init__(self, repo: str, tags: List[str] = None):
        self._repo = repo

        if tags is None:
            self._tags = ['latest']
        else:
            self._tags = tags

    @property
    def repo(self) -> str:
        """The repo name for the image."""
        return self._repo

    @property
    def tags(self) -> List[str]:
        """The tags for the image."""
        return self._tags

    def formatted_list(self) -> List[str]:
        """Returns a list of formatted image names"""
        return [f"{self._repo}:{tag}" for tag in self._tags]

    def __str__(self):
        """Returns a string representation of the image info"""
        if len(self._tags) == 1:
            return f"{self._repo}:{self._tags[0]}"
        return f"{self._repo} tags={self._tags}"

    def __repr__(self):
        """Returns a string representation of the image info"""
        return self.__str__()


class MultiplatformImageBuilder:
    """Multiple platform image builder"""

    def __init__(self,
                 use_local_registry: bool = True,
                 keep_images: bool = False,):
        self._reg_name = None
        self._reg_ip = None
        self._reg_port = None
        self._use_local_registry = use_local_registry
        self._keep_images = keep_images

        # key is destination image name, value is list of built images
        self._intermediate_built_images = {}
        self._tagged_images_names = {}

    def __enter__(self):
        # Starts local registry container to do ephemeral image storage
        if self._use_local_registry:
            self._start_local_registry()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._use_local_registry:
            self._stop_local_registry()

        # Removes all intermediate built images
        if self._intermediate_built_images:
            for name, images in self._intermediate_built_images.items():
                for image in images:
                    for tag in image.tags:
                        LOGGER.debug(f"Removing image {image.repo}:{tag} for {name}")
                        docker.image.remove(f'{image.repo}:{tag}', force=True)

        # Removes all tagged images if keep_images is False
        if self._tagged_images_names and not self._keep_images:
            for name, images in self._tagged_images_names.items():
                for image in images:
                    LOGGER.debug(f"Removing tagged image {image} for {name}")
                    docker.image.remove(image, force=True)

    @property
    def registry_ip(self) -> int:
        """Returns the ip address of the local registry"""
        return self._reg_ip

    @property
    def registry_port(self) -> int:
        """Returns the port of the local registry"""
        return self._reg_port

    @property
    def tagged_images_names(self) -> List[str]:
        """Returns a list of all the tagged images names"""
        return self._tagged_images_names

    def is_multiplatform(self, name: str) -> bool:
        """Returns True if the image with name is multiplatform"""
        return len(self._intermediate_built_images.get(name, [])) > 0

    def registry_address(self) -> str:
        """Returns the address of the local registry"""
        return f"{self._reg_ip}:{self._reg_port}"

    def _start_local_registry(self):
        """
        Starts a local docker registry container

        Returns:
            str: The name of the registry container
        """
        LOGGER.debug("Starting local docker registry")
        container = docker.run("registry", detach=True, publish_all=True)
        ports = container.network_settings.ports

        # Something changed in the registry image, so we need to update this code
        assert len(ports) == 1, \
            f"Expected 1 port, but got {len(ports)}"
        assert isinstance(ports.get('5000/tcp')[0], dict), \
            f"Expected dict, but got {type(ports.get('5000/tcp')[0])}"
        assert ports.get('5000/tcp')[0].get('HostIp') == '0.0.0.0', \
            f"Expected HostIp to be 0.0.0.0 but got {ports.get('5000/tcp')[0].get('HostIp')}"

        self._reg_ip = 'localhost'
        self._reg_port = ports.get('5000/tcp')[0].get('HostPort')
        self._reg_name = container.name
        LOGGER.debug(f"Started local registry {self._reg_name} at {self._reg_ip}:{self._reg_port}")

    def _stop_local_registry(self):
        """
        Stops and removes the local registry along with any images
        """
        LOGGER.debug(f"Stopping and removing local registry {self._reg_name} at {self._reg_ip}:{self._reg_port}")
        docker.stop(self._reg_name)
        docker.remove(self._reg_name, volumes=True, force=True)

    # pylint: disable=too-many-arguments
    def build_image(self,
                    name: str,
                    platform: str,
                    push: bool = True,
                    path: str = '.',
                    file: str = 'Dockerfile',
                    tags: List[str] = None,) -> None:
        """
        Builds the image for the given platform

        Args:
            name (str): The name of the image
            platform (str): The platform to build the image for (e.g. linux/amd64)
            push (bool, optional): Whether to push the image to the registry. Defaults to True.
            path (str, optional): The path to the Dockerfile. Defaults to '.'.
            file (str, optional): The path/name of the Dockerfile (ie. <path>/Dockerfile). Defaults to 'Dockerfile'.
            tags (List[str], optional): The tags to apply to the image. Defaults to None.
        """
        if tags is None:
            tags = ['latest']

        assert os.path.isdir(path) and os.path.exists(f'{file}'), \
            f"Either path {path}({os.path.isdir(path)}) or file " \
            "'{file}'({os.path.exists(f'{file}')}) does not exist!"

        tagged_names = [f'{name}:{tag}' for tag in tags]
        LOGGER.debug(f"Building {tagged_names} for {platform}")

        # Build the image with the specified tags
        image = docker.buildx.build(path, tags=tagged_names, platforms=[platform], push=push, file=file)

        # Check that the images were built and in the registry
        # Docker search is not currently implemented in python-on-wheels
        for tag_name in tagged_names:
            try:
                images = docker.image.pull(tag_name)
                assert images, f"Failed to build {tag_name}"
                docker.image.remove(images, force=True)
            except python_on_whales.exceptions.DockerException as err:
                LOGGER.error(f"Failed to build {tag_name}: {err}")
                raise err
        return image

    def build(self,
              platforms: List[str],
              path: str = '.',
              file: str = 'Dockerfile',
              name: str = None,
              tags: List[str] = None,
              push=True,
              do_multiprocessing: bool = False) -> List[ImageInfo]:
        """
        Builds the images for the given platforms

        Args:
            platforms (List[str]): The platforms to build the image for (e.g. linux/amd64)
            path (str, optional): The path to the Dockerfile. Defaults to '.'.
            file (str, optional): The path/name of the Dockerfile (ie. <path>/Dockerfile). Defaults to 'Dockerfile'.
            name (str, optional): The name of the image. Defaults to None.
            tags (List[str], optional): The tags to apply to the image. Defaults to None.
            push (bool, optional): Whether to push the image to the registry. Defaults to True.
            do_multiprocessing (bool, optional): Whether to use multiprocessing to build the images. Defaults to False.

        Returns:
            List[ImageInfo]: The list of intermediate built images, these images are ephemeral
            and will be removed when the builder is garbage collected
        """
        LOGGER.debug(f"Building {name}:{tags} for platforms {platforms} from {file}")

        if tags is None:
            tags = ['latest']

        # Updates name to be compatible with docker
        image_prefix = 'buildrunner-mp'
        santized_name = f"{image_prefix}-{name.replace('/', '-').replace(':', '-')}"
        base_image_name = f"{self._reg_ip}:{self._reg_port}/{santized_name}"

        # Keeps track of the built images {name: [ImageInfo(image_names)]]}
        self._intermediate_built_images[name] = []

        processes = []
        for platform in platforms:
            curr_name = f"{base_image_name}-{platform.replace('/', '-')}"
            LOGGER.debug(f"Building {curr_name} for {platform}")
            if do_multiprocessing:
                processes.append(Process(target=self.build_image, args=(curr_name, platform, push, path, file, tags)))
            else:
                self.build_image(curr_name, platform, push, path, file, tags)
            self._intermediate_built_images[name].append(ImageInfo(curr_name, tags))

        for proc in processes:
            proc.start()

        for proc in processes:
            proc.join()

        return self._intermediate_built_images[name]

    def push(self, name: str, dest_names: List[str] = None) -> None:
        """
        Pushes the image to the remote registry embedded in dest_names or name if dest_names is None

        Args:
            name (str): The name of the image to push
            dest_names (List[str], optional): The names of the images to push to. Defaults to None.

        Raises:
            TimeoutError: If the image fails to push within the specified timeout and retries
        """
        tagged_names = []
        src_names = []

        # Parameters for timeout and retries
        initial_timeout_seconds = 60
        timeout_step_seconds = 60
        timeout_max_seconds = 600
        retries = 5

        src_images = self._intermediate_built_images[name]
        # only need get tags for one image, since they should be identical
        assert len(src_images) > 0, f"No images found for {name}"

        # Append the tags to the names prior to pushing
        if dest_names is None:
            dest_names = name
            for tag in src_images[0].tags:
                tagged_names.append(f'{dest_names}:{tag}')
        else:
            tagged_names = dest_names

        for image in src_images:
            for tag in image.tags:
                src_names.append(f'{image.repo}:{tag}')

        timeout_seconds = initial_timeout_seconds
        while retries > 0:
            retries -= 1
            LOGGER.debug(f"Creating manifest list {name} with timeout {timeout_seconds} seconds")
            curr_process = Process(target=docker.buildx.imagetools.create,
                                   kwargs={"sources": src_names, "tags": tagged_names})
            curr_process.start()
            curr_process.join(timeout_seconds)
            if curr_process.is_alive():
                curr_process.kill()
                if retries == 0:
                    raise TimeoutError(f"Timeout pushing {dest_names} after {retries} retries"
                                       " and {timeout_seconds} seconds each try")
            else:
                # Process finished within timeout
                LOGGER.info(f"Successfully created multiplatform images {dest_names}")
                break
            timeout_seconds += timeout_step_seconds

            # Cap timeout at max timeout
            timeout_seconds = min(timeout_seconds, timeout_max_seconds)
        return tagged_names

    def _find_native_platform_images(self, name: str) -> str:
        """
        Returns the built native platform image(s) for the given name

        Args:
            name (str): The name of the image to find

        Returns:
            str: The name of the native platform image
        """
        host_os = system()
        host_arch = machine()
        LOGGER.debug(f"Finding native platform for {name} for {host_os}/{host_arch}")
        pattern = f'{host_os}-{host_arch}'

        # No images built for this name
        if name not in self._intermediate_built_images.keys() \
           or self._intermediate_built_images[name] == []:  # pylint: disable=consider-iterating-dictionary
            return None

        match_platform = [image for image in self._intermediate_built_images[name] if image.repo.endswith(pattern)]

        # No matches found, change os
        if match_platform == []:
            if host_os == 'Darwin':
                pattern = f'linux-{host_arch}'
            match_platform = [image for image in self._intermediate_built_images[name] if image.repo.endswith(pattern)]

        assert len(match_platform) <= 1, f"Found more than one match for {name} and {pattern}: {match_platform}"

        # Still no matches found, get the first image
        if match_platform == []:
            return self._intermediate_built_images[name][0]

        return match_platform[0]

    def tag_single_platform(self, name: str, tags: List[str] = None,  dest_name: str = None) -> None:
        """
        Loads a single platform image into the host registry. If a matching image to the native platform
        is not found, then the first image is loaded.

        Args:
            name (str): The name of the image to load
            tags (List[str], optional): The tags to load. Defaults to 'latest'.
            dest_name (str, optional): The name to load the image as. Defaults to the 'name' arg.
        """
        # This is to handle pylint's "dangerous-default-value" error
        if tags is None:
            tags = ['latest']
        LOGGER.debug(f'Tagging {name} with tags {tags} - Dest name: {dest_name}')
        source_image = self._find_native_platform_images(name)
        if dest_name is None:
            dest_name = name

        if self._tagged_images_names.get(name) is None:
            self._tagged_images_names[name] = []

        # Tags all the source images with the dest_name and tags
        # Then removes the intermediate source images
        for image in source_image.formatted_list():
            try:
                docker.pull(image)
                for tag in tags:
                    dest_tag = f'{dest_name}:{tag}'
                    docker.tag(image, dest_tag)
                    LOGGER.debug(f"Tagged {image} as {dest_tag}")
                    self._tagged_images_names[name].append(dest_tag)
                docker.image.remove(image, force=True)
            except python_on_whales.exceptions.DockerException as err:
                LOGGER.error(f"Failed while tagging {dest_name}: {err}")
                raise err
