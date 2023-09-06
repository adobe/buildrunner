
import yaml
from buildrunner.validation.config import validate_config, Errors


def test_platform_and_platforms_invalid():
    # Invalid to have platform and platforms
    config_yaml = """
    steps:
      build-container-multi-platform:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
          platform: linux/amd64
          platforms:
            - linux/amd64
            - linux/arm64
        push:
          repository: mytest-reg/buildrunner-test-multi-platform
          tags:
            - latest
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_platforms_invalid():
    # Invalid to have platforms as a string, it should be a list
    config_yaml = """
    steps:
      build-container-multi-platform:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
          platforms: linux/amd64
        push:
          repository: mytest-reg/buildrunner-test-multi-platform
          tags:
            - latest
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 2


def test_build_is_path():
    config_yaml = """
    steps:
      build-is-path:
        build: .
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_valid_platforms():
    config_yaml = """
    steps:
      build-container-multi-platform:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
          platforms:
            - linux/amd64
            - linux/arm64
        push:
          repository: mytest-reg/buildrunner-test-multi-platform
          tags:
            - latest
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_duplicate_mp_tags_dictionary_invalid():
    # Invalid to have duplicate multi-platform tag
    config_yaml = """
    steps:
      build-container-multi-platform1:
        build:
          platforms:
            - linux/amd64
            - linux/arm64
        push:
          repository: mytest-reg/buildrunner-test-multi-platform
          tags:
            - latest
      build-container-multi-platform2:
        build:
          platforms:
            - linux/amd64
            - linux/arm64
        push:
          repository: mytest-reg/buildrunner-test-multi-platform
          tags:
            - latest
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_duplicate_mp_tags_strings_invalid():
    # Invalid to have duplicate multi-platform tag
    # Testing with both string format, one inferred 'latest' the other explicit 'latest'
    config_yaml = """
    steps:
      build-container-multi-platform1:
        build:
          platforms:
            - linux/amd64
            - linux/arm64
        push: mytest-reg/buildrunner-test-multi-platform
      build-container-multi-platform2:
        build:
          platforms:
            - linux/amd64
            - linux/arm64
        push: mytest-reg/buildrunner-test-multi-platform:latest
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1

    # Indentical tags in same string format
    config_yaml = """
    steps:
      build-container-multi-platform1:
        build:
          platforms:
            - linux/amd64
            - linux/arm64
        push: mytest-reg/buildrunner-test-multi-platform:latest
      build-container-multi-platform2:
        build:
          platforms:
            - linux/amd64
            - linux/arm64
        push: mytest-reg/buildrunner-test-multi-platform:latest
    """
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_duplicate_mp_tags_strings_valid():
    #  Same string format but different MP tags
    config_yaml = """
    steps:
      build-container-multi-platform1:
        build:
          platforms:
            - linux/amd64
            - linux/arm64
        push: mytest-reg/buildrunner-test-multi-platform:latest
      build-container-multi-platform2:
        build:
          platforms:
            - linux/amd64
            - linux/arm64
        push: mytest-reg/buildrunner-test-multi-platform:not-latest
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_duplicate_mp_tags_platform_platforms_invalid():
    # Invalid to have duplicate multi-platform tag and single platform tag
    config_yaml = """
    steps:
      build-container-multi-platform1:
        build:
          platforms:
            - linux/amd64
            - linux/arm64
        push: mytest-reg/buildrunner-test-multi-platform:latest
      build-container-single-platform:
        build:
          platform: linux/arm64
        push: mytest-reg/buildrunner-test-multi-platform:latest
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_step_remote_valid():
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


def test_step_remote_missing_cmd():
    config_yaml = """
    steps:
      build-remote:
        remote:
          host: myserver.ut1
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_commit():
    config_yaml = """
    steps:
      step1:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
        commit:
          repository: mytest-reg/image1
          tags:
            - latest
      step2:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
        commit: mytest-reg/image1
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_pypi_push():
    config_yaml = """
    steps:
      pypi1:
        run:
          image: python:2
          cmds:
            - python setup.py sdist
          artifacts:
            "dist/*.tar.gz": { type: 'python-sdist' }
        pypi-push: artifactory-releng
      pypi2:
        run:
          image: python:2
          cmds:
            - python -m build
          artifacts:
            "dist/*.tar.gz": { type: 'python-sdist' }
            "dist/*.whl": { type: 'python-wheel' }
        pypi-push:
          repository: https://artifactory.example.com/artifactory/api/pypi/pypi-myownrepo
          username: myuser
          password: mypass
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None
