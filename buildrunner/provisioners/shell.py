"""
Copyright (C) 2014 Adobe
"""
from buildrunner.provisioners import BuildRunnerProvisionerError


class ShellProvisioner(object):
    """
    Provisioner used to run a shell script.
    """


    def __init__(self, script, shell='/bin/sh', console=None):
        self.script = script
        self.shell = shell
        self.console = console


    def provision(self, runner):
        """
        Run the shell script as a provisioner, with the given shell.
        """
        if self.console:
            self.console.write('Running shell provisioner...\n')
        exit_code = runner.run_script(
            self.script,
            shell=self.shell,
            console=self.console,
        )
        if exit_code != 0:
            raise BuildRunnerProvisionerError("Shell provisioner failed")
