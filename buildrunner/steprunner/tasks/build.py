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


    def __init__(
            self,
            step_runner,
            config,
            image_to_prepend_to_dockerfile=None,
    ):
        super(BuildBuildStepRunnerTask, self).__init__(step_runner, config)

        self.path = None
        self.dockerfile = None
        self.to_inject = {}
        self.image_to_prepend_to_dockerfile = image_to_prepend_to_dockerfile
        self.nocache = False
        self.pull = True
        self._import = None
        if is_dict(self.config):
            if 'import' in self.config:
                self._import = self.config['import']
            elif all(prop not in self.config for prop in (
                    'path',
                    'dockerfile',
                    'inject'
            )):
                raise BuildRunnerConfigurationError(
                    'Docker build context must specify a '
                    '"path", "dockerfile", or "inject" attribute'
                )

            if 'path' in self.config:
                self.path = self.config['path']

            if 'dockerfile' in self.config:
                self.dockerfile = self.config['dockerfile']

            if 'no-cache' in self.config:
                self.nocache = self.config['no-cache']

            if 'pull' in self.config:
                self.pull = self.config['pull']

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

        if not self.dockerfile:
            if self.path:
                path_dockerfile = os.path.join(self.path, 'Dockerfile')
                if os.path.exists(path_dockerfile):
                    self.dockerfile = path_dockerfile
            for src_file, dest_file in self.to_inject.iteritems():
                if dest_file in [
                        './Dockerfile',
                        '././Dockerfile',
                        '/Dockerfile',
                ]:
                    self.dockerfile = src_file

        if self.dockerfile:
            _dockerfile_abs_path = self.step_runner.build_runner.to_abs_path(
                self.dockerfile,
            )
            if os.path.exists(_dockerfile_abs_path):
                self.dockerfile = _dockerfile_abs_path
                if self.image_to_prepend_to_dockerfile:
                    # need to load the contents of the Dockerfile so that we
                    # can prepend the image
                    with open(_dockerfile_abs_path, 'r') as _dockerfile:
                        self.dockerfile = _dockerfile.read()

            if self.image_to_prepend_to_dockerfile:
                # prepend the given image to the dockerfile
                self.dockerfile = 'FROM %s\n%s' % (
                    self.image_to_prepend_to_dockerfile,
                    self.dockerfile
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

        if not self.dockerfile:
            raise BuildRunnerConfigurationError(
                'Cannot find a Dockerfile in the given path '
                'or inject configurations'
            )

        self.step_runner.log.write('Running docker build\n')
        builder = DockerBuilder(
            self.path,
            inject=self.to_inject,
            dockerfile=self.dockerfile,
        )
        try:
            exit_code = builder.build(
                console=self.step_runner.log,
                nocache=self.nocache,
                pull=self.pull,
            )
            if exit_code != 0 or not builder.image:
                raise BuildRunnerProcessingError('Error building image')
        except Exception as exc:
            self.step_runner.log.write('ERROR: {0}\n'.format(exc))
            raise
        finally:
            builder.cleanup()
        context['image'] = builder.image
