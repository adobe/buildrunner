"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
import logging
import os
from typing import List, Optional

import buildrunner.docker
from buildrunner.config.models_step import StepPushCommit
from buildrunner.errors import (
    BuildRunnerProcessingError,
)
from buildrunner.steprunner.tasks import BuildStepRunnerTask
from buildrunner.utils import sanitize_tag


LOGGER = logging.getLogger(__name__)


class RepoDefinition:
    """
    Contains the definition for a push repository.
    """

    def __init__(
        self,
        repository: str,
        tags: Optional[List[str]] = None,
    ):
        # Force a lower-case repo
        repo_lower = repository.lower()
        if repo_lower != repository:
            LOGGER.info(
                f"Forcing repository to lowercase: {repository} => {repo_lower}"
            )
        self.repository = repo_lower

        if tags:
            self.tags = [sanitize_tag(tag) for tag in tags]
        else:
            self.tags = []

        # if there is a tag in the repository value, strip it off and add the tag to the list of tags
        tag_index = self.repository.find(":")
        if tag_index > 0:
            tag = self.repository[tag_index + 1 :]
            if tag not in self.tags:
                self.tags.append(tag)
            self.repository = self.repository[0:tag_index]


class PushBuildStepRunnerTask(BuildStepRunnerTask):
    """
    Class used to push the resulting image (either from the build task, or if
    there is a run task, the snapshot of the resulting run container) to the
    given registry/repository.
    """

    def __init__(self, step_runner, pushes: List[StepPushCommit], commit_only=False):
        super().__init__(step_runner, pushes[0])
        self._docker_client = buildrunner.docker.new_client(
            timeout=step_runner.build_runner.docker_timeout,
        )
        self._commit_only = commit_only
        self._repos = [
            RepoDefinition(
                push.repository,
                push.tags,
            )
            for push in pushes
        ]

    def run(self, context):  # pylint: disable=too-many-branches
        # Tag multi-platform images
        built_image = context.get("mp_built_image")
        if built_image:
            # These are used in the image artifacts below, and should match for all tagged images
            built_image_ids_str = ",".join(
                [image.trunc_digest for image in built_image.built_images]
            )
            built_image_id_with_platforms = [
                f"{image.platform}:{image.trunc_digest}"
                for image in built_image.built_images
            ]

            for repo in self._repos:
                tagged_image = built_image.add_tagged_image(repo.repository, repo.tags)

                # Add tagged image refs to committed images for use in determining if pull should be true/false
                for image_ref in tagged_image.image_refs:
                    self.step_runner.build_runner.committed_images.add(image_ref)

                # Add tagged image as artifact if this is a push and not just a commit
                if not self._commit_only:
                    self.step_runner.build_runner.add_artifact(
                        repo.repository,
                        {
                            "type": "docker-image",
                            "docker:image": built_image_ids_str,
                            "docker:repository": repo.repository,
                            "docker:tags": repo.tags,
                            "docker:platforms": built_image_id_with_platforms,
                        },
                    )

            # Tag all images locally for the native platform
            self.step_runner.multi_platform.tag_native_platform(built_image)

        # Tag single platform images
        else:
            # first see if a run task produced an image (via a post-build config)
            if "run-image" in context:
                image_to_use = context.get("run-image")
            # next see if there was a run task, committing the end state of the
            # container as the image to use
            elif "run_runner" in context:
                image_to_use = context["run_runner"].commit(self.step_runner.log)
            # finally see if we have an image from a build task
            else:
                image_to_use = context.get("image", None)

            # validate we have an image
            if not image_to_use:
                raise BuildRunnerProcessingError(
                    "Cannot find an image to tag/push from a previous task"
                )
            self.step_runner.log.write(f"Using image {image_to_use} for tagging\n")

            # add the image to the list of generated images for potential cleanup
            self.step_runner.build_runner.generated_images.append(image_to_use)

            for repo in self._repos:
                if self._commit_only:
                    self.step_runner.log.write(
                        f'Committing resulting image as "{repo.repository}" with tags {", ".join(repo.tags)}.\n'
                    )
                else:
                    self.step_runner.log.write(
                        f'Preparing resulting image for push to "{repo.repository}" with tags {", ".join(repo.tags)}.\n'
                    )

                # Tag the image
                for tag in repo.tags:
                    self._docker_client.tag(
                        image_to_use,
                        repo.repository,
                        tag=tag,
                        force=True,
                    )
                    self.step_runner.build_runner.committed_images.add(
                        f"{repo.repository}:{tag}"
                    )

                    if not self._commit_only:
                        self.step_runner.build_runner.repo_tags_to_push.append(
                            (
                                f"{repo.repository}:{tag}",
                                # Used to be insecure registry, but this is now deprecated/removed
                                False,
                            )
                        )

                # add image as artifact
                if not self._commit_only:
                    self.step_runner.build_runner.add_artifact(
                        os.path.join(self.step_runner.name, image_to_use),
                        {
                            "type": "docker-image",
                            "docker:image": image_to_use,
                            "docker:repository": repo.repository,
                            "docker:tags": repo.tags,
                        },
                    )


class CommitBuildStepRunnerTask(PushBuildStepRunnerTask):
    """
    Class used to commit the resulting image (either from the build task, or if
    there is a run task, the snapshot of the resulting run container) with a
    tag matching the given registry/repository.
    """

    def __init__(self, step_runner, commits: List[StepPushCommit]):
        # Subclasses the push task, just set commit only to true
        super().__init__(step_runner, commits, commit_only=True)
