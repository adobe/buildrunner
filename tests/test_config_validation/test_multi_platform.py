import yaml
from buildrunner.validation.config import validate_config, Errors


def test_no_run_with_multiplatform_build():
    # Run in multi platform build is not supported
    config_yaml = """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM {{ DOCKER_REGISTRY }}/busybox:latest
                platforms:
                    - linux/amd64
                    - linux/arm64/v8
            push:
                repository: user1/buildrunner-test-multi-platform
                tags: []
            run:
                image: user1/buildrunner-test-multi-platform
                cmd: echo "Hello World"
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_no_run_with_single_build():
    # Run in single platform build is supported
    config_yaml = """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM {{ DOCKER_REGISTRY }}/busybox:latest
            push:
                repository: user1/buildrunner-test-multi-platform
                tags: []
            run:
                image: user1/buildrunner-test-multi-platform
                cmd: echo "Hello World"
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None
