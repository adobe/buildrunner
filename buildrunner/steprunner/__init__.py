"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import os
import traceback
import uuid

from buildrunner.docker.multiplatform_image_builder import MultiplatformImageBuilder
from buildrunner.config.models_step import Step, StepBuild, StepRun
from buildrunner.errors import BuildRunnerError
from buildrunner.steprunner.tasks.build import BuildBuildStepRunnerTask
from buildrunner.steprunner.tasks.push import (
    CommitBuildStepRunnerTask,
    PushBuildStepRunnerTask,
)
from buildrunner.steprunner.tasks.pypipush import PypiPushBuildStepRunnerTask
from buildrunner.steprunner.tasks.remote import RemoteBuildStepRunnerTask
from buildrunner.steprunner.tasks.run import RunBuildStepRunnerTask

TASK_MAPPINGS = {
    "remote": RemoteBuildStepRunnerTask,
    "build": BuildBuildStepRunnerTask,
    "run": RunBuildStepRunnerTask,
    "push": PushBuildStepRunnerTask,
    "commit": CommitBuildStepRunnerTask,
    "pypi-push": PypiPushBuildStepRunnerTask,
}


class BuildStepRunner:  # pylint: disable=too-many-instance-attributes
    """
    Class used to manage running a build step.
    """

    class ImageConfig:
        """
        An object that captures image-specific configuration
        """

        def __init__(self, local_images=False, platform=None):
            self.local_images = local_images
            self.platform = platform

    def __init__(
        self,  # pylint: disable=too-many-arguments
        build_runner,
        step_name,
        step: Step,
        image_config,
        multi_platform: MultiplatformImageBuilder,
        container_labels,
    ):
        """
        Constructor.
        """
        local_images = image_config.local_images
        platform = image_config.platform
        self.name = step_name
        self.step = step
        self.local_images = local_images
        self.platform = platform

        self.build_runner = build_runner
        self.src_dir = self.build_runner.build_dir
        self.results_dir = os.path.join(
            self.build_runner.build_results_dir,
            self.name,
        )
        if not os.path.exists(self.results_dir):
            os.mkdir(self.results_dir)

        self.log = self.build_runner.log

        # generate a unique step id
        self.id = str(uuid.uuid4())  # pylint: disable=invalid-name
        self.multi_platform = multi_platform
        self.container_labels = container_labels

    def run(self):
        """
        Run the build step.
        """
        # create the step results dir
        self.log.write(f'\nRunning step "{self.name}"\n')
        self.log.write(f"{'_' * 40}\n")

        _tasks = []
        _context = {}
        try:
            for task_name, task_class in TASK_MAPPINGS.items():
                task_data = getattr(self.step, task_name.replace("-", "_"))
                if not task_data:
                    continue
                self.log.write(f"==> Running step: {self.name}:{task_name}\n")
                if isinstance(task_data, (StepBuild, StepRun)):
                    if self.local_images:
                        task_data.pull = False
                    if self.platform:
                        task_data.platform = self.platform
                _task = task_class(self, task_data)
                _tasks.append(_task)
                try:
                    _task.run(_context)
                except BuildRunnerError as err:
                    if not isinstance(task_data, StepRun) or not task_data.xfail:
                        raise

                    self.log.write(
                        f'Step "{self.name}" failed with exception: {err}\n    '
                        f"Ignoring due to XFAIL\n"
                    )
                except Exception as err:  # pylint: disable=broad-except
                    self.log.write(f'Step "{self.name}" failed with exception: {err}\n')
                    raise err
        finally:
            for _task in _tasks:
                try:
                    _task.cleanup(_context)
                except Exception:  # pylint: disable=broad-except
                    self.log.write("\nError cleaning up task:\n")
                    traceback.print_exc(file=self.log)
