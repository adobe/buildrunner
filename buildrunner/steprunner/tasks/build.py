"""
Copyright (C) 2015 Adobe
"""
from __future__ import absolute_import
import glob
import os

from buildrunner.docker.importer import DockerImporter
from buildrunner.docker.builder import DockerBuilder
from buildrunner.errors import (
    BuildRunnerConfigurationError,
    BuildRunnerProcessingError,
)
from buildrunner.steprunner.tasks import BuildStepRunnerTask
from buildrunner.utils import is_dict


class BuildBuildStepRunnerTask(BuildStepRunnerTask):
    """
    Class used to manage "build" build tasks.
    """


    def __init__(self, step_runner, config):
        super(BuildBuildStepRunnerTask, self).__init__(step_runner, config)

        self.path = None
        self.to_inject = {}
        self.nocache = False
        self._import = None
        if is_dict(self.config):
            if 'import' in self.config:
                self._import = self.config['import']
            elif 'path' not in self.config and 'inject' not in self.config:
                raise BuildRunnerConfigurationError(
                    'Docker build context must specify a '
                    '"path" or "inject" attribute'
                )

            if 'path' in self.config:
                self.path = self.config['path']

            if 'no-cache' in self.config:
                self.nocache = self.config['no-cache']

            if 'inject' in self.config and is_dict(self.config['inject']):
                for src_glob, dest_dir in self.config['inject'].iteritems():
                    src_glob = self.step_runner.build_runner.to_abs_path(
                        src_glob,
                    )
                    for source_file in glob.glob(src_glob):
                        self.to_inject[source_file] = os.path.join(
                            '.',
                            dest_dir,
                            os.path.basename(source_file),
                        )
        else:
            self.path = self.config

        if self.path:
            self.path = self.step_runner.build_runner.to_abs_path(self.path)

        if self.path and not os.path.exists(self.path):
            raise BuildRunnerConfigurationError(
                'Invalid build context path "%s"' % self.path
            )


    def run(self, context):
        # 'import' will override other configuration and perform a 'docker
        # import'
        if self._import:
            self.step_runner.log.write('  Importing %s as a Docker image\n' % (
                self._import,
            ))
            context['image'] = DockerImporter(self._import).import_image()
            return

        self.step_runner.log.write('Running docker build\n')
        builder = DockerBuilder(
            self.path,
            inject=self.to_inject,
        )
        try:
            exit_code = builder.build(
                console=self.step_runner.log,
                nocache=self.nocache,
            )
            if exit_code != 0 or not builder.image:
                raise BuildRunnerProcessingError('Error building image')
        finally:
            builder.cleanup()
        context['image'] = builder.image
