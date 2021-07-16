"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import os
from io import StringIO

from fabric import Connection

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
        super().__init__(step_runner, config)

        # must have a 'host' attribute
        if 'host' not in self.config:
            raise BuildRunnerConfigurationError(
                f'Step "{self.step_runner.name}" has a "remote" configuration without a "host" attribute\n'
            )
        self.host = self.step_runner.build_runner.get_build_server_from_alias(
            self.config['host'],
        )

        # must specify the cmd to run
        if 'cmd' not in self.config:
            raise BuildRunnerConfigurationError(
                f'Step "{self.step_runner.name}" has a "remote" configuration without a "cmd" attribute\n'
            )
        self.cmd = self.config['cmd']

        self.artifacts = self.config.get('artifacts', {})

    def run(self, context):  # pylint: disable=unused-argument,too-many-branches,too-many-locals
        self.step_runner.log.write(
            f"Building on remote host {self.host}\n\n"
        )

        # call remote functions to copy tar and build remotely
        remote_build_dir = f'/tmp/buildrunner/{self.step_runner.build_runner.build_id}-{self.step_runner.name}'
        remote_archive_filepath = remote_build_dir + '/source.tar'
        self.step_runner.log.write(
            f"[{self.host}] Creating temporary remote directory '{remote_build_dir}'\n"
        )

        with Connection(self.host) as connection:
            mkdir_result = connection.run(
                f"mkdir -p {remote_build_dir}",
                warn=True,
                out_stream=self.step_runner.log,
                err_stream=self.step_runner.log,
            )
            if mkdir_result.return_code:
                raise BuildRunnerProcessingError(
                    "Error creating remote directory"
                )

            try:  # pylint: disable=too-many-nested-blocks
                self.step_runner.log.write(
                    f"[{self.host}] Pushing archive file to remote directory\n"
                )
                files = connection.put(
                    self.step_runner.build_runner.get_source_archive_path(),
                    remote_archive_filepath,
                )
                if files:
                    self.step_runner.log.write(
                        f"[{self.host}] Extracting source tree archive on remote host:\n"
                    )
                    extract_result = connection.run(
                        f"(cd {remote_build_dir}; tar -xvf source.tar && rm -f source.tar)",
                        warn=True,
                        out_stream=self.step_runner.log,
                        err_stream=self.step_runner.log,
                    )
                    if extract_result.return_code:
                        raise BuildRunnerProcessingError(
                            "Error extracting archive file"
                        )

                    self.step_runner.log.write(f"[{self.host}] Running command '{self.cmd}'\n")
                    package_result = connection.run(
                        f"(cd {remote_build_dir}; {self.cmd})",
                        warn=True,
                        out_stream=self.step_runner.log,
                        err_stream=self.step_runner.log,
                    )

                    if self.artifacts:
                        _arts = []
                        for _art, _props in self.artifacts.items():
                            # check to see if there are artifacts
                            # that match the pattern
                            dummy_out = StringIO()
                            art_result = connection.run(
                                f'ls -A1 {remote_build_dir}/{_art}',
                                hide=True,
                                warn=True,
                                out_stream=dummy_out,
                                err_stream=dummy_out,
                            )
                            if art_result.return_code:
                                continue

                            # we have at least one match--run the get
                            for _ca in connection.get(  # pylint: disable=not-an-iterable
                                    f"{remote_build_dir}/{_art}",
                                    f"{self.step_runner.results_dir}/%(basename)s"
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
                                f'- found {os.path.basename(_art)}\n',
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
                    f"[{self.host}] Cleaning up remote temp directory {remote_build_dir}\n"
                )
                cleanup_result = connection.run(
                    f"rm -Rf {remote_build_dir}",
                    out_stream=self.step_runner.log,
                    err_stream=self.step_runner.log,
                )
                if cleanup_result.return_code:
                    raise BuildRunnerProcessingError(
                        "Error cleaning up remote directory"
                    )
