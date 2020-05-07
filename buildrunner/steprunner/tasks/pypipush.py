"""
Copyright (C) 2019 Adobe
"""
from __future__ import absolute_import

from buildrunner.errors import (
    BuildRunnerConfigurationError,
)
from buildrunner.steprunner.tasks import BuildStepRunnerTask
from buildrunner.utils import is_dict


class PypiPushBuildStepRunnerTask(BuildStepRunnerTask):
    """
    Class used to push the resulting python packages to the given repository.
    """

    def __init__(self, step_runner, config):
        super(PypiPushBuildStepRunnerTask, self).__init__(step_runner, config)

        if not self.step_runner.build_runner.push:
            # Was not invoked with ``--push`` so just skip this.  This avoids twine
            # complaining when the push repository is not configured and the user
            # is not even interested in pushing.
            return

        self._repository = None
        self._username = None
        self._password = None
        self._skip_existing = False

        if is_dict(config):
            if 'repository' not in config:
                raise BuildRunnerConfigurationError(
                    'Pypi push configuration must specify a "repository" attribute'
                )
            self._repository = config['repository']

            if 'username' not in config:
                raise BuildRunnerConfigurationError(
                    'Pypi push configuration must specify a "username" attribute'
                )
            self._username = config['username']

            if 'password' not in config:
                raise BuildRunnerConfigurationError(
                    'Pypi push configuration must specify a "password" attribute'
                )
            self._password = config['password']

            if 'skip_existing' not in config:
                self._skip_existing = config['skip_existing']

        else:
            self._repository = config

        if self._repository not in self.step_runner.build_runner.pypi_packages:
            # Importing here avoids twine dependency when it is unnecessary
            import twine.settings
            try:
                if self._username is not None and self._password is not None:
                    upload_settings = twine.settings.Settings(
                        repository_url=self._repository,
                        username=self._username,
                        password=self._password,
                        disable_progress_bar=True,
                        skip_existing=self._skip_existing,
                    )
                else:
                    upload_settings = twine.settings.Settings(
                        repository_name=self._repository,
                        disable_progress_bar=True,
                        skip_existing=self._skip_existing,
                    )
            except twine.exceptions.InvalidConfiguration as err:
                raise BuildRunnerConfigurationError(
                    (
                        'Pypi is unable to find an entry for "{0}" in your .pypirc.\n'
                        '    See documentation: https://***REMOVED***/xeng/build/tools/pypi-pip.html\n'
                    ).format(self._repository)
                )

            self.step_runner.build_runner.pypi_packages[self._repository] = {
                'upload_settings': upload_settings,
                'packages': [],
            }

    def run(self, context):
        if not self.step_runner.build_runner.push:
            self.step_runner.log.write(
                'Push not requested with "--push": skipping\n'
            )
            return

        self.step_runner.log.write(
            'Preparing resulting packages for push to "%s".\n' % self._repository
        )

        # get python-sdist packages for this step only
        for _artifact, _attributes in self.step_runner.build_runner.artifacts.iteritems():
            if _artifact.startswith(self.step_runner.name + "/") and \
                    'type' in _attributes and \
                    _attributes['type'] == "python-sdist":
                self.step_runner.build_runner.pypi_packages[self._repository]['packages'].append(
                    "{0}/{1}".format(self.step_runner.build_runner.build_results_dir, _artifact)
                )
