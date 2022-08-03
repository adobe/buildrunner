"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""


class BuildRunnerError(Exception):
    """Base BuildRunner Exception"""
    pass


class BuildRunnerProtocolError(BuildRunnerError):
    """Error with unhandled state in protocol"""
    pass


class BuildRunnerConfigurationError(BuildRunnerError):
    """Error indicating an issue with the build configuration"""
    pass


class BuildRunnerProcessingError(BuildRunnerError):
    """Error indicating the build should be 'failed'"""
    pass


class BuildRunnerProvisionerError(BuildRunnerError):
    """Error indicating an issue with a provisioner"""
    pass


class BuildRunnerVersionError(Exception):
    """
    Exception class for invalid buildrunner version
    """
    pass


class ConfigVersionFormatError(Exception):
    """
    Exception class for invalid config version format
    """
    pass


class ConfigVersionTypeError(Exception):
    """
    Exception class for invalid config version type
    """
    pass
