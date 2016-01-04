"""
Copyright (C) 2015 Adobe
"""
from __future__ import absolute_import
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
        for _type, _value in provisioners_config.iteritems():
            if _type in PROVISIONERS:
                _provisioners.append(
                    PROVISIONERS[_type](_value, console=logger)
                )
            else:
                raise BuildRunnerProvisionerError(
                    'Unknown provisioner type "%s"' % _type
                )

    return _provisioners
