"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

from buildrunner.errors import BuildRunnerProvisionerError


class ShellProvisioner:
    """
    Provisioner used to run a shell script.
    """

    def __init__(self, script, console=None):
        self.script = script
        self.console = console

    def provision(self, runner):
        """
        Run the shell script as a provisioner, with the given shell.
        """
        if self.console:
            self.console.write('Running shell provisioner...\n')
        exit_code = runner.run_script(
            self.script,
            console=self.console,
        )
        if exit_code != 0:
            raise BuildRunnerProvisionerError("Shell provisioner failed")
