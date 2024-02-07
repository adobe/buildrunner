"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from buildrunner.config.models_step import StepTask


class BuildStepRunnerTask:
    """
    Base task class.
    """

    def __init__(self, step_runner, step: StepTask):
        """
        Subclasses should extend this method to validate the task configuration
        and set any attributes.
        """
        self.step_runner = step_runner
        self.step = step

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
