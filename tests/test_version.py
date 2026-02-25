from collections import OrderedDict

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


@pytest.fixture(name="version_file", autouse=True)
def fixture_setup_version_file(tmp_path):
    version_file = tmp_path / "version.py"
    version_file.write_text(f"__version__ = '{buildrunner_version}'")
    original_path = loader.VERSION_FILE_PATH
    loader.VERSION_FILE_PATH = str(version_file)
    yield str(version_file)
    loader.VERSION_FILE_PATH = original_path


def test_valid_version_file(config):
    loader._validate_version(config=config)


def test_missing_version_file(config):
    # No exception for a missing version file it just prints a warning
    loader.VERSION_FILE_PATH = "bogus"
    loader._validate_version(config=config)


def test_missing_version_in_version_file(config, version_file):
    with open(version_file, "w") as file:
        file.truncate()

    with pytest.raises(BuildRunnerVersionError):
        loader._validate_version(config=config)


def test_invalid_delim_version(config, version_file):
    with open(version_file, "w") as file:
        file.truncate()
        file.write("__version__: '1.3.4'")

    with pytest.raises(ConfigVersionFormatError):
        loader._validate_version(config=config)


def test_invalid_config_number_version(config, version_file):
    with open(version_file, "w") as file:
        file.truncate()
        file.write("__version__ = '1'")

    with pytest.raises(ConfigVersionFormatError):
        loader._validate_version(config=config)


def test_invalid_config_version_type(config, version_file):
    with open(version_file, "w") as file:
        file.truncate()
        file.write("__version__ = 'two.zero.five'")

    with pytest.raises(ConfigVersionTypeError):
        loader._validate_version(config=config)


def test_bad_version(config):
    config = OrderedDict({"version": 2.1})

    with pytest.raises(ConfigVersionFormatError):
        loader._validate_version(config=config)
