import yaml
from buildrunner.validation.config import validate_config, Errors, RETAG_ERROR_MESSAGE


def test_invalid_multiplatform_retagging_with_push():
    # Retagging a multiplatform image is not supported
    config_yaml = """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM busybox:latest
                platforms:
                    - linux/amd64
                    - linux/arm64/v8
            push: user1/buildrunner-multi-platform-image:latest
        retag-multi-platform-image:
            run:
                image: user1/buildrunner-multi-platform-image:latest
                cmd: echo "Hello World"
            push: user1/buildrunner-multi-platform-image2:latest
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1

def test_invalid_multiplatform_retagging_latest_tag():
    # Retagging a multiplatform image is not supported
    # Tests adding 'latest' tag when left out

    # Tests adding 'latest' tag to build.push
    config_yaml = """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM busybox:latest
                platforms:
                    - linux/amd64
                    - linux/arm64/v8
            push: user1/buildrunner-multi-platform-image
        retag-multi-platform-image:
            run:
                image: user1/buildrunner-multi-platform-image:latest
                cmd: echo "Hello World"
            push: user1/buildrunner-multi-platform-image2
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1

    # Tests adding 'latest' tag to run.image
    config_yaml = """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM busybox:latest
                platforms:
                    - linux/amd64
                    - linux/arm64/v8
            push: user1/buildrunner-multi-platform-image:latest
        retag-multi-platform-image:
            run:
                image: user1/buildrunner-multi-platform-image
                cmd: echo "Hello World"
            push: user1/buildrunner-multi-platform-image2
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1

    # Tests adding 'latest' tag to build.push and run.image
    config_yaml = """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM busybox:latest
                platforms:
                    - linux/amd64
                    - linux/arm64/v8
            push: user1/buildrunner-multi-platform-image
        retag-multi-platform-image:
            run:
                image: user1/buildrunner-multi-platform-image
                cmd: echo "Hello World"
            push: user1/buildrunner-multi-platform-image2
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1

def test_invalid_multiplatform_retagging_with_push_empty_tags():
    # Retagging a multiplatform image is not supported
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

        retag-built-image:
            run:
                image: user1/buildrunner-test-multi-platform
                cmd: echo "Hello World"
            push:
                repository: user1/buildrunner-test-multi-platform2
                tags: []
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1

def test_invalid_multiplatform_retagging_with_commit():
    # Retagging a multiplatform image is not supported
    # Tests with commit in build step
    config_yaml = """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM busybox:latest
                platforms:
                    - linux/amd64
                    - linux/arm64/v8
            commit: user1/buildrunner-multi-platform-image
        retag-multi-platform-image:
            run:
                image: user1/buildrunner-multi-platform-image
                command: echo "Hello World"
            push: user1/buildrunner-multi-platform-image2
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1

def test_invalid_multiplatform_retagging_with_commit2():
    # Retagging a multiplatform image is not supported
    # Tests with commit after build step
    config_yaml = """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM {{ DOCKER_REGISTRY }}/busybox:latest
                platforms:
                    - linux/amd64
                    - linux/arm64/v8
            push: user1/buildrunner-test-multi-platform

        retag-built-image:
            run:
                image: user1/buildrunner-test-multi-platform
                cmd: echo "Hello World"
            commit: user1/buildrunner-test-multi-platform2
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1

def test_valid_single_platform_retagging():
    # Retagging a single platform image is supported
    config_yaml = """
    steps:
        build-container-single-platform:
            build:
                dockerfile: |
                    FROM {{ DOCKER_REGISTRY }}/busybox:latest
            push: user1/buildrunner-test-single-platform:latest

        retag-built-image:
            run:
                image: user1/buildrunner-test-single-platform:latest
                cmd: echo "Hello World"
            push: user1/buildrunner-test-single-platform2
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None

def test_invalid_multiplatform_rebuild_and_push():
    # Retagging a multiplatform image is not supported
    # Tests reading from dockerfile for the 2nd dockerfile
    config_yaml = """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM busybox:latest
                platforms:
                    - linux/amd64
                    - linux/arm64/v8
            push: user1/buildrunner-multi-platform-image
        retag-multi-platform-image:
            build:
                dockerfile: |
                    FROM user1/buildrunner-multi-platform-image
            push: user1/buildrunner-multi-platform-image2
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1

def test_invalid_multiplatform_from_dockerfile_in_filesystem():
    # Retagging a multiplatform image is not supported
    # Tests reading from dockerfile for the 2nd dockerfile
    config_yaml = """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: tests/test_config_validation/Dockerfile.retag
                platforms:
                    - linux/amd64
                    - linux/arm64/v8
            push: user1/buildrunner-multi-platform-image
        retag-multi-platform-image:
            build:
                dockerfile: |
                    FROM user1/buildrunner-multi-platform-image
            push: user1/buildrunner-multi-platform-image2
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1
    assert RETAG_ERROR_MESSAGE in errors.errors[0].message
