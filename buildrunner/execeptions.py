"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""


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
