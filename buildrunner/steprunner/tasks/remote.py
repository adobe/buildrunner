"""
Copyright (C) 2015 Adobe
"""

import os
from io import StringIO

import fabric.tasks
from fabric.api import hide, run, put, get
from fabric.context_managers import settings

from buildrunner.errors import (
    BuildRunnerConfigurationError,
    BuildRunnerProcessingError,
)
from buildrunner.steprunner.tasks import BuildStepRunnerTask


class RemoteBuildStepRunnerTask(BuildStepRunnerTask):
    """
    Class used to manage "remote" build tasks.
    """


    def __init__(self, step_runner, config):
        super(RemoteBuildStepRunnerTask, self).__init__(step_runner, config)

        # must have a 'host' attribute
        if 'host' not in self.config:
            raise BuildRunnerConfigurationError(
                'Step "%s" has a "remote" configuration without '
                'a "host" attribute\n' % self.step_runner.name
            )
        self.host = self.step_runner.build_runner.get_build_server_from_alias(
            self.config['host'],
        )

        # must specify the cmd to run
        if 'cmd' not in self.config:
            raise BuildRunnerConfigurationError(
                'Step "%s" has a "remote" configuration without a'
                '"cmd" attribute\n' % self.step_runner.name
            )
        self.cmd = self.config['cmd']

        self.artifacts = self.config.get('artifacts', {})


    def run(self, step_context): #pylint: disable=unused-argument
        self.step_runner.log.write(
            "Building on remote host %s\n\n" % self.host
        )
        fabric.tasks.execute(
            fabric.tasks.WrappedCallableTask(self._run),
            hosts=[self.host],
        )


    def _run(self):
        """
        Routine run by fabric.
        """
        # call remote functions to copy tar and build remotely

        remote_build_dir = '/tmp/buildrunner/%s-%s' % (
            self.step_runner.build_runner.build_id,
            self.step_runner.name,
        )
        remote_archive_filepath = remote_build_dir + '/source.tar'
        self.step_runner.log.write(
            "[%s] Creating temporary remote directory '%s'\n" % (
                self.host,
                remote_build_dir,
            )
        )

        mkdir_result = run(
            "mkdir -p %s" % remote_build_dir,
            warn_only=True,
            stdout=self.step_runner.log,
            stderr=self.step_runner.log,
        )
        if mkdir_result.return_code:
            raise BuildRunnerProcessingError(
                "Error creating remote directory"
            )

        try:
            self.step_runner.log.write(
                "[%s] Pushing archive file to remote directory\n" % (
                    self.host,
                )
            )
            files = put(
                self.step_runner.build_runner.get_source_archive_path(),
                remote_archive_filepath,
            )
            if files:
                self.step_runner.log.write(
                    "[%s] Extracting source tree archive on "
                    "remote host:\n" % self.host
                )
                extract_result = run(
                    "(cd %s; tar -xvf source.tar && "
                    "rm -f source.tar)" % (
                        remote_build_dir,
                    ),
                    warn_only=True,
                    stdout=self.step_runner.log,
                    stderr=self.step_runner.log,
                )
                if extract_result.return_code:
                    raise BuildRunnerProcessingError(
                        "Error extracting archive file"
                    )
                else:
                    self.step_runner.log.write("[%s] Running command '%s'\n" % (
                        self.host,
                        self.cmd,
                    ))
                    package_result = run(
                        "(cd %s; %s)" % (
                            remote_build_dir,
                            self.cmd,
                        ),
                        warn_only=True,
                        stdout=self.step_runner.log,
                        stderr=self.step_runner.log,
                    )

                    if self.artifacts:
                        _arts = []
                        for _art, _props in self.artifacts.items():
                            # check to see if there are artifacts
                            # that match the pattern
                            with hide('everything'): #pylint: disable=not-context-manager
                                dummy_out = StringIO()
                                art_result = run(
                                    'ls -A1 %s/%s' % (
                                        remote_build_dir,
                                        _art,
                                    ),
                                    warn_only=True,
                                    stdout=dummy_out,
                                    stderr=dummy_out,
                                )
                                if art_result.return_code:
                                    continue

                            # we have at least one match--run the get
                            with settings(warn_only=True):
                                for _ca in get(
                                        "%s/%s" % (
                                            remote_build_dir,
                                            _art,
                                        ),
                                        "%s/%%(basename)s" % (
                                            self.step_runner.results_dir,
                                        )
                                ):
                                    _arts.append(_ca)
                                    self.step_runner.build_runner.add_artifact(
                                        os.path.join(
                                            self.step_runner.name,
                                            os.path.basename(_ca),
                                        ),
                                        _props,
                                    )
                        self.step_runner.log.write("\nGathered artifacts:\n")
                        for _art in _arts:
                            self.step_runner.log.write(
                                '- found %s\n' % os.path.basename(_art),
                            )
                        self.step_runner.log.write("\n")


                    if package_result.return_code:
                        raise BuildRunnerProcessingError(
                            "Error running remote build"
                        )

            else:
                raise BuildRunnerProcessingError(
                    "Error uploading source archive to host"
                )
        finally:
            self.step_runner.log.write(
                "[%s] Cleaning up remote temp directory %s\n" % (
                    self.host,
                    remote_build_dir,
                )
            )
            cleanup_result = run(
                "rm -Rf %s" % remote_build_dir,
                stdout=self.step_runner.log,
                stderr=self.step_runner.log,
            )
            if cleanup_result.return_code:
                raise BuildRunnerProcessingError(
                    "Error cleaning up remote directory"
                )
