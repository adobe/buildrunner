import pytest

from buildrunner.config.validation import RUN_MP_ERROR_MESSAGE


@pytest.mark.parametrize(
    "config_yaml, error_matches",
    [
        # Run in multiplatform build is not supported
        (
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
                        tags: ['latest']
                    run:
                        image: user1/buildrunner-test-multi-platform
                        cmd: echo "Hello World"
            """,
            [
                "run is not allowed in the same step as a multi-platform build step build-container-multi-platform"
            ],
        ),
        # Run in single platform build is supported
        (
            """
            steps:
                build-container:
                    build:
                        dockerfile: |
                            FROM {{DOCKER_REGISTRY}}/busybox:latest
                    push:
                        repository: user1/buildrunner-test-multi-platform
                        tags: ['latest']
                    run:
                        image: user1/buildrunner-test-multi-platform
                        cmd: echo "Hello World"
            """,
            [],
        ),
        # Post build is not supported for multiplatform builds
        (
            """
            steps:
                build-container-multi-platform:
                    build:
                        dockerfile: |
                            FROM busybox:latest
                        platforms:
                            - linux/amd64
                            - linux/arm64/v8
                    run:
                        post-build: path/to/build/context
            """,
            [RUN_MP_ERROR_MESSAGE],
        ),
        # Post build is supported for single platform builds
        (
            """
            steps:
                build-container-single-platform:
                    build:
                        dockerfile: |
                            FROM busybox:latest
                    run:
                        post-build: path/to/build/context
            """,
            [],
        ),
        (
            """
            steps:
                build-container-multi-platform:
                    build:
                        dockerfile: |
                            FROM busybox:latest
                        platforms:
                            - linux/amd64
                            - linux/arm64/v8
                        cache_from: busybox:latest
            """,
            [],
        ),
        (
            """
            steps:
                build-container-multi-platform:
                    build:
                        dockerfile: |
                            FROM busybox:latest
                        platforms:
                            - linux/amd64
                            - linux/arm64/v8
                        cache_from:
                            - type: local
                              src: path/to/dir
            """,
            [],
        ),
        (
            """
            steps:
                build-container-multi-platform:
                    build:
                        dockerfile: |
                            FROM busybox:latest
                        platforms:
                            - linux/amd64
                            - linux/arm64/v8
                        cache_from:
                            type: local
                            src: path/to/dir
            """,
            [],
        ),
    ],
)
def test_config_data(
    config_yaml, error_matches, assert_generate_and_validate_config_errors
):
    assert_generate_and_validate_config_errors(config_yaml, error_matches)
