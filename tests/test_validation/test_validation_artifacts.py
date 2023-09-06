
import yaml
from buildrunner.validation.config import validate_config, Errors


def test_step_remote_artifacts_valid():
    config_yaml = """
    steps:
      build-remote:
        remote:
          host: myserver.ut1
          cmd: docker build -t mytest-reg/buildrunner-test .
          artifacts:
            bogus/path/to/artifacts/*:
              type: tar
              compression: lzma
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_step_run_artifacts_valid():
    config_yaml = """
    steps:
      build-run:
        run:
          artifacts:
            bogus/path/to/artifacts/*:
              type: zip
              compression: lzma
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    print(errors)
    assert errors is None


def test_step_artifacts_valid_compression():
    config_yaml = """
    steps:
      build-remote:
        remote:
          host: myserver.ut1
          cmd: docker build -t mytest-reg/buildrunner-test .
          artifacts:
            bogus/path/to/artifacts/*:
              type: tar
              compression: gz
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_step_artifacts_invalid_compression():
    config_yaml = """
    steps:
      build-remote:
        remote:
          host: myserver.ut1
          cmd: docker build -t mytest-reg/buildrunner-test .
          artifacts:
            bogus/path/to/artifacts/*:
              type: tar
              compression: bogus
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_step_run_format_valid():
    config_yaml = """
    steps:
      build-run:
        run:
          artifacts:
            bogus/path/to/artifacts/*:
              format: uncompressed
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_step_run_format_invalid():
    config_yaml = """
    steps:
      build-run:
        run:
          artifacts:
            bogus/path/to/artifacts/*:
              format: 134
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_step_type_valid():
    #  Checks zip type
    config_yaml = """
    steps:
      build-run:
        run:
          artifacts:
            bogus/path/to/artifacts/*:
              type: zip
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None

    # Checks tar type
    config_yaml = """
    steps:
      build-run:
        run:
          artifacts:
            bogus/path/to/artifacts/*:
              type: tar
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_push_invalid():
    config_yaml = """
    steps:
      build-run:
        run:
          artifacts:
            bogus/path/to/artifacts/*:
              push: bogus
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_push_valid():
    config_yaml = """
    steps:
      build-run:
        run:
          artifacts:
            bogus/path/to/artifacts/*:
              push: True
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_valid_extra_properties():
    config_yaml = """
    steps:
      build-run:
        run:
          artifacts:
            bogus/path/to/artifacts/*:
              push: True
              something_else: awesome data
              something_else2: True
              something_else3: 123
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None
