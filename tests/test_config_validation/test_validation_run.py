
from buildrunner.validation.config import validate_config, Errors
import yaml


def test_step_run_artifacts_valid():
    config_yaml = """
    steps:
      build-run:
        run:
          image: mytest-reg/buildrunner-test
          artifacts:
            bogus/path/to/artifacts/*:
              type: zip
              compression: lzma
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_push_valid():
    config_yaml = """
    steps:
      build-run:
        run:
          artifacts:
            bogus/path/to/artifacts/*:
              type: zip
              compression: lzma
              push: True
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_push_invalid():
    # Push must be a boolean
    config_yaml = """
    steps:
      build-run:
        run:
          artifacts:
            bogus/path/to/artifacts/*:
              type: zip
              compression: lzma
              push: 1212
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1
