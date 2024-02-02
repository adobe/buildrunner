import os
from typing import List, Union

import pytest
import yaml

from buildrunner.validation.config import generate_and_validate_config, Errors


@pytest.fixture(autouse=True)
def set_cwd():
    # Some of the validation tests rely on loading the Dockerfiles in the correct directories, so set the path to the
    # top-level project folder (i.e. the root of the repository)
    os.chdir(os.path.realpath(os.path.join(os.path.dirname(__file__), "../..")))


@pytest.fixture()
def assert_generate_and_validate_config_errors():
    def _func(config_data: Union[str, dict], error_matches: List[str]):
        if isinstance(config_data, str):
            config_data = yaml.load(config_data, Loader=yaml.Loader)
        config, errors = generate_and_validate_config(**config_data)
        if error_matches:
            assert not config
            assert isinstance(errors, Errors)
            for index, error_match in enumerate(error_matches):
                assert error_match in errors.errors[index].message
        else:
            assert config
            assert not errors

    return _func
