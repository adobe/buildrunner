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
from buildrunner.errors import (BuildRunnerConfigurationError,
                                BuildRunnerError)
from buildrunner.steprunner.tasks.build import BuildBuildStepRunnerTask
from buildrunner.steprunner.tasks.push import (CommitBuildStepRunnerTask,
                                               PushBuildStepRunnerTask)
from buildrunner.steprunner.tasks.pypipush import PypiPushBuildStepRunnerTask
from buildrunner.steprunner.tasks.remote import RemoteBuildStepRunnerTask
from buildrunner.steprunner.tasks.run import RunBuildStepRunnerTask

TASK_MAPPINGS = {
    'remote': RemoteBuildStepRunnerTask,
    'build': BuildBuildStepRunnerTask,
    'run': RunBuildStepRunnerTask,
    'push': PushBuildStepRunnerTask,
    'commit': CommitBuildStepRunnerTask,
    'pypi-push': PypiPushBuildStepRunnerTask,
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

    def __init__(self,  # pylint: disable=too-many-arguments
                 build_runner,
                 step_name,
                 step_config,
                 image_config,
                 multi_platform: MultiplatformImageBuilder):
        """
        Constructor.
        """
        local_images = image_config.local_images
        platform = image_config.platform
        self.name = step_name
        self.config = step_config
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
            for _task_name, _task_config in self.config.items():
                self.log.write(f'==> Running step: {self.name}:{_task_name}\n')
                if _task_name in TASK_MAPPINGS:
                    if self.local_images:
                        _task_config['pull'] = False
                    if self.platform:
                        _task_config['platform'] = self.platform
                    _task = TASK_MAPPINGS[_task_name](self, _task_config)
                    _tasks.append(_task)
                    try:
                        _task.run(_context)
                    except BuildRunnerError as err:
                        if not isinstance(_task_config, dict) or not _task_config.get('xfail', False):
                            raise

                        self.log.write(
                            f'Step "{self.name}" failed with exception: {err}\n    '
                            f'Ignoring due to XFAIL\n'
                        )
                else:
                    raise BuildRunnerConfigurationError(
                        f'Step "{self.name}" contains an unknown task "{_task_name}"\n'
                    )
        finally:
            for _task in _tasks:
                try:
                    _task.cleanup(_context)
                except Exception:  # pylint: disable=broad-except
                    self.log.write('\nError cleaning up task:\n')
                    traceback.print_exc(file=self.log)
