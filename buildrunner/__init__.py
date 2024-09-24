"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
# pylint: disable=too-many-lines

from collections import OrderedDict
import fnmatch
import importlib.machinery
import inspect
import json
import logging
import os
import shutil
import sys
import tarfile
import tempfile
import types
from typing import List, Optional

import requests

from retry import retry
from vcsinfo import detect_vcs, VCSUnsupported, VCSMissingRevision
from docker.errors import ImageNotFound

from buildrunner import docker, loggers
from buildrunner.config import (
    BuildRunnerConfig,
)
from buildrunner.config.models import DEFAULT_CACHES_ROOT
from buildrunner.errors import (
    BuildRunnerConfigurationError,
    BuildRunnerProcessingError,
)
from buildrunner.steprunner import BuildStepRunner
from buildrunner.docker.multiplatform_image_builder import MultiplatformImageBuilder
import buildrunner.docker.builder as legacy_builder


LOGGER = logging.getLogger(__name__)

__version__ = "DEVELOPMENT"
try:
    _VERSION_FILE = os.path.join(os.path.dirname(__file__), "version.py")
    if os.path.exists(_VERSION_FILE):
        loader = importlib.machinery.SourceFileLoader(
            "buildrunnerversion", _VERSION_FILE
        )
        _VERSION_MOD = types.ModuleType(loader.name)
        loader.exec_module(_VERSION_MOD)
        __version__ = getattr(_VERSION_MOD, "__version__", __version__)
except Exception:  # pylint: disable=broad-except
    pass

SOURCE_DOCKERFILE = os.path.join(os.path.dirname(__file__), "SourceDockerfile")


class BuildRunner:
    """
    Class used to manage running a build.
    """

    def __init__(
        self,
        *,
        build_dir: str,
        build_results_dir: str,
        global_config_file: Optional[str],
        run_config_file: Optional[str],
        build_time: int,
        build_number: int,
        push: bool,
        cleanup_images: bool,
        cleanup_cache: bool,
        steps_to_run: Optional[List[str]],
        publish_ports: bool,
        log_generated_files: bool,
        docker_timeout: int,
        local_images: bool,
        platform: Optional[str],
        global_config_overrides: dict,
    ):  # pylint: disable=too-many-statements,too-many-branches,too-many-locals,too-many-arguments
        self.build_dir = build_dir
        self.build_results_dir = build_results_dir
        self.build_time = build_time
        self.build_number = build_number
        self.push = push
        self.cleanup_images = cleanup_images
        self.cleanup_cache = cleanup_cache
        self.generated_images = []
        # The set of images (including tag) that were committed as part of this build
        # This is used to check if images should be pulled by default or not
        self.committed_images = set()
        self.repo_tags_to_push = []
        self.steps_to_run = steps_to_run
        self.publish_ports = publish_ports
        self.log_generated_files = log_generated_files
        self.docker_timeout = docker_timeout
        self.local_images = local_images
        self.platform = platform

        self.tmp_files = []
        self.artifacts = OrderedDict()
        self.pypi_packages = OrderedDict()

        self.exit_code = None
        self._source_image = None
        self._source_archive = None
        self._log = None
        self._step_runner = None

        try:
            vcs = detect_vcs(self.build_dir)
            self.build_id = f"{vcs.id_string}-{self.build_number}"
        except VCSUnsupported as err:
            self.log.write(
                f"{err}\nPlease verify you have a VCS set up for this project.\n"
            )
            sys.exit()
        except VCSMissingRevision as err:
            self.log.write(f"{err}\nMake sure you have at least one commit.\n")
            sys.exit()

        # load global configuration - must come *after* VCS detection
        BuildRunnerConfig.initialize_instance(
            push=push,
            build_number=self.build_number,
            build_id=self.build_id,
            vcs=vcs,
            steps_to_run=self.steps_to_run,
            build_dir=self.build_dir,
            global_config_file=global_config_file,
            run_config_file=run_config_file,
            log_generated_files=self.log_generated_files,
            build_time=self.build_time,
            tmp_files=self.tmp_files,
            global_config_overrides=global_config_overrides,
        )
        self.buildrunner_config = BuildRunnerConfig.get_instance()

        # cleanup local cache
        if self.cleanup_cache:
            self.clean_cache()

        if steps_to_run:
            missing_steps = [
                step
                for step in steps_to_run
                if step not in self.buildrunner_config.run_config.steps
            ]
            if missing_steps:
                raise BuildRunnerConfigurationError(
                    f"The following steps do not exist: {', '.join(missing_steps)}"
                )

    @property
    def log(self) -> loggers.ConsoleLogger:
        """
        Create the log file and open for writing
        """
        if self._log is None:
            self._log = loggers.ConsoleLogger(__name__)
            self.add_artifact(
                os.path.basename(
                    loggers.get_build_log_file_path(self.build_results_dir)
                ),
                {"type": "log"},
            )
        return self._log

    @staticmethod
    def get_cache_archive_ext():
        """
        Returns the archive file extension used for cache archive files
        """
        return "tar"

    def get_cache_archive_file(self, cache_name, project_name=""):
        """
        Given a cache name determine the local file path.
        """

        def get_filename(caches_root, cache_name):
            local_cache_archive_file = os.path.expanduser(
                os.path.join(caches_root, cache_name)
            )
            cache_dir = os.path.dirname(local_cache_archive_file)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            return local_cache_archive_file

        cache_name = f"{cache_name}.{self.get_cache_archive_ext()}"
        if project_name != "":
            cache_name = f"{project_name}-{cache_name}"

        caches_root = BuildRunnerConfig.get_instance().global_config.caches_root
        try:
            local_cache_archive_file = get_filename(caches_root, cache_name)
        except Exception as exc:  # pylint: disable=broad-except
            # Intentionally catch all exceptions here since we don't want to fail the build
            LOGGER.warning(f"There was an issue with {caches_root}: {str(exc)}")
            local_cache_archive_file = get_filename(DEFAULT_CACHES_ROOT, cache_name)
            LOGGER.warning(f"Using {DEFAULT_CACHES_ROOT} for the cache directory")

        return local_cache_archive_file

    @staticmethod
    def clean_cache():
        """
        Clean cache dir
        """
        global_config = BuildRunnerConfig.get_instance().global_config
        cache_dir = os.path.expanduser(global_config.caches_root)
        if os.path.exists(cache_dir):
            LOGGER.info(f'Cleaning cache dir "{cache_dir}"')
            shutil.rmtree(f"{cache_dir}/")
            LOGGER.info(f'Cleaned cache dir "{cache_dir}"')
        else:
            LOGGER.info(f'Cache dir "{cache_dir}" is already clean')

    def add_artifact(self, artifact_file, properties):
        """
        Register a build artifact to be included in the artifacts manifest.
        """
        self.artifacts[artifact_file] = properties

    @retry(exceptions=FileNotFoundError, tries=5, delay=1, backoff=3, max_delay=10)
    def _create_archive_tarfile(self, dir_to_add, _fileobj, filter_func):
        """
        Create the tarfile with retries
        """
        with tarfile.open(mode="w", fileobj=_fileobj) as tfile:
            tfile.add(dir_to_add, arcname="", filter=filter_func)

    def get_source_archive_path(self):
        """
        Create the source archive for use in remote builds or to build the
        source image.
        """
        if not self._source_archive:
            buildignore = os.path.join(self.build_dir, ".buildignore")
            excludes = []
            if os.path.exists(buildignore):
                with open(buildignore, "r", encoding="utf-8") as _file:
                    excludes = _file.read().splitlines()

            def _filter_results_and_excludes(tarinfo):
                """
                Filter to exclude results dir and listed excludes from source archive.
                """
                if tarinfo.name == os.path.basename(self.build_results_dir):
                    return None
                for _ex in excludes:
                    if _ex and _ex.strip() and fnmatch.fnmatch(tarinfo.name, _ex):
                        return None
                return tarinfo

            self.log.write("Creating source archive\n")
            _fileobj = None
            try:
                # pylint: disable=consider-using-with
                _fileobj = tempfile.NamedTemporaryFile(
                    delete=False,
                    dir=BuildRunnerConfig.get_instance().global_config.temp_dir,
                )
                self._create_archive_tarfile(
                    self.build_dir, _fileobj, _filter_results_and_excludes
                )
                self._source_archive = _fileobj.name
            finally:
                if _fileobj:
                    _fileobj.close()
        return self._source_archive

    def get_source_image(self):
        """
        Get and/or create the base image source containers will be created from.
        """
        if not self._source_image:
            self.log.write("Creating source image\n")
            source_archive_path = self.get_source_archive_path()
            inject = {
                source_archive_path: "source.tar",
                SOURCE_DOCKERFILE: "Dockerfile",
            }
            if self.buildrunner_config.run_config.use_legacy_builder:
                image = legacy_builder.build_image(
                    temp_dir=self.buildrunner_config.global_config.temp_dir,
                    inject=inject,
                    timeout=self.docker_timeout,
                    docker_registry=self.buildrunner_config.global_config.docker_registry,
                    nocache=True,
                    pull=False,
                )
                self._source_image = image
            else:
                # Use buildx builder
                native_platform = self._step_runner.multi_platform.get_native_platform()
                LOGGER.info(f"Setting platforms to [{native_platform}]")
                platforms = [native_platform]
                built_images_info = (
                    self._step_runner.multi_platform.build_multiple_images(
                        platforms=platforms,
                        inject=inject,
                        cache=False,
                        pull=False,
                        build_args={
                            "BUILDRUNNER_DISTRO": os.environ.get("BUILDRUNNER_DISTRO")
                        },
                    )
                )
                if len(built_images_info.built_images) != 1:
                    raise BuildRunnerProcessingError(
                        "Failed to build source image. Retrying the build may resolve the issue."
                    )
                self._source_image = built_images_info.built_images[0].trunc_digest

        return self._source_image

    def _write_artifact_manifest(self):
        """
        If we have registered artifacts write the files and associated metadata
        to the artifacts manifest.
        """
        if self.artifacts:
            self.log.write("\nWriting artifact properties\n")
            artifact_manifest = os.path.join(
                self.build_results_dir,
                "artifacts.json",
            )
            # preserve contents of artifacts.json between steps run separately
            if os.path.exists(artifact_manifest):
                with open(artifact_manifest, "r", encoding="utf-8") as _af:
                    data = json.load(_af, object_pairs_hook=OrderedDict)
                    artifacts = OrderedDict(
                        list(data.items()) + list(self.artifacts.items())
                    )
            else:
                artifacts = self.artifacts

            with open(artifact_manifest, "w", encoding="utf-8") as _af:
                json.dump(artifacts, _af, indent=2)

    def _exit_message(self, exit_explanation):
        """
        Determine the exit message and output to the log.
        """
        if self.exit_code:
            exit_message = "Build ERROR."
            log_method = self.log.error
        else:
            exit_message = "Build SUCCESS."
            log_method = self.log.info

        if self.log:
            if exit_explanation:
                self.log.info("")
                log_method(exit_explanation)
            self.log.info("")
            log_method(exit_message)
        else:
            if exit_explanation:
                print(f"\n{exit_explanation}")
            print(f"\n{exit_message}")

    def run(self):  # pylint: disable=too-many-statements,too-many-branches,too-many-locals
        """
        Run the build.
        """
        # reset the exit_code
        self.exit_code = None

        exit_explanation = None
        try:  # pylint: disable=too-many-nested-blocks
            with MultiplatformImageBuilder(
                docker_registry=self.buildrunner_config.global_config.docker_registry,
                build_registry=self.buildrunner_config.global_config.build_registry,
                temp_dir=self.buildrunner_config.global_config.temp_dir,
                platform_builders=self.buildrunner_config.global_config.platform_builders,
                cache_builders=self.buildrunner_config.global_config.docker_build_cache.builders,
                cache_from=self.buildrunner_config.global_config.docker_build_cache.from_config,
                cache_to=self.buildrunner_config.global_config.docker_build_cache.to_config,
            ) as multi_platform:
                self.get_source_archive_path()
                # run each step
                for (
                    step_name,
                    step_config,
                ) in self.buildrunner_config.run_config.steps.items():
                    # Reset the cache_from and cache_to for each step to the global values
                    multi_platform.set_cache_from(
                        self.buildrunner_config.global_config.docker_build_cache.from_config
                    )
                    multi_platform.set_cache_to(
                        self.buildrunner_config.global_config.docker_build_cache.to_config
                    )

                    if not self.steps_to_run or step_name in self.steps_to_run:
                        image_config = BuildStepRunner.ImageConfig(
                            self.local_images, self.platform
                        )

                        # Override the multiplatform cache_from and cache_to if the step has its own
                        if step_config.build and step_config.build.cache_from:
                            LOGGER.info(
                                f"Overriding cache_from with {step_config.build.cache_from}"
                            )
                            multi_platform.set_cache_from(step_config.build.cache_from)
                        if step_config.build and step_config.build.cache_to:
                            LOGGER.info(
                                f"Overriding cache_to with {step_config.build.cache_to}"
                            )
                            multi_platform.set_cache_to(step_config.build.cache_to)

                        self._step_runner = BuildStepRunner(
                            self, step_name, step_config, image_config, multi_platform
                        )
                        self._step_runner.run()

                self.log.write(
                    "\nFinalizing build\n________________________________________\n"
                )

                # see if we should push registered tags to remote registries/repositories
                if self.push:
                    self.log.write(
                        "Push requested--pushing generated images/packages to remote registries/repositories\n"
                    )
                    # Push multi-platform images
                    if multi_platform.num_built_images:
                        self.log.write(
                            f"===> Pushing {multi_platform.num_built_images} multiplatform image(s)\n"
                        )
                        multi_platform.push()

                    # Push single platform images
                    _docker_client = docker.new_client(timeout=self.docker_timeout)
                    for _repo_tag, _insecure_registry in self.repo_tags_to_push:
                        self.log.write(f"\nPushing {_repo_tag}\n")

                        # Newer Python Docker bindings drop support for the insecure_registry
                        # option.  This test will optionally use it when it's available.
                        push_kwargs = {
                            "stream": True,
                        }
                        if (
                            "insecure_registry"
                            in inspect.getfullargspec(_docker_client.push).args
                        ):
                            push_kwargs["insecure_registry"] = _insecure_registry

                        stream = _docker_client.push(_repo_tag, **push_kwargs)
                        previous_status = None
                        for msg_str in stream:
                            for msg in msg_str.decode("utf-8").split("\n"):
                                if not msg:
                                    continue
                                msg = json.loads(msg)
                                if "status" in msg:
                                    if msg["status"] == previous_status:
                                        continue
                                    self.log.write(msg["status"] + "\n")
                                    previous_status = msg["status"]
                                elif "errorDetail" in msg:
                                    error_detail = (
                                        f"Error pushing image: {msg['errorDetail']}\n"
                                    )
                                    self.log.write("\n" + error_detail)
                                    self.log.write(
                                        (
                                            "This could be because you are not "
                                            "authenticated with the given Docker "
                                            "registry (try 'docker login "
                                            "<registry>')\n\n"
                                        )
                                    )
                                    raise BuildRunnerProcessingError(error_detail)
                                else:
                                    self.log.write(str(msg) + "\n")

                    # Push to pypi repositories
                    # Placing the import here avoids the dependency when pypi is not needed
                    import twine.commands.upload  # pylint: disable=import-outside-toplevel

                    for _, _items in self.pypi_packages.items():
                        twine.commands.upload.upload(
                            _items["upload_settings"], _items["packages"]
                        )
                else:
                    self.log.write("\nPush not requested\n")

        except BuildRunnerConfigurationError as brce:
            exit_explanation = str(brce)
            self.exit_code = os.EX_CONFIG
        except BuildRunnerProcessingError as brpe:
            exit_explanation = str(brpe)
            self.exit_code = 1
        except requests.exceptions.ConnectionError as rce:
            print(str(rce))
            exit_explanation = (
                "Error communicating with the remote host.\n\tCheck that the "
                "remote docker Daemon is running and/or that the DOCKER_* "
                "environment variables are set correctly.\n\tCheck that the "
                "remote PyPi server information is set correctly."
            )
            self.exit_code = 1

        finally:
            self._write_artifact_manifest()

            _docker_client = docker.new_client(timeout=self.docker_timeout)

            # cleanup the source image
            if self._source_image:
                self.log.write(f"Destroying source image {self._source_image}\n")
                try:
                    _docker_client.remove_image(
                        self._source_image,
                        noprune=False,
                        force=True,
                    )
                except ImageNotFound:
                    self.log.warning(
                        f"Failed to remove source image {self._source_image}\n"
                    )

            if self.cleanup_images:
                self.log.write("Removing local copy of generated images\n")
                # cleanup all registered docker images
                # reverse the order of the images since child images would likely come after parent images
                for _image in self.generated_images[::-1]:
                    try:
                        _docker_client.remove_image(
                            _image,
                            noprune=False,
                            force=True,
                        )
                    except Exception as _ex:  # pylint: disable=broad-except
                        self.log.write(f"Error removing image {_image}: {str(_ex)}\n")
            else:
                self.log.write("Keeping generated images\n")
            if self._source_archive:
                self.log.write("Destroying source archive\n")
                os.remove(self._source_archive)

            # remove any temporary files that we created
            for tmp_file in self.tmp_files:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)

            self._exit_message(exit_explanation)


# Local Variables:
# fill-column: 100
# End:
