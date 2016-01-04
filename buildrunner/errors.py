"""
Copyright (C) 2014 Adobe
"""
from __future__ import absolute_import

class BuildRunnerError(Exception):
    """Base BuildRunner Exception"""
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
