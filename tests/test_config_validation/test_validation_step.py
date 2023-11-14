
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
          no-cache: true
          cache_from:
            - mytest-reg/buildrunner-test-multi-platform:latest
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


def test_invalid_mp_import():
    config_yaml = """
    steps:
      build-container-multi-platform:
        build:
          path: .
          dockerfile: Dockerfile
          platforms:
            - linux/amd64
            - linux/arm64
          import: mytest-reg/buildrunner-test-multi-platform:latest
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1


def test_valid_import():
    config_yaml = """
    steps:
      build-container-multi-platform:
        build:
          path: .
          dockerfile: Dockerfile
          import: mytest-reg/buildrunner-test-multi-platform:latest
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_services():
    config_yaml = """
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
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None