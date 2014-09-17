"""
Copyright (C) 2014 Adobe
"""
import os
import requests
import yaml

from buildrunner.provisioners import BuildRunnerProvisionerError


class SaltProvisioner(object):
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
            bootstrap_response = requests.get('http://bootstrap.saltstack.org')
            if 200 != bootstrap_response.status_code:
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
        os.mkdir(file_root_dir)
        with open(os.path.join(file_root_dir, 'top.sls'), 'w') as top_fd:
            top_fd.write('base: {"*": ["dr"]}')
        with open(os.path.join(file_root_dir, 'dr.sls'), 'w') as dr_fd:
            dr_fd.write(yaml.dump(dict(self.sls)))

        # run a salt-call highstate with the new file_root dir
        salt_call_prefix = ''
        exit_code = runner.run('sudo -h')
        if exit_code == 0:
            salt_call_prefix = 'sudo '
        exit_code = runner.run(
            '%ssalt-call --local --file-root=%s state.highstate' % (
                salt_call_prefix,
                runner.map_local_path(file_root_dir)
            ),
            console=self.console,
        )
        if exit_code != 0:
            raise BuildRunnerProvisionerError("Unable to provision with salt")
