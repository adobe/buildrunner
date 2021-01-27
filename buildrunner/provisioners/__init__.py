"""
Copyright (C) 2020 Adobe
"""

from buildrunner.errors import BuildRunnerProvisionerError

from buildrunner.provisioners.salt import SaltProvisioner
from buildrunner.provisioners.shell import ShellProvisioner

PROVISIONERS = {
    'shell': ShellProvisioner,
    'salt': SaltProvisioner,
}


def create_provisioners(provisioners_config, logger):
    """
    Given provisioners config return a list of provisioner objects.
    """
    _provisioners = []

    if provisioners_config:
        for _type, _value in provisioners_config.items():
            if _type in PROVISIONERS:
                _provisioners.append(
                    PROVISIONERS[_type](_value, console=logger)
                )
            else:
                raise BuildRunnerProvisionerError(f'Unknown provisioner type "{_type}"')

    return _provisioners
