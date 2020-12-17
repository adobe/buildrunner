"""
Copyright (C) 2020 Adobe
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


# Local Variables:
# fill-column: 100
# End:
