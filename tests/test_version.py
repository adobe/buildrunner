from collections import OrderedDict
from unittest.mock import patch

import pytest
from buildrunner.config import loader
from buildrunner.config.loader import (
    BuildRunnerVersionError,
    ConfigVersionFormatError,
    ConfigVersionTypeError,
)

buildrunner_version = "2.0.701"
config_version = "2.0"


@pytest.fixture(name="config")
def fixture_config_file():
    config = OrderedDict({"version": config_version})
    yield config


def test_valid_version(config):
    """Valid config version (<= buildrunner version) passes validation."""
    with patch("buildrunner.__version__", buildrunner_version):
        loader._validate_version(config=config)


def test_development_version_skips_validation(config):
    """When buildrunner version is DEVELOPMENT, validation is skipped with a warning."""
    with patch("buildrunner.__version__", "DEVELOPMENT"):
        loader._validate_version(config=config)


def test_single_component_version_raises(config):
    """Single-component buildrunner version (e.g. '1') raises BuildRunnerVersionError."""
    with patch("buildrunner.__version__", "1"):
        with pytest.raises(BuildRunnerVersionError):
            loader._validate_version(config=config)


def test_config_version_higher_than_buildrunner_raises(config):
    """Config version higher than buildrunner version raises ConfigVersionFormatError."""
    with patch("buildrunner.__version__", "1.3.4"):
        config_high = OrderedDict({"version": "99.0"})
        with pytest.raises(ConfigVersionFormatError):
            loader._validate_version(config=config_high)


def test_invalid_config_version_type(config):
    """Non-numeric buildrunner version component raises ConfigVersionTypeError when comparing."""
    with patch("buildrunner.__version__", "two.zero.five"):
        with pytest.raises(ConfigVersionTypeError):
            loader._validate_version(config=config)


def test_bad_version(config):
    """Config version 2.1 when buildrunner is 2.0 raises ConfigVersionFormatError."""
    with patch("buildrunner.__version__", "2.0.0"):
        config_bad = OrderedDict({"version": 2.1})
        with pytest.raises(ConfigVersionFormatError):
            loader._validate_version(config=config_bad)
