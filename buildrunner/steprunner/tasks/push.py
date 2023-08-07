"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
import os
from typing import List, Optional, Union

import buildrunner.docker
from buildrunner.errors import (
    BuildRunnerConfigurationError,
    BuildRunnerProcessingError,
)
from buildrunner.steprunner.tasks import MultiPlatformBuildStepRunnerTask, sanitize_tag


class RepoDefinition:
    """
    Contains the definition for a push repository.
    """

    def __init__(
            self,
            log,
            repository: str,
            tags: Optional[List[str]] = None,
            insecure_registry: Optional[bool] = None,
    ):
        # Force a lower-case repo
        repo_lower = repository.lower()
        if repo_lower != repository:
            log.write(
                f'Forcing repository to lowercase: {repository} => {repo_lower}\n'
            )
        self.repository = repo_lower

        if tags:
            self.tags = [sanitize_tag(tag, log=log) for tag in tags]
        else:
            self.tags = []
        self.insecure_registry = insecure_registry

        # if there is a tag in the repository value, strip it off and add the tag to the list of tags
        tag_index = self.repository.find(":")
        if tag_index > 0:
            tag = self.repository[tag_index + 1:]
            if tag not in self.tags:
                self.tags.append(tag)
            self.repository = self.repository[0:tag_index]


class PushBuildStepRunnerTask(MultiPlatformBuildStepRunnerTask):
    """
    Class used to push the resulting image (either from the build task, or if
    there is a run task, the snapshot of the resulting run container) to the
    given registry/repository.
    """
    def _get_repo_definition(self, config: Union[dict, str]) -> RepoDefinition:
        if isinstance(config, dict):
            if 'repository' not in config:
                raise BuildRunnerConfigurationError(
                    'Docker push configuration must at least specify a "repository" attribute'
                )
            return RepoDefinition(
                self.step_runner.log,
                config['repository'],
                config.get('tags'),
                config.get('insecure_registry'),
            )
        return RepoDefinition(self.step_runner.log, config)

    def __init__(self, step_runner, config, commit_only=False):
        super().__init__(step_runner, config)
        self._docker_client = buildrunner.docker.new_client(
            timeout=step_runner.build_runner.docker_timeout,
        )
        self._commit_only = commit_only
        if isinstance(config, list):
            self._repos = [self._get_repo_definition(item) for item in config]
        else:
            self._repos = [self._get_repo_definition(config)]

    def run(self, context):  # pylint: disable=too-many-branches

        # Determine internal tag based on source control information and build number
        # Note: do not log sanitization as it would need to happen almost every time
        default_tag = sanitize_tag(self.step_runner.build_runner.build_id)

        # Tag multi-platform images
        if self.step_runner.multi_platform.is_multiplatform(self.get_unique_build_name()):
            for repo in self._repos:
                # Always add default tag
                repo.tags.append(default_tag)
                self.step_runner.multi_platform.tag_single_platform(name=self.get_unique_build_name(),
                                                                    tags=repo.tags,
                                                                    dest_name=repo.repository)

        # Tag single platform images
        else:
            # first see if a run task produced an image (via a post-build config)
            if 'run-image' in context:
                image_to_use = context.get('run-image')
            # next see if there was a run task, committing the end state of the
            # container as the image to use
            elif 'run_runner' in context:
                image_to_use = context['run_runner'].commit(self.step_runner.log)
            # finally see if we have an image from a build task
            else:
                image_to_use = context.get('image', None)

            # validate we have an image
            if not image_to_use:
                raise BuildRunnerProcessingError(
                    'Cannot find an image to tag/push from a previous task'
                )
            self.step_runner.log.write(
                f'Using image {image_to_use} for tagging\n'
            )

            # add the image to the list of generated images for potential cleanup
            self.step_runner.build_runner.generated_images.append(image_to_use)

            for repo in self._repos:
                # Always add default tag
                repo.tags.append(default_tag)

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
                    self.step_runner.build_runner.committed_images.add(f'{repo.repository}:{tag}')

                    if not self._commit_only:
                        self.step_runner.build_runner.repo_tags_to_push.append((
                            f"{repo.repository}:{tag}",
                            repo.insecure_registry,
                        ))

                # add image as artifact
                if not self._commit_only:
                    self.step_runner.build_runner.add_artifact(
                        os.path.join(self.step_runner.name, image_to_use),
                        {
                            'type': 'docker-image',
                            'docker:image': image_to_use,
                            'docker:repository': repo.repository,
                            'docker:tags': repo.tags,
                        },
                    )


class CommitBuildStepRunnerTask(PushBuildStepRunnerTask):
    """
    Class used to commit the resulting image (either from the build task, or if
    there is a run task, the snapshot of the resulting run container) with a
    tag matching the given registry/repository.
    """

    def __init__(self, step_runner, config):
        # Subclasses the push task, just set commit only to true
        super().__init__(step_runner, config, commit_only=True)


# Local Variables:
# fill-column: 100
# End:
