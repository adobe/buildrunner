"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from typing import List, Optional

from buildrunner.config.models_step import StepPypiPush
from buildrunner.errors import (
    BuildRunnerConfigurationError,
)
from buildrunner.steprunner.tasks import BuildStepRunnerTask


class PypiRepoDefinition:
    """
    Contains the definition for a PyPi push repository.
    """

    def __init__(
        self,
        repository: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        skip_existing: bool = False,
    ):
        self.repository = repository
        self.username = username
        self.password = password
        self.skip_existing = skip_existing


class PypiPushBuildStepRunnerTask(BuildStepRunnerTask):
    """
    Class used to push the resulting python packages to the given repository.
    """

    def __init__(self, step_runner, pypi_pushes: List[StepPypiPush]):
        super().__init__(step_runner, pypi_pushes[0])

        if not self.step_runner.build_runner.push:
            # Was not invoked with ``--push`` so just skip this.  This avoids twine
            # complaining when the push repository is not configured and the user
            # is not even interested in pushing.
            return

        self._repos = [
            PypiRepoDefinition(
                push.repository,
                push.username,
                push.password,
                push.skip_existing,
            )
            for push in pypi_pushes
        ]

        imported = False
        for repo in self._repos:
            if repo.repository not in self.step_runner.build_runner.pypi_packages:
                if not imported:
                    # Importing here avoids twine dependency when it is unnecessary
                    import twine.settings  # pylint: disable=import-outside-toplevel
                    import twine.exceptions  # pylint: disable=import-outside-toplevel

                    imported = True

                try:
                    if repo.username is not None and repo.password is not None:
                        upload_settings = twine.settings.Settings(
                            repository_url=repo.repository,
                            username=repo.username,
                            password=repo.password,
                            disable_progress_bar=True,
                            skip_existing=repo.skip_existing,
                        )
                    else:
                        upload_settings = twine.settings.Settings(
                            repository_name=repo.repository,
                            disable_progress_bar=True,
                            skip_existing=repo.skip_existing,
                        )
                except twine.exceptions.InvalidConfiguration as twe:
                    raise BuildRunnerConfigurationError(
                        f'Pypi is unable to find an entry for "{repo.repository}" in your .pypirc.\n'
                    ) from twe

                self.step_runner.build_runner.pypi_packages[repo.repository] = {
                    "upload_settings": upload_settings,
                    "packages": [],
                }

    def run(self, context):
        if not self.step_runner.build_runner.push:
            self.step_runner.log.write('Push not requested with "--push": skipping\n')
            return

        self.step_runner.log.write(
            f"Preparing resulting packages for push to {'/'.join(repo.repository for repo in self._repos)}.\n"
        )

        # get python-sdist packages for this step only
        for _artifact, _attributes in self.step_runner.build_runner.artifacts.items():
            if (
                _artifact.startswith(self.step_runner.name + "/")
                and _attributes
                and "type" in _attributes
                and _attributes["type"] in ("python-wheel", "python-sdist")
            ):
                for repo in self._repos:
                    self.step_runner.build_runner.pypi_packages[repo.repository][
                        "packages"
                    ].append(
                        f"{self.step_runner.build_runner.build_results_dir}/{_artifact}"
                    )
