"""
Copyright (C) 2015 Adobe
"""
from __future__ import absolute_import
import buildrunner.docker
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
        self._docker_client = buildrunner.docker.new_client(
            timeout=step_runner.build_runner.docker_timeout,
        )
        self.path = None
        self.dockerfile = None
        self.to_inject = {}
        self.image_to_prepend_to_dockerfile = image_to_prepend_to_dockerfile
        self.nocache = False
        self.cache_from = []
        self.pull = True
        self.buildargs = {}
        self._import = None

        if not is_dict(self.config):
            self.path = self.config
            self.config = {}
        else:
            self._import = self.config.get('import', self._import)
            self.path = self.config.get('path', self.path)
            self.dockerfile = self.config.get('dockerfile', self.dockerfile)
            self.nocache = self.config.get('no-cache', self.nocache)
            self.pull = self.config.get('pull', self.pull)

            if not is_dict(self.config.get('buildargs', self.buildargs)):
                raise BuildRunnerConfigurationError(
                    'Step %s:build:buildargs must be a collection/map/dictionary' % self.step_runner
                )

            self.buildargs = self.config.get('buildargs', self.buildargs)

            if not isinstance(self.config.get('cache_from', self.cache_from), list):
                raise BuildRunnerConfigurationError(
                    'Step %s:build:cache_from must be a list' % self.step_runner
                )

            self.cache_from = self.config.get('cache_from', self.cache_from)

            for cache_from_image in self.cache_from:
                try:
                    self._docker_client.pull(cache_from_image)
                    # If the pull is successful, add the image to be cleaned up at the end of the script
                    self.step_runner.build_runner.generated_images.append(cache_from_image)
                    self.step_runner.log.write('Using cache_from image: %s\n' % cache_from_image)
                except:
                    self.step_runner.log.write('WARNING: Unable to pull the cache_from image: %s\n' % cache_from_image)

            if not is_dict(self.config.get('inject', {})):
                raise BuildRunnerConfigurationError(
                    'Step %s:build:inject must be a collection/map/dictionary' % self.step_runner
                )

            for src_glob, dest_dir in self.config.get('inject', {}).iteritems():
                src_glob = self.step_runner.build_runner.to_abs_path(src_glob)
                for source_file in glob.glob(src_glob):
                    self.to_inject[source_file] = os.path.join(
                        '.',
                        dest_dir,
                        os.path.basename(source_file),
                    )

            if not self._import and not any((
                    self.path, self.dockerfile, self.to_inject
            )):
                raise BuildRunnerConfigurationError(
                    'Docker build context must specify a '
                    '"path", "dockerfile", or "inject" attribute'
                )

        if self.path:
            self.path = self.step_runner.build_runner.to_abs_path(self.path)

        if self.path and not os.path.exists(self.path):
            raise BuildRunnerConfigurationError(
                'Step %s:build:path:%s: Invalid build context path' % (
                    self.step_runner, self.path
                ))

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
            context['image'] = DockerImporter(
                self._import,
                timeout=self.step_runner.build_runner.docker_timeout,
            ).import_image()
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
                cache_from=self.cache_from,
                pull=self.pull,
                buildargs=self.buildargs
            )
            if exit_code != 0 or not builder.image:
                raise BuildRunnerProcessingError('Error building image')
        except Exception as exc:
            self.step_runner.log.write('ERROR: {0}\n'.format(exc))
            raise
        finally:
            builder.cleanup()
        context['image'] = builder.image
