"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
import logging
import os
import platform as python_platform
import re
import shutil
import tempfile
import uuid
from multiprocessing import Process, SimpleQueue
from typing import Dict, List, Optional, Union

import python_on_whales
import timeout_decorator
from python_on_whales import docker
from retry import retry

from buildrunner.config import BuildRunnerConfig
from buildrunner.config.models import MP_LOCAL_REGISTRY
from buildrunner.docker import get_dockerfile
from buildrunner.docker.image_info import BuiltImageInfo, BuiltTaggedImage
from buildrunner.errors import BuildRunnerConfigurationError


LOGGER = logging.getLogger(__name__)
OUTPUT_LINE = "-----------------------------------------------------------------"
IMAGE_PREFIX = "buildrunner-mp"

PUSH_TIMEOUT = 300


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
        build_registry: Optional[str] = MP_LOCAL_REGISTRY,
        temp_dir: str = os.getcwd(),
        platform_builders: Optional[Dict[str, str]] = None,
        cache_builders: Optional[List[str]] = None,
        cache_from: Optional[Union[dict, str]] = None,
        cache_to: Optional[Union[dict, str]] = None,
    ):
        self._docker_registry = docker_registry
        self._build_registry = build_registry
        self._use_local_registry = build_registry == MP_LOCAL_REGISTRY
        self._temp_dir = temp_dir
        self._platform_builders = platform_builders
        self._cache_builders = set(cache_builders if cache_builders else [])
        self._cache_from = cache_from
        self._cache_to = cache_to
        if self._cache_from or self._cache_to:
            LOGGER.info(
                f'Configuring multiplatform builds to cache from {cache_from} and to {cache_to} '
                f'for builders {", ".join(cache_builders) if cache_builders else "(all)"}'
            )

        self._built_images: List[BuiltImageInfo] = []
        self._local_registry_is_running = False
        self._mp_registry_info = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._local_registry_is_running:
            self._stop_local_registry()

    def set_cache_from(self, cache_from):
        self._cache_from = cache_from

    def set_cache_to(self, cache_to):
        self._cache_to = cache_to

    def _build_registry_address(self) -> str:
        """Returns the address of the local registry"""
        if self._build_registry == MP_LOCAL_REGISTRY:
            return f"{self._mp_registry_info.ip_addr}:{self._mp_registry_info.port}"
        return self._build_registry

    def _start_local_registry(self):
        """
        Starts a local docker registry container

        Returns:
            str: The name of the registry container
        """
        if not self._local_registry_is_running:
            if os.getenv("BUILDRUNNER_CONTAINER"):
                raise BuildRunnerConfigurationError(
                    "Multiplatform builds cannot be used in the buildrunner Docker image without "
                    "a 'build-registry' configured in the global buildrunner configuration."
                )

            LOGGER.debug("Starting local docker registry")
            image = "registry"
            if self._docker_registry:
                image = f"{self._docker_registry}/{image}"
            container = docker.run(image, detach=True, publish_all=True)
            ports = container.network_settings.ports

            # If any assert fails something changed in the registry image and we need to update this code
            assert len(ports) == 1, f"Expected 1 port, but got {len(ports)}"
            assert isinstance(
                ports.get("5000/tcp")[0], dict
            ), f"Expected dict, but got {type(ports.get('5000/tcp')[0])}"
            assert (
                ports.get("5000/tcp")[0].get("HostIp") == "0.0.0.0"
            ), f"Expected HostIp to be 0.0.0.0 but got {ports.get('5000/tcp')[0].get('HostIp')}"

            self._mp_registry_info = RegistryInfo(
                container.name, "localhost", ports.get("5000/tcp")[0].get("HostPort")
            )
            self._local_registry_is_running = True
            LOGGER.debug(f"Started local registry {self._mp_registry_info}")
        else:
            LOGGER.warning("Local registry is already running")

    def _stop_local_registry(self):
        """
        Stops and removes the local registry along with any images
        """
        if self._local_registry_is_running:
            LOGGER.debug(
                f"Stopping and removing local registry {self._mp_registry_info}"
            )
            try:
                docker.remove(self._mp_registry_info.name, volumes=True, force=True)
            except python_on_whales.exceptions.NoSuchContainer as err:
                LOGGER.error(
                    f"Failed to stop and remove local registry {self._mp_registry_info.name}: {err}"
                )
            self._local_registry_is_running = False
        else:
            LOGGER.warning("Local registry is not running when attempting to stop it")

    def _get_build_cache_options(self, builder: Optional[str]) -> dict:
        cache_options = {
            "cache_from": self._cache_from,
            "cache_to": self._cache_to,
        }
        # If there are no configured cache builders, always return the cache options
        if not self._cache_builders:
            return cache_options

        # If there are cache builders configured, make sure the current builder is in it
        actual_builder = builder or "default"
        return cache_options if actual_builder in self._cache_builders else {}

    # pylint: disable=too-many-arguments,too-many-locals
    def _build_with_inject(
        self,
        inject: dict,
        image_ref: str,
        platform: str,
        path: str,
        dockerfile: str,
        target: str,
        build_args: dict,
        builder: Optional[str],
        cache: bool = False,
        pull: bool = False,
    ) -> None:
        if not path or not os.path.isdir(path):
            LOGGER.warning(
                f"Failed to inject {inject} for {image_ref} since path {path} isn't a directory."
            )
            return

        dir_prefix = "mp-tmp-dir"
        with tempfile.TemporaryDirectory(
            dir=self._temp_dir, prefix=dir_prefix
        ) as tmp_dir:
            context_dir = os.path.join(tmp_dir, f"{dir_prefix}/")
            shutil.copytree(
                path, context_dir, ignore=shutil.ignore_patterns(dir_prefix, ".git")
            )

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

            assert os.path.isdir(
                context_dir
            ), f"Failed to create context dir {context_dir}"

            docker.buildx.build(
                context_dir,
                tags=[image_ref],
                platforms=[platform],
                load=True,
                file=dockerfile,
                target=target,
                builder=builder,
                build_args=build_args,
                cache=cache,
                pull=pull,
                **self._get_build_cache_options(builder),
            )

    @staticmethod
    def _get_image_digest(image_ref: str) -> str:
        return docker.buildx.imagetools.inspect(image_ref).config.digest

    # pylint: disable=too-many-arguments
    @retry(
        python_on_whales.exceptions.DockerException,
        tries=5,
        delay=1,
        backoff=3,
        max_delay=30,
        logger=LOGGER,
    )
    def _build_single_image(
        self,
        queue: SimpleQueue,
        image_ref: str,
        platform: str,
        path: str,
        dockerfile: str,
        target: str,
        build_args: dict,
        inject: dict,
        cache: bool = False,
        pull: bool = False,
    ) -> None:
        """
        Builds a single image for the given platform.

        Args:
            queue (SimpleQueue): The queue to put the message digest on
            image_ref (str): The image ref for the new image
            platform (str): The platform to build the image for (e.g. linux/amd64)
            path (str): The path to the Dockerfile.
            dockerfile (str): The path/name of the Dockerfile (i.e. <path>/Dockerfile).
            target (str): The name of the stage to build in a multi-stage Dockerfile
            build_args (dict): The build args to pass to docker.
            inject (dict): The files to inject into the build context.
        """
        assert os.path.isdir(path) and os.path.exists(dockerfile), (
            f"Either path {path} ({os.path.isdir(path)}) or file "
            f"'{dockerfile}' ({os.path.exists(dockerfile)}) does not exist!"
        )

        builder = (
            self._platform_builders.get(platform) if self._platform_builders else None
        )
        LOGGER.debug(f"Building image {image_ref} for platform {platform}")
        LOGGER.info(
            f"Building image for platform {platform} with {builder or 'default'} builder"
        )

        if inject and isinstance(inject, dict):
            self._build_with_inject(
                inject=inject,
                image_ref=image_ref,
                platform=platform,
                path=path,
                dockerfile=dockerfile,
                target=target,
                build_args=build_args,
                builder=builder,
                cache=cache,
                pull=pull,
            )
        else:
            docker.buildx.build(
                path,
                tags=[image_ref],
                platforms=[platform],
                load=True,
                file=dockerfile,
                target=target,
                build_args=build_args,
                builder=builder,
                cache=cache,
                pull=pull,
                **self._get_build_cache_options(builder),
            )
        # Push after the initial load to support remote builders that cannot access the local registry
        docker.push([image_ref])

        # Retrieve the digest and put it on the queue
        image_digest = self._get_image_digest(image_ref)
        queue.put((image_ref, image_digest))

    @staticmethod
    def get_native_platform():
        """
        Retrieves the native platform for the current machine or a name that is similar
        to the native platform used by Docker.
        """
        host_system = python_platform.system()
        host_machine = python_platform.machine()

        if host_system.lower() in ("darwin", "linux"):
            host_system = "linux"
        if host_machine.lower() == "x86_64":
            host_machine = "amd64"
        elif host_machine.lower() == "aarch64":
            host_machine = "arm64"
        return f"{host_system}/{host_machine}"

    def _get_single_platform_to_build(self, platforms: List[str]) -> str:
        """Returns the platform to build for single platform flag"""

        assert isinstance(platforms, list), f"Expected list, but got {type(platforms)}"
        assert (
            len(platforms) > 0
        ), f"Expected at least one platform, but got {len(platforms)}"

        native_platform = self.get_native_platform()

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
        target: Optional[str] = None,
        do_multiprocessing: bool = True,
        build_args: dict = None,
        inject: dict = None,
        cache: bool = False,
        pull: bool = False,
    ) -> BuiltImageInfo:
        """
        Builds multiple images for the given platforms. One image will be built for each platform.

        :arg platforms: The platforms to build the image for (e.g. linux/amd64)
        :arg path: The path to the Dockerfile. Defaults to ".".
        :arg file: The path/name of the Dockerfile (i.e. <path>/Dockerfile). Defaults to "Dockerfile".
        :arg do_multiprocessing: Whether to use multiprocessing to build the images. Defaults to True.
        :arg build_args: The build args to pass to docker. Defaults to None.
        :arg inject: The files to inject into the build context. Defaults to None.
        :arg cache: If true, enables cache, defaults to False
        :arg pull: If true, pulls image before build, defaults to False
        :return: A BuiltImageInfo instance that describes the built images for each platform and can be used to track
                 final images as well
        """
        if build_args is None:
            build_args = {}
        build_args["DOCKER_REGISTRY"] = self._docker_registry

        # It is not valid to pass None for the path when building multi-platform images
        if not path:
            if os.path.exists(file):
                path = os.path.dirname(file)
            else:
                path = "."

        dockerfile, cleanup_dockerfile = get_dockerfile(file)

        # Track this newly built image
        built_image = BuiltImageInfo(id=str(uuid.uuid4()))
        self._built_images.append(built_image)

        LOGGER.debug(
            f"Building multi-platform images {built_image} for platforms {platforms} from {dockerfile}"
        )

        if self._use_local_registry and not self._local_registry_is_running:
            # Starts local registry container to do ephemeral image storage
            self._start_local_registry()

        # Uses the current node name as the repo
        if python_platform.node():
            sanitized_name = f"{IMAGE_PREFIX}-{re.sub(r'[^a-zA-Z0-9]', '', python_platform.node()).lower()}"
        else:
            sanitized_name = f"{IMAGE_PREFIX}-unknown-node"
        repo = f"{self._build_registry_address()}/{sanitized_name}"

        if BuildRunnerConfig.get_instance().global_config.disable_multi_platform:
            platforms = [self._get_single_platform_to_build(platforms)]
            LOGGER.info(OUTPUT_LINE)
            LOGGER.info(
                "Note: Disabling multi-platform build, this will only build a single-platform image."
            )
            LOGGER.info(f"image: {repo} platform:{platforms[0]}")
            LOGGER.info(OUTPUT_LINE)
        else:
            LOGGER.info(OUTPUT_LINE)
            LOGGER.info(
                "Note: Building multi-platform images can take a long time, please be patient."
            )
            LOGGER.info(
                "If you are running this locally, you can speed this up by using the '--disable-multi-platform' "
                "CLI flag or set the 'disable-multi-platform' flag in the global config file."
            )
            LOGGER.info(OUTPUT_LINE)

        processes = []
        LOGGER.info(
            f'Starting builds for {len(platforms)} platforms in {"parallel" if do_multiprocessing else "sequence"}'
        )

        # Since multiprocessing may be used, use a simple queue to communicate with the build method
        # This queue receives tuples of (image_ref, image_digest)
        image_info_by_image_ref = {}
        queue = SimpleQueue()
        for platform in platforms:
            tag = f"{built_image.id}-{platform.replace('/', '-')}"
            image_ref = f"{repo}:{tag}"
            # Contains all fields needed for the BuiltTaggedImage instance except digest, which will be added later
            image_info_by_image_ref[image_ref] = {
                "repo": repo,
                "tag": tag,
                "platform": platform,
            }
            build_single_image_args = (
                queue,
                image_ref,
                platform,
                path,
                dockerfile,
                target,
                build_args,
                inject,
                cache,
                pull,
            )
            LOGGER.debug(f"Building {repo} for {platform}")
            if do_multiprocessing:
                processes.append(
                    Process(
                        target=self._build_single_image,
                        args=build_single_image_args,
                    )
                )
            else:
                self._build_single_image(*build_single_image_args)

        # Start and join processes in parallel if multiprocessing is enabled
        for proc in processes:
            proc.start()
        for proc in processes:
            proc.join()

        while not queue.empty():
            image_ref, image_digest = queue.get()
            assert (
                image_ref in image_info_by_image_ref
            ), f"Image ref {image_ref} is missing in generated info"
            image_info = image_info_by_image_ref.pop(image_ref)
            built_image.add_platform_image(
                image_info.get("platform"),
                BuiltTaggedImage(
                    **image_info,
                    digest=image_digest,
                ),
            )
        assert not image_info_by_image_ref, f"Image refs were not generated successfully, unclaimed refs: {image_info_by_image_ref}"

        if cleanup_dockerfile and dockerfile and os.path.exists(dockerfile):
            os.remove(dockerfile)

        return built_image

    @timeout_decorator.timeout(PUSH_TIMEOUT)
    def _push_with_timeout(self, src_names: List[str], tag_names: List[str]) -> None:
        """
        Creates tags from a set of source images in the remote registry.
        This method will time out if it takes too long. An exception may be
        caught and retried for the timeout.

        Args:
            src_names (List[str]): The source images to combine into the image manifest
            tag_names (List[str]): The tags to push with the final image manifest

        Raises:
            TimeoutError: If the image fails to push within the timeout
        """
        LOGGER.info(f"Pushing sources {src_names} to tags {tag_names}")
        docker.buildx.imagetools.create(sources=src_names, tags=tag_names)

    def push(self) -> None:
        """
        Pushes all built images to their tagged image counterparts.
        :raises TimeoutError: If the image fails to push within the specified timeout and retries
        """
        # Parameters for timeout and retries
        initial_timeout_seconds = 60
        timeout_step_seconds = 60
        timeout_max_seconds = 600
        retries = 5

        for built_image in self._built_images:
            if not built_image.tagged_images:
                LOGGER.info(
                    f"No tags exist for built image {built_image.id}, not pushing"
                )
                continue

            source_image_refs = [image.image_ref for image in built_image.built_images]

            for tagged_image in built_image.tagged_images:
                LOGGER.info(
                    f"Pushing {built_image.id} to {', '.join(tagged_image.image_refs)}"
                )

                timeout_seconds = initial_timeout_seconds
                while retries > 0:
                    retries -= 1
                    LOGGER.debug(
                        f"Creating manifest(s) {tagged_image} with timeout {timeout_seconds} seconds"
                    )
                    try:
                        # Push each tag individually in order to prevent strange errors with multiple matching tags
                        for image_ref in tagged_image.image_refs:
                            self._push_with_timeout(source_image_refs, [image_ref])
                        # Process finished within timeout
                        LOGGER.info(
                            f"Successfully pushed multiplatform image(s) {tagged_image}"
                        )
                        break
                    except Exception as exc:  # pylint: disable=broad-exception-caught
                        LOGGER.warning(
                            f"Caught exception while pushing images, retrying: {exc}"
                        )
                    if retries == 0:
                        raise TimeoutError(
                            f"Timeout pushing {tagged_image} after {retries} retries"
                            f" and {timeout_seconds} seconds each try"
                        )
                    timeout_seconds += timeout_step_seconds

                    # Cap timeout at max timeout
                    timeout_seconds = min(timeout_seconds, timeout_max_seconds)

    @property
    def num_built_images(self) -> int:
        """
        Returns the count of built images that currently exist.
        """
        return len(self._built_images)

    @staticmethod
    def tag_native_platform(built_image: BuiltImageInfo) -> None:
        """
        Tags a single built image into the host registry for the platform matching this machine's platform.
        If a matching image to the native platform is not found, then the first image is tagged. The tags come
        from all registered tagged images in the built image info.
        :arg built_image: The built image to pull and tag
        """
        for tagged_image in built_image.tagged_images:
            LOGGER.debug(
                f"Tagging {built_image} as {tagged_image} for the native platform"
            )
            native_image = built_image.native_platform_image

            # Pull the native image and then tag it
            try:
                docker.pull(native_image.image_ref)
                for tagged_image_ref in tagged_image.image_refs:
                    docker.tag(native_image.image_ref, tagged_image_ref)
                    LOGGER.debug(
                        f"Tagged {native_image.image_ref} as {tagged_image_ref}"
                    )
                docker.image.remove(native_image.image_ref, force=True)
            except python_on_whales.exceptions.DockerException as err:
                LOGGER.error(
                    f"Failed while tagging {native_image.image_ref} as {tagged_image}: {err}"
                )
                raise err
