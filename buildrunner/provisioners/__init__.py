"""
Copyright (C) 2014 Adobe
"""
from buildrunner import BuildRunnerError


class BuildRunnerProvisionerError(BuildRunnerError):
    """Error indicating an issue with the build configuration"""
    pass


def create_provisioners(provisioners_config, logger):
    """
    Given provisioners config return a list of provisioner objects.
    """
    _provisioners = []

    if provisioners_config:
        for _type, _value in provisioners_config.iteritems():
            _prov = None
            if 'shell' == _type:
                _prov = ShellProvisioner(_value, console=logger)
            elif 'salt' == _type:
                _prov = SaltProvisioner(_value, console=logger)
            else:
                raise BuildRunnerProvisionerError(
                    'Unknown provisioner type "%s"' % _type
                )

            if _prov:
                _provisioners.append(_prov)

    return _provisioners


from buildrunner.provisioners.salt import SaltProvisioner
from buildrunner.provisioners.shell import ShellProvisioner
