import os
import tempfile
from unittest import mock
import pytest
import yaml
from buildrunner import BuildRunner
from buildrunner.errors import BuildRunnerConfigurationError
from buildrunner.validation.config import validate_config, Errors, RETAG_ERROR_MESSAGE


TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BLANK_GLOBAL_CONFIG = os.path.join(TEST_DIR, "files/blank_global_config.yaml")


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
    assert errors is None


def test_invalid_multiplatform_retagging_with_push_empty_tags():
    # Retagging a multiplatform image is not supported
    config_yaml = """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM {{DOCKER_REGISTRY}}/busybox:latest
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
                    FROM {{DOCKER_REGISTRY}}/busybox:latest
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
                    FROM {{DOCKER_REGISTRY}}/busybox:latest
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
            push: user1/buildrunner-multi-platform-image:latest
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
            push: user1/buildrunner-multi-platform-image:latest
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


def test_reusing_multi_platform_images():
    # Reuse multi-platform images is valid if the image isn't committed or pushed
    config_yaml = """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM {{DOCKER_REGISTRY}}/busybox
                platforms:
                    - linux/amd64
                    - linux/arm64/v8
            push:
                - repository: user1/buildrunner-test-multi-platform
                  tags: [ 'latest', '0.0.1' ]
                - repository: user2/buildrunner-test-multi-platform
                  tags: [ 'latest', '0.0.1' ]

        use-built-image1:
            run:
                image: user1/buildrunner-test-multi-platform:0.0.1
                cmd: echo "Hello World"

        use-built-image2:
            run:
                image: user2/buildrunner-test-multi-platform:0.0.1
                cmd: echo "Hello World"
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


@pytest.mark.parametrize(
    "config_yaml",
    [
        # Tests that "BUILDRUNNER_BUILD_DOCKER_TAG" is replaced with id_string-build_number
        """
        steps:
            build-container-multi-platform:
                build:
                    dockerfile: |
                        FROM {{ DOCKER_REGISTRY }}/busybox
                    platforms:
                        - linux/amd64
                        - linux/arm64/v8
                push:
                    - repository: user1/buildrunner-test-multi-platform
                      tags: [ 'latest', '0.0.1', {{ BUILDRUNNER_BUILD_DOCKER_TAG }} ]
    
            use-built-image1:
                run:
                    image: user1/buildrunner-test-multi-platform
                    cmd: echo "Hello World"
    """,
        """
        steps:
            build-container-multi-platform:
                build:
                    dockerfile: |
                        FROM {{ DOCKER_REGISTRY }}/busybox
                    platforms:
                        - linux/amd64
                        - linux/arm64/v8
                push:
                    - repository: user1/buildrunner-test-multi-platform
                      tags: [ 'latest', '0.0.1', {{ BUILDRUNNER_BUILD_DOCKER_TAG }} ]
    
            use-built-image1:
                build:
                    dockerfile: |
                        FROM user1/buildrunner-test-multi-platform:latest
                    platforms:
                        - linux/amd64
                        - linux/arm64/v8
                push:
                    repository: user1/buildrunner-test-multi-platform2
                    tags: [ 'latest' ]
    """,
    ],
)
@mock.patch("buildrunner.config.DEFAULT_GLOBAL_CONFIG_FILES", [])
@mock.patch("buildrunner.detect_vcs")
def test_valid_config_with_buildrunner_build_tag(detect_vcs_mock, config_yaml):
    id_string = "main-921.ie02ed8.m1705616822"
    build_number = 342
    type(detect_vcs_mock.return_value).id_string = mock.PropertyMock(
        return_value=id_string
    )

    with tempfile.TemporaryDirectory() as tmpdirname:
        with tempfile.NamedTemporaryFile(
            dir=tmpdirname, mode="w", delete=False
        ) as tmpfile:
            tmpfile.write(config_yaml)
            tmpfile.close()
            try:
                runner = BuildRunner(
                    build_dir=tmpdirname,
                    build_results_dir=tmpdirname,
                    global_config_file=None,
                    run_config_file=tmpfile.name,
                    build_time=0,
                    build_number=build_number,
                    push=False,
                    cleanup_images=False,
                    cleanup_cache=False,
                    steps_to_run=None,
                    publish_ports=False,
                    log_generated_files=False,
                    docker_timeout=30,
                    local_images=False,
                    platform=None,
                    disable_multi_platform=False,
                )
                config = runner.run_config
                assert isinstance(config, dict)
                assert f"{id_string}-{build_number}" in config.get("steps").get(
                    "build-container-multi-platform"
                ).get("push")[0].get("tags")
            except Exception as e:
                assert False, f"Unexpected exception raised: {e}"


@pytest.mark.parametrize(
    "config_json",
    [
        """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM {{ DOCKER_REGISTRY }}/busybox
                platforms:
                    - linux/amd64
                    - linux/arm64/v8
            push:
                - repository: user1/buildrunner-test-multi-platform
                  tags: [ 'latest', '0.0.1', {{ BUILDRUNNER_BUILD_DOCKER_TAG }} ]

        use-built-image1:
            run:
                image: user1/buildrunner-test-multi-platform:{{ BUILDRUNNER_BUILD_DOCKER_TAG }}
                cmd: echo "Hello World"
            push:
                repository: user1/buildrunner-test-multi-platform2
                tags: [ 'latest' ]
    """,
        """
    steps:
        build-container-multi-platform:
            build:
                dockerfile: |
                    FROM {{ DOCKER_REGISTRY }}/busybox
                platforms:
                    - linux/amd64
                    - linux/arm64/v8
            push:
                - repository: user1/buildrunner-test-multi-platform
                  tags: [ 'latest', '0.0.1' ]

        use-built-image1:
            run:
                image: user1/buildrunner-test-multi-platform:{{ BUILDRUNNER_BUILD_DOCKER_TAG }}
                cmd: echo "Hello World"
            push: user1/buildrunner-test-multi-platform2
    """,
    ],
    ids=["buildrunnder_build_tag_explict", "buildrunnder_build_tag_implied"],
)
@mock.patch("buildrunner.config.DEFAULT_GLOBAL_CONFIG_FILES", [])
@mock.patch("buildrunner.detect_vcs")
def test_invalid_retagging_with_buildrunner_build_tag(detect_vcs_mock, config_json):
    # Tests that BUILDRUNNER_BUILD_DOCKER_TAG is added to push tags and fails for re-tagging
    id_string = "main-921.ie02ed8.m1705616822"
    build_number = 342
    type(detect_vcs_mock.return_value).id_string = mock.PropertyMock(
        return_value=id_string
    )

    with tempfile.TemporaryDirectory() as tmpdirname:
        with tempfile.NamedTemporaryFile(
            dir=tmpdirname, mode="w", delete=False
        ) as tmpfile:
            tmpfile.write(config_json)
            tmpfile.close()
            with pytest.raises(BuildRunnerConfigurationError) as excinfo:
                BuildRunner(
                    build_dir=tmpdirname,
                    build_results_dir=tmpdirname,
                    global_config_file=None,
                    run_config_file=tmpfile.name,
                    build_time=0,
                    build_number=build_number,
                    push=False,
                    cleanup_images=False,
                    cleanup_cache=False,
                    steps_to_run=None,
                    publish_ports=False,
                    log_generated_files=False,
                    docker_timeout=30,
                    local_images=False,
                    platform=None,
                    disable_multi_platform=False,
                )
            assert RETAG_ERROR_MESSAGE in excinfo.value.args[0]
            assert (
                f"user1/buildrunner-test-multi-platform:{id_string}-{build_number}"
                in excinfo.value.args[0]
            )
