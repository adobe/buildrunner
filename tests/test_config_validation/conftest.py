import os
from typing import Callable, List, Optional, Tuple, Union

import pytest
import yaml

from buildrunner.config.models import (
    generate_and_validate_config,
    generate_and_validate_global_config,
)


@pytest.fixture(autouse=True)
def set_cwd():
    # Some of the validation tests rely on loading the Dockerfiles in the correct directories, so set the path to the
    # top-level project folder (i.e. the root of the repository)
    os.chdir(os.path.realpath(os.path.join(os.path.dirname(__file__), "../..")))


def _validate_and_assert_internal(
    config_data: Union[str, dict],
    error_matches: List[str],
    generate_and_validate: Callable,
) -> Tuple[Optional[dict], Optional[List[str]]]:
    if isinstance(config_data, str):
        config_data = yaml.load(config_data, Loader=yaml.Loader)
    config, errors = generate_and_validate(**config_data)
    if error_matches:
        assert not config
        assert errors
        assert len(errors) == len(error_matches)
        for index, error_match in enumerate(error_matches):
            assert error_match in errors[index]
    else:
        assert not errors
        assert config
    return config, errors


@pytest.fixture()
def assert_generate_and_validate_config_errors():
    def _func(config_data: Union[str, dict], error_matches: List[str]):
        return _validate_and_assert_internal(
            config_data, error_matches, generate_and_validate_config
        )

    return _func


@pytest.fixture()
def assert_generate_and_validate_global_config_errors():
    def _func(config_data: Union[str, dict], error_matches: List[str]):
        return _validate_and_assert_internal(
            config_data, error_matches, generate_and_validate_global_config
        )

    return _func
