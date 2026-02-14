import os
from unittest import mock
import pytest
from buildrunner import BuildRunner
from buildrunner.config import BuildRunnerConfig
from buildrunner.config.validation import (
    RETAG_ERROR_MESSAGE,
)
from buildrunner.errors import BuildRunnerConfigurationError


TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BLANK_GLOBAL_CONFIG = os.path.join(TEST_DIR, "files/blank_global_config.yaml")


@pytest.mark.parametrize(
    "desc, config_yaml, error_matches",
    [
        (
            "Retagging a multiplatform image is not supported",
            """
        steps:
            build-container-multi-platform:
                build:
                    dockerfile: |
                        FROM busybox:latest
                    platforms:
                        - linux/amd64
                        - linux/arm64/v8
                push:
                    repository: user1/buildrunner-multi-platform-image
                    tags: [latest]
            retag-multi-platform-image:
                run:
                    image: user1/buildrunner-multi-platform-image:latest
                    cmd: echo "Hello World"
                push:
                    repository: user1/buildrunner-multi-platform-image2
                    tags: [latest]
        """,
            [
                "The following images are re-tagged: ['user1/buildrunner-multi-platform-image:latest']"
            ],
        ),
        (
            "Latest tag is assumed if not specified in image",
            """
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
                tags: [latest]

        retag-built-image:
            run:
                image: user1/buildrunner-test-multi-platform
                cmd: echo "Hello World"
            push:
                repository: user1/buildrunner-test-multi-platform2
                tags: [latest]
    """,
            [
                "The following images are re-tagged: ['user1/buildrunner-test-multi-platform:latest']"
            ],
        ),
        (
            "Commit in build step",
            """
        steps:
            build-container-multi-platform:
                build:
                    dockerfile: |
                        FROM busybox:latest
                    platforms:
                        - linux/amd64
                        - linux/arm64/v8
                commit:
                    repository: user1/buildrunner-multi-platform-image
                    tags: [latest]
            retag-multi-platform-image:
                run:
                    image: user1/buildrunner-multi-platform-image
                    cmd: echo "Hello World"
                push:
                    repository: user1/buildrunner-multi-platform-image2
                    tags: [latest]
        """,
            [
                "The following images are re-tagged: ['user1/buildrunner-multi-platform-image:latest']"
            ],
        ),
        (
            "Commit after build step",
            """
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
                    tags: [latest]

            retag-built-image:
                run:
                    image: user1/buildrunner-test-multi-platform
                    cmd: echo "Hello World"
                commit:
                    repository: user1/buildrunner-test-multi-platform2
                    tags: [latest]
        """,
            [
                "The following images are re-tagged: ['user1/buildrunner-test-multi-platform:latest']"
            ],
        ),
        (
            "Retagging a single platform image is supported",
            """
        steps:
            build-container-single-platform:
                build:
                    dockerfile: |
                        FROM {{DOCKER_REGISTRY}}/busybox:latest
                push:
                    repository: user1/buildrunner-test-single-platform
                    tags: [latest]

            retag-built-image:
                run:
                    image: user1/buildrunner-test-single-platform:latest
                    cmd: echo "Hello World"
                push:
                    repository: user1/buildrunner-test-single-platform2
                    tags: [latest]
        """,
            [],
        ),
        (
            "Read from dockerfile for the 2nd dockerfile",
            """
        steps:
            build-container-multi-platform:
                build:
                    dockerfile: |
                        FROM busybox:latest
                    platforms:
                        - linux/amd64
                        - linux/arm64/v8
                push:
                    repository: user1/buildrunner-multi-platform-image
                    tags: [latest]
            retag-multi-platform-image:
                build:
                    dockerfile: |
                        FROM user1/buildrunner-multi-platform-image
                push:
                    repository: user1/buildrunner-multi-platform-image2
                    tags: [latest]
        """,
            [
                "The following images are re-tagged: ['user1/buildrunner-multi-platform-image:latest']"
            ],
        ),
        (
            "Read from dockerfile file",
            """
        steps:
            build-container-multi-platform:
                build:
                    dockerfile: tests/test_config_validation/Dockerfile.retag
                    platforms:
                        - linux/amd64
                        - linux/arm64/v8
                push:
                    repository: user1/buildrunner-multi-platform-image
                    tags: [latest]
            retag-multi-platform-image:
                build:
                    dockerfile: |
                        FROM user1/buildrunner-multi-platform-image
                push:
                    repository: user1/buildrunner-multi-platform-image2
                    tags: [latest]
        """,
            [RETAG_ERROR_MESSAGE],
        ),
        (
            "Reuse multi-platform images is valid if the image isn't committed or pushed",
            """
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
        """,
            [],
        ),
    ],
)
def test_config_data(
    desc, config_yaml, error_matches, assert_generate_and_validate_config_errors
):
    _ = desc
    assert_generate_and_validate_config_errors(config_yaml, error_matches)


@pytest.mark.parametrize(
    "config_yaml",
    [
        # Tests that "BUILDRUNNER_BUILD_DOCKER_TAG" is replaced with id_string-build_number
        """
        steps:
            build-container:
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
        # Re-pushing images where both steps are multi-platform is valid
        """
        steps:
            build-container:
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
        """
        steps:
            build-container:
                build:
                    dockerfile: |
                        FROM {{ DOCKER_REGISTRY }}/nginx:latest
                        RUN printf '{{ BUILDRUNNER_BUILD_NUMBER }}' > /usr/share/nginx/html/index.html
                push:
                    repository:  user1/buildrunner-test-image
                    tags: [latest]
    """,
        """
        steps:
            build-container:
                build:
                    dockerfile: |
                        FROM {{ DOCKER_REGISTRY }}/nginx:latest
                        RUN printf '{{ BUILDRUNNER_BUILD_NUMBER }}' > /usr/share/nginx/html/index.html
                push:
                    repository: user1/buildrunner-test-image
                    tags: [latest]
    """,
    ],
)
@mock.patch("buildrunner.config.DEFAULT_GLOBAL_CONFIG_FILES", [])
@mock.patch("buildrunner.detect_vcs")
def test_valid_config_with_buildrunner_build_tag(
    detect_vcs_mock, config_yaml, tmp_path
):
    id_string = "main-921.ie02ed8.m1705616822"
    build_number = 342
    type(detect_vcs_mock.return_value).id_string = mock.PropertyMock(
        return_value=id_string
    )

    buildrunner_path = tmp_path / "buildrunner.yaml"
    buildrunner_path.write_text(config_yaml)
    BuildRunner(
        build_dir=str(tmp_path),
        build_results_dir=str(tmp_path / "buildrunner.results"),
        global_config_file=None,
        run_config_file=str(buildrunner_path),
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
        global_config_overrides={},
    )
    buildrunner_config = BuildRunnerConfig.get_instance()
    push_info = buildrunner_config.run_config.steps["build-container"].push
    assert isinstance(push_info, list)
    assert f"{id_string}-{build_number}" in push_info[0].tags


@pytest.mark.parametrize(
    "config_yaml",
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
    ids=["buildrunner_build_tag_explict", "buildrunner_build_tag_implied"],
)
@mock.patch("buildrunner.config.DEFAULT_GLOBAL_CONFIG_FILES", [])
@mock.patch("buildrunner.detect_vcs")
def test_invalid_retagging_with_buildrunner_build_tag(
    detect_vcs_mock, config_yaml, tmp_path
):
    # Tests that BUILDRUNNER_BUILD_DOCKER_TAG is added to push tags and fails for re-tagging
    id_string = "main-921.ie02ed8.m1705616822"
    build_number = 342
    type(detect_vcs_mock.return_value).id_string = mock.PropertyMock(
        return_value=id_string
    )

    buildrunner_path = tmp_path / "buildrunner.yaml"
    buildrunner_path.write_text(config_yaml)
    with pytest.raises(BuildRunnerConfigurationError) as excinfo:
        BuildRunner(
            build_dir=str(tmp_path),
            build_results_dir=str(tmp_path / "buildrunner.results"),
            global_config_file=None,
            run_config_file=str(buildrunner_path),
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
            global_config_overrides={},
        )
    assert RETAG_ERROR_MESSAGE in excinfo.value.args[0]
    assert (
        f"user1/buildrunner-test-multi-platform:{id_string}-{build_number}"
        in excinfo.value.args[0]
    )
