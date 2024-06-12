"""
Copyright 2024 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import glob
import os
import re

import buildrunner.docker
from buildrunner.config import BuildRunnerConfig
from buildrunner.config.models_step import StepBuild
from buildrunner.docker.importer import DockerImporter
from buildrunner.docker.builder import DockerBuilder
from buildrunner.errors import (
    BuildRunnerConfigurationError,
    BuildRunnerProcessingError,
)
from buildrunner.steprunner.tasks import BuildStepRunnerTask


class BuildBuildStepRunnerTask(BuildStepRunnerTask):  # pylint: disable=too-many-instance-attributes
    """
    Class used to manage "build" build tasks.
    """

    DOCKERFILE_IMAGE_REGEX = re.compile(r"^FROM (.*)", re.IGNORECASE)

    def __init__(
        self,
        step_runner,
        step: StepBuild,
        image_to_prepend_to_dockerfile=None,
    ):  # pylint: disable=too-many-statements,too-many-branches,too-many-locals
        super().__init__(step_runner, step)
        self._docker_client = buildrunner.docker.new_client(
            timeout=step_runner.build_runner.docker_timeout,
        )
        self.to_inject = {}
        self.image_to_prepend_to_dockerfile = image_to_prepend_to_dockerfile

        self._import = step.import_param
        self.path = step.path
        self.dockerfile = step.dockerfile
        self.target = step.target
        self.nocache = step.no_cache
        self.platform = step.platform
        self.platforms = step.platforms
        self.buildargs = step.buildargs
        self.cache_from = step.cache_from

        buildrunner_config = BuildRunnerConfig.get_instance()

        #  Pull the cache_from images only for single platform builds
        if self.cache_from and isinstance(self.cache_from, list) and not self.platforms:
            for cache_from_image in self.cache_from:
                if isinstance(cache_from_image, str):
                    try:
                        self._docker_client.pull(
                            cache_from_image, platform=self.platform
                        )
                        # If the pull is successful, add the image to be cleaned up at the end of the script
                        self.step_runner.build_runner.generated_images.append(
                            cache_from_image
                        )
                        self.step_runner.log.write(
                            f"Using cache_from image: {cache_from_image}\n"
                        )
                    except Exception:  # pylint: disable=broad-except
                        self.step_runner.log.write(
                            f"WARNING: Unable to pull the cache_from image: {cache_from_image}\n"
                        )

        for src_glob, dest_path in (step.inject or {}).items():
            if not dest_path:
                dest_path = ""
            _src_glob = buildrunner_config.to_abs_path(src_glob)
            xsglob = glob.glob(_src_glob)
            if not xsglob:
                # Failed to resolve the glob
                raise BuildRunnerConfigurationError(
                    f"Unable to expand inject glob: {_src_glob}"
                )
            if len(xsglob) == 1:
                # Only one source - destination may be directory or filename - check for a trailing
                # '/' and treat it accordingly.
                source_file = xsglob[0]
                if dest_path and (
                    dest_path[-1] == "/" or os.path.split(dest_path)[-1] in (".", "..")
                ):
                    self.to_inject[source_file] = os.path.normpath(
                        os.path.join(".", dest_path, os.path.basename(source_file))
                    )
                else:
                    self.to_inject[source_file] = os.path.normpath(
                        os.path.join(".", dest_path)
                    )
            else:
                # Multiple sources - destination *must* be a directory - add the source basename
                # to the dest_dir name.
                for source_file in xsglob:
                    self.to_inject[source_file] = os.path.normpath(
                        os.path.join(
                            ".",
                            dest_path,
                            os.path.basename(source_file),
                        )
                    )

        if not self._import and not any((self.path, self.dockerfile, self.to_inject)):
            raise BuildRunnerConfigurationError(
                'Docker build context must specify a "path", "dockerfile", or "inject" attribute'
            )

        if self.path:
            self.path = buildrunner_config.to_abs_path(self.path)

        if self.path and not os.path.exists(self.path):
            raise BuildRunnerConfigurationError(
                f"Step {self.step_runner}:build:path:{self.path}: Invalid build context path"
            )

        if not self.dockerfile:
            if self.path:
                path_dockerfile = os.path.join(self.path, "Dockerfile")
                if os.path.exists(path_dockerfile):
                    self.dockerfile = path_dockerfile
            for src_file, dest_file in self.to_inject.items():
                if os.path.normpath(dest_file) in [
                    "Dockerfile",
                    "/Dockerfile",
                ]:
                    self.dockerfile = src_file

        dockerfile_image = None
        if self.dockerfile:
            _dockerfile_abs_path = buildrunner_config.to_abs_path(
                self.dockerfile,
            )
            if os.path.exists(_dockerfile_abs_path):
                self.dockerfile = _dockerfile_abs_path
                if self.image_to_prepend_to_dockerfile:
                    # need to load the contents of the Dockerfile so that we
                    # can prepend the image
                    with open(
                        _dockerfile_abs_path, "r", encoding="utf-8"
                    ) as _dockerfile:
                        self.dockerfile = _dockerfile.read()

            if self.image_to_prepend_to_dockerfile:
                # prepend the given image to the dockerfile
                self.dockerfile = (
                    f"FROM {self.image_to_prepend_to_dockerfile}\n{self.dockerfile}"
                )
                dockerfile_image = self.image_to_prepend_to_dockerfile
            else:
                # Find from image in dockerfile
                match = self.DOCKERFILE_IMAGE_REGEX.match(self.dockerfile)
                if match:
                    dockerfile_image = match.group(1)

        # Set the pull attribute based on configuration or the image itself
        if step.pull is not None:
            self.pull = step.pull
            self.step_runner.log.write(
                f"Pulling image was overridden via config to {self.pull}\n"
            )
        elif not dockerfile_image:
            # Default to true if we could not determine the image
            self.pull = True
            self.step_runner.log.write(
                "Could not determine docker image, defaulting pull to true\n"
            )
        else:
            # If the image was previously committed in this run, do not pull by default
            self.pull = (
                dockerfile_image not in self.step_runner.build_runner.committed_images
            )
            self.step_runner.log.write(
                f"Pull was not specified in configuration, defaulting to {self.pull}\n"
            )

    def run(self, context):
        # 'import' will override other configuration and perform a 'docker
        # import'
        if self._import and not self.platforms:
            self.step_runner.log.write(
                f"  Importing {self._import} as a Docker image\n"
            )
            context["image"] = DockerImporter(
                self._import,
                timeout=self.step_runner.build_runner.docker_timeout,
            ).import_image()
            return

        if not self.dockerfile:
            raise BuildRunnerConfigurationError(
                "Cannot find a Dockerfile in the given path " "or inject configurations"
            )

        buildrunner_config = BuildRunnerConfig.get_instance()
        docker_registry = buildrunner_config.global_config.docker_registry
        self.step_runner.log.write("Running docker build\n")
        builder = DockerBuilder(
            self.path,
            inject=self.to_inject,
            dockerfile=self.dockerfile,
            docker_registry=docker_registry,
        )
        try:
            if self.platforms:
                built_image = self.step_runner.multi_platform.build_multiple_images(
                    platforms=self.platforms,
                    path=self.path,
                    file=self.dockerfile,
                    target=self.target,
                    build_args=self.buildargs,
                    inject=self.to_inject,
                    cache=not self.nocache,
                    pull=self.pull,
                )

                num_platforms = len(self.platforms)

                if buildrunner_config.global_config.disable_multi_platform:
                    num_platforms = 1

                num_built_platforms = len(built_image.platforms)

                assert num_built_platforms == num_platforms, (
                    f"Number of built images ({num_built_platforms}) does not match "
                    f"the number of platforms ({num_platforms})"
                )
                context["mp_built_image"] = built_image

            else:
                exit_code = builder.build(
                    console=self.step_runner.log,
                    nocache=self.nocache,
                    cache_from=self.cache_from,
                    pull=self.pull,
                    buildargs=self.buildargs,
                    platform=self.platform,
                    target=self.target,
                )
                if exit_code != 0 or not builder.image:
                    raise BuildRunnerProcessingError("Error building image")
                context["image"] = builder.image
                self.step_runner.build_runner.generated_images.append(builder.image)
        except Exception as exc:
            self.step_runner.log.write(f"ERROR: {exc}\n")
            raise
        finally:
            builder.cleanup()
