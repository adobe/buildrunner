"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import json
import os
import requests

from buildrunner.errors import BuildRunnerProvisionerError


class SaltProvisioner:
    """
    Provisioner used to apply a salt state defined in the run configuration.
    """

    def __init__(self, sls, console=None):
        self.sls = sls
        self.console = console

    def provision(self, runner):
        """
        Apply the configured salt state, bootstrapping salt if it is not found.
        """
        if self.console:
            self.console.write('Running salt provisioner...\n')

        # see if salt is installed, bootstrap if it isn't
        if runner.run('salt-call -h') != 0:
            # pull bootstrap and run as a script
            bootstrap_response = requests.get('http://bootstrap.saltstack.org', timeout=600)
            if bootstrap_response.status_code != 200:
                raise BuildRunnerProvisionerError(
                    "Unable to get salt bootstrap"
                )
            if self.console:
                self.console.write(
                    'Cannot detect salt installation--bootstrapping...\n'
                )
            runner.run_script(
                bootstrap_response.text,
                args='-X -n',
                console=self.console,
            )
            # we don't rely on the bootstrap return code because the
            # ubuntu/debian install fails because the services aren't
            # registered. just rely on salt-call being present instead
            exit_code = runner.run('salt-call -h')
            if exit_code != 0:
                raise BuildRunnerProvisionerError("Unable to bootstrap salt")

        # create tmp file_root dir and write top.sls and dr.sls there
        file_root_dir = runner.tempfile(suffix='_salt_file_root')
        runner.run(f'mkdir -p {file_root_dir}')
        runner.write_to_container_file(
            'base: {"*": ["dr"]}',
            os.path.join(file_root_dir, 'top.sls'),
        )
        runner.write_to_container_file(
            json.dumps(dict(self.sls)),
            os.path.join(file_root_dir, 'dr.sls'),
        )

        # run a salt-call highstate with the new file_root dir
        salt_call_prefix = ''
        exit_code = runner.run('sudo -h')
        if exit_code == 0:
            salt_call_prefix = 'sudo '
        exit_code = runner.run(
            f'{salt_call_prefix}salt-call --local --file-root={file_root_dir} state.highstate',
            console=self.console,
        )
        if exit_code != 0:
            raise BuildRunnerProvisionerError("Unable to provision with salt")
