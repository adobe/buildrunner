import os
import tempfile
import unittest
from collections import OrderedDict

import pytest
from buildrunner.config import (
    BuildRunnerConfig,
    BuildRunnerVersionError,
    ConfigVersionFormatError,
    ConfigVersionTypeError,
)

buildrunner_version = '2.0.701'
config_version = '2.0'


@pytest.fixture(name="config")
def fixture_config_file():
    config = OrderedDict({'version': config_version})
    yield config


@pytest.fixture(name="version_file")
def fixture_setup_version_file():
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        version_file = f"{tmp_dir_name}/version.py"

        with open(version_file,'w') as file:
            file.write(f"__version__ = '{buildrunner_version}'")

        yield version_file


def test_valid_version_file(config, version_file):
        BuildRunnerConfig._validate_version(config=config, version_file_path=f"{version_file}")


def test_missing_version_file(config, version_file):
    # No exception for a missing version file it just prints a warning
    BuildRunnerConfig._validate_version(config=config, version_file_path=f"{version_file}-bogus")


def test_missing_version_in_version_file(config, version_file):
    with open(version_file,'w') as file:
        file.truncate()

    with pytest.raises(BuildRunnerVersionError) as file_error:
        BuildRunnerConfig._validate_version(config=config, version_file_path=f"{version_file}")


def test_invalid_delim_version(config, version_file):
    with open(version_file,'w') as file:
        file.truncate()
        file.write(f"__version__: '1.3.4'")

    with pytest.raises(ConfigVersionFormatError) as file_error:
        BuildRunnerConfig._validate_version(config=config, version_file_path=f"{version_file}")


def test_invalid_config_number_version(config, version_file):
    with open(version_file,'w') as file:
        file.truncate()
        file.write(f"__version__ = '1'")

    with pytest.raises(ConfigVersionFormatError) as file_error:
        BuildRunnerConfig._validate_version(config=config, version_file_path=f"{version_file}")


def test_invalid_config_version_type(config, version_file):
    with open(version_file,'w') as file:
        file.truncate()
        file.write(f"__version__ = 'two.zero.five'")

    with pytest.raises(ConfigVersionTypeError) as file_error:
        BuildRunnerConfig._validate_version(config=config, version_file_path=f"{version_file}")


def test_bad_version(config, version_file):
    config = OrderedDict({'version': 2.1})

    with pytest.raises(ConfigVersionFormatError) as file_error:
        BuildRunnerConfig._validate_version(config=config, version_file_path=f"{version_file}")
