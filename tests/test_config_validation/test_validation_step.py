import pytest


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
            ["Input should be a valid list", "Input should be a valid string"],
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
              # The 'build' attribute functions the same way that the step
              # 'build' attribute does. The only difference is that the image
              # produced by a service container build attribute cannot be pushed
              # to a remote repository.
              build: <path/to/build/context or map>

              # The pre-built image to base the container on. The 'build' and
              # 'image' attributes are mutually exclusive in the service
              # container context.
              image: <the Docker image to run>

              # The command to run. If ommitted Buildrunner runs the command
              # configured in the Docker image without modification. If provided
              # Buildrunner always sets the container command to a shell, running
              # the given command here within the shell.
              cmd: <a command to run>

              # A collection of provisioners to run. Provisioners work similar to
              # the way Packer provisioners do and are always run within a shell.
              # When a provisioner is specified Buildrunner always sets the
              # container command to a shell, running the provisioners within the
              # shell. Currently Buildrunner supports shell and salt
              # provisioners.
              provisioners:
                shell: path/to/script.sh
                salt: <simple salt sls yaml config>

              # The shell to use when specifying the cmd or provisioners
              # attributes. Defaults to /bin/sh. If the cmd and provisioners
              # attributes are not specified this setting has no effect.
              shell: /bin/sh

              # The directory to run commands within. Defaults to /source.
              cwd: /source

              # The user to run commands as. Defaults to the user specified in
              # the Docker image.
              user: <user to run commands as (can be username:group / uid:gid)>

              # The hostname assigned to the service container.
              hostname: <the hostname>

              # Custom dns servers to use in the service container.
              dns:
                - 8.8.8.8
                - 8.8.4.4

              # A custom dns search path to use in the service container.
              dns_search: mydomain.com

              # Add entries to the hosts file
              # The keys are the hostnames.  The values can be either
              # ip addresses or references to other service containers.
              extra_hosts:
                "www1.test.com": "192.168.0.1"
                "www2.test.com": "192.168.0.2"

              # A map specifying additional environment variables to be injected
              # into the container. Keys are the variable names and values are
              # variable values.
              env:
                ENV_VARIABLE_ONE: value1
                ENV_VARIABLE_TWO: value2

              # A map specifying files that should be injected into the container.
              # The map key is the alias referencing a given file (as configured in
              # the "local-files" section of the global configuration file) and the
              # value is the path the given file should be mounted at within the
              # container.
              files:
                namespaced.file.alias1: "/path/to/readonly/file/or/dir"
                namespaced.file.alias2: "/path/to/readwrite/file/or/dir:rw"

              # A list specifying other service containers whose exposed volumes
              # should be mapped into this service container's file system. Any
              # service containers in this list must be defined before this
              # container is.
              # An exposed volume is one created by the volume Dockerfile command.
              # See https://docs.docker.com/engine/reference/builder/#volume for more
              # details regarding the volume Dockerfile command.
              volumes_from:
                - my-service-container

              # A map specifying ports to expose and link within other containers
              # within the step.
              ports:
                8081: 8080

              # Whether or not to pull the image from upstream prior to running
              # the step.  This is almost always desirable, as it ensures the
              # most up to date source image.  There are situations, however, when
              # this can be set to false as an optimization.  For example, if a
              # container is built at the beginning of a buildrunner file and then
              # used repeatedly.  In this case, it is clear that the cached version
              # is appropriate and we don't need to check upstream for changes.
              pull: true

              # See above
              systemd: true

              # A list of container names or labels created within any run container
              # that buildrunner should clean up.  (Use if you call
              # 'docker run --name <name>' or 'docker run --label <label>' within a run container.)
              containers:
                - container1
                - container2

              # Wait for ports to be open this container before moving on.
              # This allows dependent services to know that a service inside the
              # container is running. This times out automatically after 10 minutes
              # or after the configured timeout.
              wait_for:
                - 80
                # A timeout in seconds may optionally be specified
                - port: 9999
                  timeout: 30

              # If ssh-keys are specified in the run step, an ssh agent will be started
              # and mounted inside the running docker container.  If inject-ssh-agent
              # is set to true, the agent will be mounted inside the service container
              # also.  This isn't enabled by default as there is the theoretical
              # (though unlikely) possibility that a this access could be exploited.
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
