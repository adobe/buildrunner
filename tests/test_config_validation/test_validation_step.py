import pytest

from buildrunner.config.models_step import StepPushCommit, StepPypiPush


@pytest.mark.parametrize(
    "config_yaml, error_matches",
    [
        # Invalid to have platform and platforms
        (
            """
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
    """,
            ["Cannot specify both platform"],
        ),
        # Invalid to have platforms as a string, it should be a list
        (
            """
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
    """,
            ["Input should be a valid list"],
        ),
        # Invalid to have cache_from specified with platforms
        (
            """
    steps:
      build-container-multi-platform:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
          platforms:
          - linux/amd64
          cache_from:
          - image1
        push:
          repository: mytest-reg/buildrunner-test-multi-platform
          tags:
            - latest
    """,
            ["cache_from"],
        ),
        # Build is a path
        (
            """
    steps:
      build-is-path:
        build: .
    """,
            [],
        ),
        # Valid platforms
        (
            """
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
    """,
            [],
        ),
        # Platforms with no-cache
        (
            """
    steps:
      build-container-multi-platform:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
          platforms:
            - linux/amd64
            - linux/arm64
          no-cache: true
        push:
          repository: mytest-reg/buildrunner-test-multi-platform
          tags:
            - latest
    """,
            [],
        ),
        # Invalid to have duplicate multi-platform tag
        (
            """
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
    """,
            [
                "Cannot specify duplicate tag mytest-reg/buildrunner-test-multi-platform:latest in build step"
            ],
        ),
        # Identical tags in same string format
        (
            """
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
    """,
            [
                "Cannot specify duplicate tag mytest-reg/buildrunner-test-multi-platform:latest in build step"
            ],
        ),
        #  Same string format but different MP tags
        (
            """
    steps:
      build-container-multi-platform1:
        build:
          dockerfile: |
            FROM busybox:latest
          platforms:
            - linux/amd64
            - linux/arm64
        push: mytest-reg/buildrunner-test-multi-platform:latest
      build-container-multi-platform2:
        build:
          dockerfile: |
            FROM busybox:latest
          platforms:
            - linux/amd64
            - linux/arm64
        push: mytest-reg/buildrunner-test-multi-platform:not-latest
    """,
            [],
        ),
        # Invalid to have duplicate multi-platform tag and single platform tag
        (
            """
    steps:
      build-container-multi-platform1:
        build:
          path: .
          platforms:
            - linux/amd64
            - linux/arm64
        push: mytest-reg/buildrunner-test-multi-platform:latest
      build-container-single-platform:
        build:
          path: .
          platform: linux/arm64
        push: mytest-reg/buildrunner-test-multi-platform:latest
    """,
            [
                "Cannot specify duplicate tag mytest-reg/buildrunner-test-multi-platform:latest in build step"
            ],
        ),
        # Valid remote step
        (
            """
    steps:
      build-remote:
        remote:
          host: myserver.ut1
          cmd: docker build -t mytest-reg/buildrunner-test .
          artifacts:
            bogus/path/to/artifacts/*:
              type: tar
              compression: lzma
    """,
            [],
        ),
        # Remote missing command
        (
            """
    steps:
      build-remote:
        remote:
          host: myserver.ut1
    """,
            ["Field required"],
        ),
        # Valid commit
        (
            """
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
    """,
            [],
        ),
        # Valid pypi push
        (
            """
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
    """,
            [],
        ),
        # Invalid multiplatform import
        (
            """
    steps:
      build-container-multi-platform:
        build:
          path: .
          dockerfile: Dockerfile
          platforms:
            - linux/amd64
            - linux/arm64
          import: mytest-reg/buildrunner-test-multi-platform:latest
    """,
            ["import is not allowed in multi-platform build step"],
        ),
        # Valid import
        (
            """
    steps:
      build-container-multi-platform:
        build:
          path: .
          dockerfile: Dockerfile
          import: mytest-reg/buildrunner-test-multi-platform:latest
    """,
            [],
        ),
        # Valid services
        (
            """
    steps:
      my-build-step:
        run:
          services:
            my-service-container:
              build: <path/to/build/context or map>
              #image: <the Docker image to run>
              cmd: <a command to run>
              provisioners:
                shell: path/to/script.sh
                salt: <simple salt sls yaml config>
              shell: /bin/sh
              cwd: /source
              user: <user to run commands as (can be username:group / uid:gid)>
              hostname: <the hostname>
              dns:
                - 8.8.8.8
                - 8.8.4.4
              dns_search: mydomain.com
              extra_hosts:
                "www1.test.com": "192.168.0.1"
                "www2.test.com": "192.168.0.2"
              env:
                ENV_VARIABLE_ONE: value1
                ENV_VARIABLE_TWO: value2
              files:
                namespaced.file.alias1: "/path/to/readonly/file/or/dir"
                namespaced.file.alias2: "/path/to/readwrite/file/or/dir:rw"
              volumes_from:
                - my-service-container
              ports:
                8081: 8080
              pull: true
              systemd: true
              containers:
                - container1
                - container2
              wait_for:
                - 80
                - port: 9999
                  timeout: 30
              inject-ssh-agent: true
    """,
            [],
        ),
    ],
)
def test_config_data(
    config_yaml, error_matches, assert_generate_and_validate_config_errors
):
    assert_generate_and_validate_config_errors(config_yaml, error_matches)


def test_transforms(assert_generate_and_validate_config_errors):
    config, _ = assert_generate_and_validate_config_errors(
        {
            "steps": {
                "build": {"build": "."},
                "pypi-str": {"pypi-push": "pypi1"},
                "pypi-list-str": {"pypi-push": ["pypi1", "pypi2"]},
                "pypi-dict": {
                    "pypi-push": {"repository": "pypi1", "skip_existing": True}
                },
                "commit-str": {"commit": "commit1"},
                "push-str": {"push": "push1"},
                "push-list-str": {"push": ["push2", "push3"]},
                # Ensure that the "push" parameter is automatically set always to the correct value
                "push-dict": {"push": {"repository": "push4", "push": False}},
            }
        },
        [],
    )
    assert config.steps["build"].build.path == "."
    assert config.steps["pypi-str"].pypi_push == [
        StepPypiPush(repository="pypi1"),
    ]
    assert config.steps["pypi-list-str"].pypi_push == [
        StepPypiPush(repository="pypi1"),
        StepPypiPush(repository="pypi2"),
    ]
    assert config.steps["pypi-dict"].pypi_push == [
        StepPypiPush(repository="pypi1", skip_existing=True),
    ]
    assert config.steps["commit-str"].commit == [
        StepPushCommit(repository="commit1", push=False),
    ]
    assert config.steps["push-str"].push == [
        StepPushCommit(repository="push1", push=True),
    ]
    assert config.steps["push-list-str"].push == [
        StepPushCommit(repository="push2", push=True),
        StepPushCommit(repository="push3", push=True),
    ]
    assert config.steps["push-dict"].push == [
        StepPushCommit(repository="push4", push=True),
    ]
