"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
import logging
import os
from multiprocessing import Manager, Process
from platform import machine, system
import shutil
import tempfile
import uuid
from typing import Dict, List, Optional

import python_on_whales
from python_on_whales import docker
from retry import retry

from buildrunner.docker import get_dockerfile

logger = logging.getLogger(__name__)


class ImageInfo:
    """Image information repo with associated tags"""
    def __init__(self, repo: str, tags: List[str] = None, platform: str = None, digest: str = None,):
        """
        Args:
            repo (str): The repo name for the image.
            tags (List[str], optional): The tags for the image. Defaults to None.
            platform (str, optional): The platform for the image. Defaults to None.
            digest (str, optional): The digest id for the image. Defaults to None.
        """
        self._repo = repo

        if tags is None:
            self._tags = ["latest"]
        else:
            self._tags = tags

        self._platform = platform
        self._digest = digest

    @property
    def repo(self) -> str:
        """The repo name for the image."""
        return self._repo

    @property
    def tags(self) -> List[str]:
        """The tags for the image."""
        return self._tags

    @property
    def digest(self) -> str:
        """The digest id for the image."""
        return self._digest

    def trunc_digest(self) -> str:
        """The truncated digest id for the image."""
        if self._digest is None:
            return "Digest not available"
        return self._digest.replace("sha256:", "")[:12]

    @property
    def platform(self) -> str:
        """The platform for the image."""
        return self._platform

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


class RegistryInfo:
    """Registry information"""
    def __init__(self, name: str, ip_addr: str, port: int):
        self._name = name
        self._ip_addr = ip_addr
        self._port = port

    @property
    def name(self) -> str:
        """The registry name"""
        return self._name

    @property
    def ip_addr(self) -> str:
        """The registry ip address"""
        return self._ip_addr

    @property
    def port(self) -> int:
        """The registry port"""
        return self._port

    def __str__(self):
        """Returns a string representation of the registry info"""
        return f"{self._name} {self._ip_addr}:{self._port}"

    def __repr__(self):
        """Returns a string representation of the registry info"""
        return self.__str__()


class MultiplatformImageBuilder:  # pylint: disable=too-many-instance-attributes
    """Multiple platform image builder"""

    # pylint: disable=too-many-arguments
    def __init__(
            self,
            docker_registry: Optional[str] = None,
            use_local_registry: bool = True,
            keep_images: bool = False,
            temp_dir: str = os.getcwd(),
            disable_multi_platform: bool = False,
            platform_builders: Optional[Dict[str, str]] = None,
    ):
        self._docker_registry = docker_registry
        self._mp_registry_info = None
        self._use_local_registry = use_local_registry
        self._keep_images = keep_images
        self._temp_dir = temp_dir
        self._disable_multi_platform = disable_multi_platform
        self._platform_builders = platform_builders

        # key is destination image name, value is list of built images
        self._intermediate_built_images = {}
        self._tagged_images_names = {}
        self._local_registry_is_running = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._local_registry_is_running:
            self._stop_local_registry()

        # Removes all intermediate built images
        if self._intermediate_built_images:
            for name, images in self._intermediate_built_images.items():
                for image in images:
                    for tag in image.tags:
                        logger.debug(f"Removing image {image.repo}:{tag} for {name}")
                        docker.image.remove(f"{image.repo}:{tag}", force=True)

        # Removes all tagged images if keep_images is False
        if self._tagged_images_names and not self._keep_images:
            for name, images in self._tagged_images_names.items():
                for image in images:
                    logger.debug(f"Removing tagged image {image} for {name}")
                    docker.image.remove(image, force=True)

    @property
    def disable_multi_platform(self) -> int:
        """Returns the ip address of the local registry"""
        return self._disable_multi_platform

    @property
    def registry_ip(self) -> int:
        """Returns the ip address of the local registry"""
        return self._mp_registry_info.ip_addr

    @property
    def registry_port(self) -> int:
        """Returns the port of the local registry"""
        return self._mp_registry_info.port

    @property
    def tagged_images_names(self) -> List[str]:
        """Returns a list of all the tagged images names"""
        return self._tagged_images_names

    def is_multiplatform(self, name: str) -> bool:
        """Returns True if the image with name is multiplatform"""
        return len(self._intermediate_built_images.get(name, [])) > 0

    def registry_address(self) -> str:
        """Returns the address of the local registry"""
        return f"{self._mp_registry_info.ip_addr}:{self._mp_registry_info.port}"

    def _start_local_registry(self):
        """
        Starts a local docker registry container

        Returns:
            str: The name of the registry container
        """
        if not self._local_registry_is_running:
            logger.debug("Starting local docker registry")
            image = 'registry'
            if self._docker_registry:
                image = f'{self._docker_registry}/{image}'
            container = docker.run(image, detach=True, publish_all=True)
            ports = container.network_settings.ports

            # If any assert fails something changed in the registry image and we need to update this code
            assert len(ports) == 1, \
                f"Expected 1 port, but got {len(ports)}"
            assert isinstance(ports.get("5000/tcp")[0], dict), \
                f"Expected dict, but got {type(ports.get('5000/tcp')[0])}"
            assert ports.get("5000/tcp")[0].get('HostIp') == "0.0.0.0", \
                f"Expected HostIp to be 0.0.0.0 but got {ports.get('5000/tcp')[0].get('HostIp')}"

            self._mp_registry_info = RegistryInfo(container.name, "localhost", ports.get("5000/tcp")[0].get("HostPort"))
            self._local_registry_is_running = True
            logger.debug(f"Started local registry {self._mp_registry_info}")
        else:
            logger.warning("Local registry is already running")

    def _stop_local_registry(self):
        """
        Stops and removes the local registry along with any images
        """
        if self._local_registry_is_running:
            logger.debug(f"Stopping and removing local registry {self._mp_registry_info}")
            try:
                docker.remove(self._mp_registry_info.name, volumes=True, force=True)
            except python_on_whales.exceptions.NoSuchContainer as err:
                logger.error(f"Failed to stop and remove local registry {self._mp_registry_info.name}: {err}")
            self._local_registry_is_running = False
        else:
            logger.warning("Local registry is not running when attempting to stop it")

    # pylint: disable=too-many-arguments,too-many-locals
    def _build_with_inject(
            self,
            inject: dict,
            tagged_names: List[str],
            platform: str,
            path: str,
            file: str,
            build_args: dict,
            builder: Optional[str],
            cache: bool = False,
            cache_from: List[str] = None,
            pull: bool = False,
    ) -> None:

        if not path or not os.path.isdir(path):
            logger.warning(f"Failed to inject {inject} for {tagged_names} since path {path} isn't a directory.")
            return

        dir_prefix = 'mp-tmp-dir'
        with tempfile.TemporaryDirectory(dir=self._temp_dir, prefix=dir_prefix) as tmp_dir:

            context_dir = os.path.join(tmp_dir, f'{dir_prefix}/')
            shutil.copytree(path, context_dir, ignore=shutil.ignore_patterns(dir_prefix, '.git'))

            for src, dest in inject.items():
                src_path = os.path.join(path, src)
                dest_path = os.path.join(context_dir, dest)

                # Check to see if the dest dir exists, if not create it
                dest_dir = os.path.dirname(dest_path)
                if not os.path.isdir(dest_dir):
                    os.mkdir(dest_dir)

                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dest_path)
                else:
                    shutil.copy(src_path, dest_path)

            assert os.path.isdir(context_dir), f"Failed to create context dir {context_dir}"

            docker.buildx.build(
                context_dir,
                tags=tagged_names,
                platforms=[platform],
                load=True,
                file=file,
                builder=builder,
                build_args=build_args,
                cache=cache,
                cache_from=cache_from,
                pull=pull,
            )

    # pylint: disable=too-many-arguments
    @retry(python_on_whales.exceptions.DockerException,
           tries=5,
           delay=1,
           backoff=3,
           max_delay=30,
           logger=logger)
    def _build_single_image(
            self,
            name: str,
            platform: str,
            path: str,
            file: str,
            tags: List[str],
            build_args: dict,
            mp_image_name: str,
            inject: dict,
            cache: bool = False,
            cache_from: List[str] = None,
            pull: bool = False,) -> None:
        """
        Builds a single image for the given platform

        Args:
            name (str): The name of the image
            platform (str): The platform to build the image for (e.g. linux/amd64)
            path (str): The path to the Dockerfile.
            file (str): The path/name of the Dockerfile (ie. <path>/Dockerfile).
            tags (List[str]): The tags to apply to the image.
            build_args (dict): The build args to pass to docker.
            mp_image_name (str): The multi-platform name of the image.
            inject (dict): The files to inject into the build context.
        """
        assert os.path.isdir(path) and os.path.exists(f"{file}"), \
            f"Either path {path}({os.path.isdir(path)}) or file " \
            f"'{file}'({os.path.exists(f'{file}')}) does not exist!"

        tagged_names = [f"{name}:{tag}" for tag in tags]
        builder = self._platform_builders.get(platform) if self._platform_builders else None
        logger.debug(f"Building tagged images {tagged_names}")
        print(f"Building image for platform {platform} with {builder or 'default'} builder")

        if inject and isinstance(inject, dict):
            self._build_with_inject(
                inject=inject,
                tagged_names=tagged_names,
                platform=platform,
                path=path,
                file=file,
                build_args=build_args,
                builder=builder,
                cache=cache,
                cache_from=cache_from,
                pull=pull,
            )
        else:
            docker.buildx.build(
                path,
                tags=tagged_names,
                platforms=[platform],
                load=True,
                file=file,
                build_args=build_args,
                builder=builder,
                cache=cache,
                cache_from=cache_from,
                pull=pull,
            )
        # Push after the initial load to support remote builders that cannot access the local registry
        docker.push(tagged_names)

        # Check that the images were built and in the registry
        # Docker search is not currently implemented in python-on-wheels
        image_id = None
        for tag_name in tagged_names:
            try:
                images = docker.image.pull(tag_name)
                assert images, f"Failed to build {tag_name}"
                image_id = docker.image.inspect(tag_name).id
                # Removes the image from host, if this fails it is considered a warning
                try:
                    logger.debug(f"Removing {tag_name}")
                    docker.image.remove(tag_name, force=True)
                except python_on_whales.exceptions.DockerException as err:
                    logger.warning(f"Failed to remove {images}: {err}")
            except python_on_whales.exceptions.DockerException as err:
                logger.error(f"Failed to build {tag_name}: {err}")
                raise err

        self._intermediate_built_images[mp_image_name].append(ImageInfo(
            repo=name,
            tags=tags,
            platform=platform,
            digest=image_id,
        ))

    def get_single_platform_to_build(self, platforms: List[str]) -> str:
        """ Returns the platform to build for single platform flag """

        assert isinstance(platforms, list), f"Expected list, but got {type(platforms)}"
        assert len(platforms) > 0, f"Expected at least one platform, but got {len(platforms)}"

        host_system = system()
        host_machine = machine()
        native_platform = None

        if host_system in ("Darwin", "linux"):
            native_platform = f"linux/{host_machine}"
        else:
            native_platform = f"{host_system}/{host_machine}"

        for curr_platform in platforms:
            if native_platform in curr_platform:
                return curr_platform

        return platforms[0]

    # pylint: disable=too-many-locals
    def build_multiple_images(
            self,
            platforms: List[str],
            path: str = ".",
            file: str = "Dockerfile",
            mp_image_name: str = None,
            tags: List[str] = None,
            do_multiprocessing: bool = True,
            build_args: dict = None,
            inject: dict = None,
            cache: bool = False,
            cache_from: List[str] = None,
            pull: bool = False,
            ) -> List[ImageInfo]:
        """
        Builds multiple images for the given platforms. One image will be built for each platform.

        Args:
            platforms (List[str]): The platforms to build the image for (e.g. linux/amd64)
            path (str, optional): The path to the Dockerfile. Defaults to ".".
            file (str, optional): The path/name of the Dockerfile (ie. <path>/Dockerfile). Defaults to "Dockerfile".
            mp_image_name (str, optional): The name of the image. Defaults to None.
            tags (List[str], optional): The tags to apply to the image. Defaults to None.
            do_multiprocessing (bool, optional): Whether to use multiprocessing to build the images. Defaults to True.
            build_args (dict, optional): The build args to pass to docker. Defaults to None.
            inject (dict, optional): The files to inject into the build context. Defaults to None.

        Returns:
            List[ImageInfo]: The list of intermediate built images, these images are ephemeral
            and will be removed when the builder is garbage collected
        """
        def get_path(file):
            if os.path.exists(file):
                return os.path.dirname(file)
            return "."

        if build_args is None:
            build_args = {}
        build_args['DOCKER_REGISTRY'] = self._docker_registry

        # It is not valid to pass None for the path when building multi-platform images
        if not path:
            path = get_path(file)

        dockerfile, cleanup_dockerfile = get_dockerfile(file)

        logger.debug(f"Building {mp_image_name}:{tags} for platforms {platforms} from {dockerfile}")

        if self._use_local_registry and not self._local_registry_is_running:
            # Starts local registry container to do ephemeral image storage
            self._start_local_registry()

        if tags is None:
            tags = ["latest"]

        # Updates name to be compatible with docker
        image_prefix = "buildrunner-mp"
        sanitized_name = f"{image_prefix}-{str(uuid.uuid4())}"
        base_image_name = f"{self._mp_registry_info.ip_addr}:{self._mp_registry_info.port}/{sanitized_name}"

        # Keeps track of the built images {name: [ImageInfo(image_names)]]}
        manager = Manager()
        self._intermediate_built_images[mp_image_name] = manager.list()
        line = "-----------------------------------------------------------------"

        if self._disable_multi_platform:
            platforms = [self.get_single_platform_to_build(platforms)]
            print(
                f"{line}\n"
                f"Note: Disabling multi-platform build, "
                "this will only build a single-platform image.\n"
                f"image: {sanitized_name} platform:{platforms[0]}\n"
                f"{line}"
            )
        else:
            print(
                f"{line}\n"
                f"Note: Building multi-platform images can take a long time, please be patient.\n"
                "If you are running this locally, you can speed this up by using the "
                "'--disable-multi-platform' CLI flag "
                "or set the 'disable-multi-platform' flag in the global config file.\n"
                f"{line}"
            )

        processes = []
        print(
            f'Starting builds for {len(platforms)} platforms in {"parallel" if do_multiprocessing else "sequence"}'
        )
        for platform in platforms:
            platform_image_name = f"{base_image_name}-{platform.replace('/', '-')}"
            build_single_image_args = (
                platform_image_name,
                platform,
                path,
                dockerfile,
                tags,
                build_args,
                mp_image_name,
                inject,
                cache,
                cache_from,
                pull,
            )
            logger.debug(f"Building {platform_image_name} for {platform}")
            if do_multiprocessing:
                processes.append(Process(
                    target=self._build_single_image,
                    args=build_single_image_args,
                ))
            else:
                self._build_single_image(*build_single_image_args)

        # Start and join processes in parallel if multiprocessing is enabled
        for proc in processes:
            proc.start()
        for proc in processes:
            proc.join()

        if cleanup_dockerfile and dockerfile and os.path.exists(dockerfile):
            os.remove(dockerfile)

        return self._intermediate_built_images[mp_image_name]

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
        assert len(src_images) > 0, f"No images found for {name}"

        # Append the tags to the names prior to pushing
        if dest_names is None:
            dest_names = name
            # only need get tags for one image, since they should be identical
            for tag in src_images[0].tags:
                tagged_names.append(f"{dest_names}:{tag}")
        else:
            tagged_names = dest_names

        for image in src_images:
            for tag in image.tags:
                src_names.append(f"{image.repo}:{tag}")

        timeout_seconds = initial_timeout_seconds
        while retries > 0:
            retries -= 1
            logger.debug(f"Creating manifest list {name} with timeout {timeout_seconds} seconds")
            curr_process = Process(target=docker.buildx.imagetools.create,
                                   kwargs={"sources": src_names, "tags": tagged_names})
            curr_process.start()
            curr_process.join(timeout_seconds)
            if curr_process.is_alive():
                curr_process.kill()
                if retries == 0:
                    raise TimeoutError(f"Timeout pushing {dest_names} after {retries} retries"
                                       f" and {timeout_seconds} seconds each try")
            else:
                # Process finished within timeout
                logger.info(f"Successfully created multiplatform images {dest_names}")
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
        logger.debug(f"Finding native platform for {name} for {host_os}/{host_arch}")
        pattern = f"{host_os}-{host_arch}"

        # No images built for this name
        if name not in self._intermediate_built_images.keys() \
           or self._intermediate_built_images[name] == []:  # pylint: disable=consider-iterating-dictionary
            return None

        match_platform = [image for image in self._intermediate_built_images[name] if image.repo.endswith(pattern)]

        # No matches found, change os
        if match_platform == []:
            if host_os == "Darwin":
                pattern = f"linux-{host_arch}"
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
            tags (List[str], optional): The tags to load. Defaults to "latest".
            dest_name (str, optional): The name to load the image as. Defaults to the "name" arg.
        """
        # This is to handle pylint's "dangerous-default-value" error
        if tags is None:
            tags = ["latest"]
        logger.debug(f"Tagging {name} with tags {tags} - Dest name: {dest_name}")
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
                    dest_tag = f"{dest_name}:{tag}"
                    docker.tag(image, dest_tag)
                    logger.debug(f"Tagged {image} as {dest_tag}")
                    self._tagged_images_names[name].append(dest_tag)
                docker.image.remove(image, force=True)
            except python_on_whales.exceptions.DockerException as err:
                logger.error(f"Failed while tagging {dest_name}: {err}")
                raise err

    def get_built_images(self, name: str) -> List[str]:
        """
        Returns the list of tagged images for the given name

        Args:
            name (str): The name of the image to find

        Returns:
            List[str]: The list of built images for the given name
        """
        return self._intermediate_built_images[name]
