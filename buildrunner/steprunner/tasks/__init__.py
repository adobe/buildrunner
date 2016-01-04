"""
Copyright (C) 2015 Adobe
"""
from __future__ import absolute_import


class BuildStepRunnerTask(object):
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
