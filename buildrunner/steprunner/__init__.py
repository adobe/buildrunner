"""
Copyright (C) 2015 Adobe
"""
from __future__ import absolute_import
import os
import traceback
import uuid

from buildrunner.errors import (
    BuildRunnerError,
    BuildRunnerConfigurationError,
    BuildRunnerProcessingError,
)
from buildrunner.steprunner.tasks.build import BuildBuildStepRunnerTask
from buildrunner.steprunner.tasks.push import PushBuildStepRunnerTask
from buildrunner.steprunner.tasks.remote import RemoteBuildStepRunnerTask
from buildrunner.steprunner.tasks.run import RunBuildStepRunnerTask


TASK_MAPPINGS = {
    'remote': RemoteBuildStepRunnerTask,
    'build': BuildBuildStepRunnerTask,
    'run': RunBuildStepRunnerTask,
    'push': PushBuildStepRunnerTask,
}


class BuildStepRunner(object):
    """
    Class used to manage running a build step.
    """


    def __init__(self, build_runner, step_name, step_config):
        """
        Constructor.
        """
        self.name = step_name
        self.config = step_config

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
        self.id = str(uuid.uuid4())


    def run(self):
        """
        Run the build step.
        """
        # create the step results dir
        self.log.write('\nRunning step "%s"\n' % self.name)
        self.log.write('________________________________________\n')

        _tasks = []
        _context = {}
        try:
            for _task_name, _task_config in self.config.iteritems():
                self.log.write('==> Running step: %s:%s\n' % (self.name, _task_name))
                if _task_name in TASK_MAPPINGS:
                    _task = TASK_MAPPINGS[_task_name](self, _task_config)
                    _tasks.append(_task)
                    try:
                        _task.run(_context)
                    except BuildRunnerError as err:
                        if not isinstance(_task_config, dict) or not _task_config.get('xfail', False):
                            raise
                        else:
                            self.log.write('Step "%s" failed with exception: %s\n    Ignoring due to XFAIL\n' % (
                                self.name, str(err)
                            ))
                else:
                    raise BuildRunnerConfigurationError(
                        (
                            'Step "%s" contains an unknown task "%s"\n'
                        ) % (self.name, _task_name)
                    )
        finally:
            for _task in _tasks:
                try:
                    _task.cleanup(_context)
                except: #pylint: disable=bare-except
                    self.log.write('\nError cleaning up task:\n')
                    traceback.print_exc(file=self.log)
