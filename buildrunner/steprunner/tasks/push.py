"""
Copyright (C) 2020-2021 Adobe
"""

import os
import re

import buildrunner.docker
from buildrunner.errors import (
    BuildRunnerConfigurationError,
    BuildRunnerProcessingError,
)
from buildrunner.steprunner.tasks import BuildStepRunnerTask
from buildrunner.utils import is_dict


def sanitize_tag(tag, log=None):
    """
    :param tag:
    :param log:
    """
    _tag = re.sub(r'[^-_\w.]+', '-', tag.lower())
    if _tag != tag and log:
        log.write(f'Forcing tag to lowercase and removing illegal characters: {tag} => {_tag}\n')
    return _tag


class PushBuildStepRunnerTask(BuildStepRunnerTask):
    """
    Class used to push the resulting image (either from the build task, or if
    there is a run task, the snapshot of the resulting run container) to the
    given registry/repository.
    """

    def __init__(self, step_runner, config):
        super().__init__(step_runner, config)
        self._docker_client = buildrunner.docker.new_client(
            timeout=step_runner.build_runner.docker_timeout,
        )
        self._repository = None
        self._insecure_registry = None
        self._tags = []
        if is_dict(config):
            if 'repository' not in config:
                raise BuildRunnerConfigurationError(
                    'Docker push configuration must at least specify a "repository" attribute'
                )
            self._repository = config['repository']

            if 'tags' in config:
                for tag in config['tags']:
                    self._tags.append(sanitize_tag(tag, self.step_runner.log))

            if 'insecure_registry' in config:
                self._insecure_registry = config['insecure_registry'] is True
        else:
            self._repository = config

        lrepo = self._repository.lower()
        if lrepo != self._repository:
            self.step_runner.log.write(
                f'Forcing repository to lowercase: {self._repository} => {lrepo}\n'
            )
            self._repository = lrepo

        # if there is a tag in the repository value, strip it off and add the tag to the list of tags
        tag_index = self._repository.find(":")
        if tag_index > 0:
            tag = self._repository[tag_index + 1:]
            if tag not in self._tags:
                self._tags.append(tag)
            self._repository = self._repository[0:tag_index]

    def run(self, context):
        self.step_runner.log.write(
            f'Preparing resulting image for push to "{self._repository}".\n'
        )

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

        # determine internal tag based on source control information and build
        # number
        self._tags.append(
            sanitize_tag(self.step_runner.build_runner.build_id, self.step_runner.log)
        )

        # add the image to the list of generated images for potential cleanup
        self.step_runner.build_runner.generated_images.append(image_to_use)

        # tag the image
        for _tag in self._tags:
            self.step_runner.log.write(
                f'Tagging image "{image_to_use}" with repository:tag "{self._repository}:{_tag}"\n'
            )
            self._docker_client.tag(
                image_to_use,
                self._repository,
                tag=_tag,
                force=True,
            )
            self.step_runner.build_runner.repo_tags_to_push.append((
                f"{self._repository}:{_tag}",
                self._insecure_registry,
            ))

        # add image as artifact
        self.step_runner.build_runner.add_artifact(
            os.path.join(self.step_runner.name, image_to_use),
            {
                'type': 'docker-image',
                'docker:image': image_to_use,
                'docker:repository': self._repository,
                'docker:tags': self._tags,
            },
        )

# Local Variables:
# fill-column: 100
# End:
