"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import re


def sanitize_tag(tag, log=None):
    """
    Sanitize a tag to remove illegal characters.

    :param tag: The tag to sanitize.
    :param log: Optional log to write warnings to.
    :return: The sanitized tag.
    """
    _tag = re.sub(r'[^-_\w.]+', '-', tag.lower())
    if _tag != tag and log:
        log.write(f'Forcing tag to lowercase and removing illegal characters: {tag} => {_tag}\n')
    return _tag


class BuildStepRunnerTask:
    """
    Base task class.
    """

    def __init__(self, step_runner, config):
        """
        Subclasses should extend this method to validate the task configuration
        and set any attributes.
        """
        self.step_runner = step_runner
        self.config = config

    def run(self, context):
        """
        Subclasses override this method to perform their task.
        """
        pass

    def cleanup(self, context):
        """
        Subclasses override this method to perform any cleanup tasks.
        """
        pass


class MultiPlatformBuildStepRunnerTask(BuildStepRunnerTask):
    """
    Base task class for tasks that need to build/use images for multiple platforms.
    """

    def get_unique_build_name(self):
        """
        Returns a unique build name for this build and step.
        """
        return f'{self.step_runner.name}-{sanitize_tag(self.step_runner.build_runner.build_id)}'
