"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""


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
