
import yaml
from buildrunner.validation.config import validate_config, Errors


def test_valid_version_config():
    #  Invalid version
    config = {
        'version': 'string'
    }
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1

    #  Valid version
    config = {
        'version': 2.0,
        'steps': {
        }
    }
    errors = validate_config(**config)
    assert errors is None

    # Optional version
    config = {
        'steps': {
        }
    }
    errors = validate_config(**config)
    assert errors is None


def test_valid_config():
    # Sample valid config, but not exhaustive
    config_yaml = """
    version: 2.0
    steps:
      build-container-single-platform1:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
          platform: linux/amd64
        push:
          repository: mytest-reg/buildrunner-test
          tags:
            - latest
      build-container-multi-platform2:
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
      build-container-multi-platform-push3:
        build:
          path: .
          dockerfile: Dockerfile
          pull: false
          platforms:
            - linux/amd64
            - linux/arm64
        push:
          - myimages/image1
          - repository: myimages/image2
            tags:
              - latest
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_multiple_errors():
    # Multiple errors
    # Invalid to have version as a string
    # Invalid to have platforms and platform
    config_yaml = """
    version: string
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
    assert errors.count() == 2


def test_doc_config():
    # Tests the documentation example with minimal changes to make valid yaml
    config_yaml = """
    version: 2.0
    steps:
      my-build-step:
        # Optional step dependency definition to specify which steps need to be processed before this step.
        # The `version` must be present and set to `2.0` or higher for buildrunner to utilize the step dependencies list.
        # An buildrunner error will occur if `depends` is present but `version` is missing or value is lower than `2.0`.
        depends:
          - test-step
          - validation-step

        run:
          # xfail indicates whether the run operation is expected to fail.  The
          # default is false - the operation is expected to succeed.  If xfail
          # is true and the operation succeeds then it will result in a failure.
          xfail: True

          # A map of additional containers that should be created and linked to
          # the primary run container. These can be used to bring up services
          # (such as databases) that are required to run the step. More details
          # on services below.
          services:
            service-name-1:
              image: <the Docker image to run>
            service-name-2:
              cmd: <a command to run>

          # The Docker image to run. If empty the image created with the 'build'
          # attribute will be used.
          image: <the Docker image to run>

          # The command(s) to run. If omitted Buildrunner runs the command
          # configured in the Docker image without modification. If provided
          # Buildrunner always sets the container command to a shell, running the
          # given command here within the shell. If both 'cmd' and 'cmds' are
          # present the command in 'cmd' is run before the commands in the 'cmds'
          # list are run.
          cmd: <a command to run>
          cmds:
            - <command one>
            - <command two>

          # A collection of provisioners to run. Provisioners work similar to the
          # way Packer provisioners do and are always run within a shell.
          # When a provisioner is specified Buildrunner always sets the container
          # command to a shell, running the provisioners within the shell.
          # Currently Buildrunner supports shell and salt provisioners.
          provisioners:
            shell: path/to/script.sh | [path/to/script.sh, ARG1, ...]
            salt: <simple salt sls yaml config>

          # The shell to use when specifying the cmd or provisioners attributes.
          # Defaults to /bin/sh. If the cmd and provisioners attributes are not
          # specified this setting has no effect.
          shell: /bin/sh

          # The directory to run commands within. Defaults to /source.
          cwd: /source

          # The user to run commands as. Defaults to the user specified in the
          # Docker image.
          user: <user to run commands as (can be username:group / uid:gid)>

          # The hostname assigned to the run container.
          hostname: <the hostname>

          # Custom dns servers to use in the run container.
          dns:
            - 8.8.8.8
            - 8.8.4.4

          # A custom dns search path to use in the run container.
          dns_search: mydomain.com

          # Add entries to the hosts file
          # The keys are the hostnames.  The values can be either
          # ip addresses or references to service containers.
          extra_hosts:
            "www1.test.com": "192.168.0.1"
            "www2.test.com": "192.168.0.2"

          # A map specifying additional environment variables to be injected into
          # the container. Keys are the variable names and values are variable
          # values.
          env:
            ENV_VARIABLE_ONE: value1
            ENV_VARIABLE_TWO: value2

          # A map specifying files that should be injected into the container.
          # The map key is the alias referencing a given file (as configured in
          # the "local-files" section of the global configuration file) or a
          # relative path to a file/directory in the build directory.  The value
          # is the path the given file should be mounted at within the container.
          files:
            namespaced.file.alias1: "/path/to/readonly/file/or/dir"
            namespaced.file.alias2: "/path/to/readwrite/file/or/dir:rw"
            build/dir/file: "/path/to/build/dir/file"

          # A map specifying cache directories that are stored as archive files on the
          # host system as `local cache key` and extracted as a directory in
          # the container named `docker path`. The cache directories are maintained
          # between builds and can be used to store files, such as downloaded
          # dependencies, to speed up builds.
          # Caches can be shared between any builds or projects on the system
          # as the names are not prefixed with any project-specific information.
          # Caches should be treated as ephemeral and should only store items
          # that can be obtained/generated by subsequent builds.
          #
          # Two formats are supported when defining caches.
          # 1) RECOMMENDED
          #    <docker path>:
          #      - <local cache key A>
          #      - <local cache key B>
          #
          #    Restore Cache:
          #      This format allows for prefix matching. The order of the list dictates the
          #      order which should be searched in the local system cache location.
          #      When an item isn't found it will search for archive files which prefix matches
          #      the item in the list. If more than one archive file is matched for a prefix
          #      the archive file most recently modified will be used. If there is no
          #      matching archive file then nothing will be restored in the docker container.
          #
          #    Save Cache:
          #      The first local cache key in the list is used for the name of the local
          #      cache archive file.
          #
          # 2) <local cache key>: <docker path> (backwards compatible with older caching method, but more limited)
          #
          caches:
            # Recommended format.
            <docker path>:
              - <local cache key A>
              - <local cache key B>

            "/root/.m2/repository":
              # Buildrunner will look for a cache that matches this cache key/prefix,
              # typically the first key should be the most specific as it is the closest match
              # Note that this first key will also be used to save the cache for use across builds or projects
              - m2repo-{{ checksum("pom.xml", "subproj/pom.xml") }}
              # If the first cache key is not found in the caches, use this prefix to look for a cache that may not
              # be an exact match, but may still be close and not require as much downloading of dependencies, etc
              # Note that this may match across any cache done by any build on the same system, so it may be wise to
              # use a unique prefix for any number of builds that have a similar dependency tree, etc
              - m2repo-
              # If no cache is found, nothing will be extracted and the application will need to rebuild the cache

            # Backwards compatible format. Not recommended for future or updated configurations.
            <local cache key>: <docker path>
            maven: "/root/.m2/repository"

          # A map specifying ports to expose, this is only used when the
          # --publish-ports parameter is passed to buildrunner
          ports:
            5458: 8080

          # A list specifying service containers (see below) whose exposed
          # volumes should be mapped into the run container's file system.
          # An exposed volume is one created by the volume Dockerfile command.
          # See https://docs.docker.com/engine/reference/builder/#volume for more
          # details regarding the volume Dockerfile command.
          volumes_from:
            - my-service-container

          # A list specifying ssh keys that should be injected into the container
          # via an ssh agent. The list should specify the ssh key aliases (as
          # configured in the "ssh-keys" section of the global configuration
          # file) that buildrunner should inject into the container. Buildrunner
          # injects the keys by mounting a ssh-agent socket and setting the
          # appropriate environment variable, meaning that the private key itself
          # is never available inside the container.
          ssh-keys:
            - my_ssh_key_alias

          # A map specifying the artifacts that should be archived for the step.
          # The keys in the map specify glob patterns of files to archive. If a
          # value is present it should be a map of additional properties that
          # should be added to the build artifacts.json file. The artifacts.json
          # file can be used to publish artifacts to another system (such as
          # Gauntlet) with the accompanying metadata. By default artifacts will be
          # listed in the artifacts.json file; this can be disabled by adding the
          # ``push`` property and set it to false.
          #
          # When archiving *directories* special properties can be set to change
          # the behavior of the archiver.  Directories by default are archived as
          # gzip'ed TARs.  The compression can be changed by setting the
          # ``compression`` property to one of the below-listed values.  The
          # archive type can be changed by setting the property ``type:zip``.
          # When a zip archive is requested then the ``compression`` property is
          # ignored.  If the directory tree should be gathered verbatim without
          # archiving then the property ``format:uncompressed`` can be used.
          #
          # NOTE: Artifacts can only be archived from the /source directory using
          # a relative path or a full path. Files outside of this directory will
          # fail to be archived.
          artifacts:
            artifacts/to/archive/*:
              format: uncompressed
              type: tar
              compression: gz
              push: true
              property1: value1
              property2: value2

          # Whether or not to pull the image from upstream prior to running
          # the step.  This is almost always desirable, as it ensures the
          # most up to date source image.
          # NOTE: If the image was created from a 'push' or 'commit' earlier in
          #       this ``buildrunner.yaml`` then this will default to false
          pull: true 

          # Specify a different platform architecture when pulling and running images.
          # This is useful if you are running an image that was built for a different architecture
          # than what buildrunner is running on, such as using a linux/arm64/v8 Apple M1 architecture
          # development machine to run or test an image built for linux/amd64 architecture.
          platform: linux/amd64
          # <or>
          # platform: linux/arm64/v8 # an apple m1 architecture

          # systemd does not play well with docker typically, but you can
          # use this setting to tell buildrunner to set the necessary docker
          # flags to get systemd to work properly:
          # - /usr/sbin/init needs to run as pid 1
          # - /sys/fs/cgroup needs to be mounted as readonly
          #   (-v /sys/fs/cgroup:/sys/fs/cgroup:ro)
          # - The security setting seccomp=unconfined must be set
          #   (--security-opt seccomp=unconfined)
          # If this is ommitted, the image will be inspected for the label
          # 'BUILDRUNNER_SYSTEMD'.
          # If found, systemd=true will be assumed.
          # systemd: true/false
          systemd: true

          # Docker supports certain kernel capabilities, like 'SYS_ADMIN'.
          # see https://goo.gl/gTQrqW for more infromation on setting these.
          cap_add: 'SYS_ADMIN'
          # <or>
          # cap_add:
          #   - 'SYS_ADMIN'
          #   - 'SYS_RAWIO'

          # Docker can run in a privileged mode. This allows access to all devices
          # on the host. Using privileged is rare, but there are good use cases
          # for this feature. see https://goo.gl/gTQrqW for more infromation on
          # setting these.
          # Default: false
          # privileged: true/false
          privileged: true

          # The post-build attribute commits the resulting run container as an
          # image and allows additional Docker build processing to occur. This is
          # useful for adding Docker configuration, such as EXPOSE and CMD
          # instructions, when building an image via the run task that cannot be
          # done without running a Docker build. The post-build attribute
          # functions the same way as the 'build' step attribute does, except
          # that it prepends the committed run container image to the provided
          post-build: path/to/build/context
          # <or>
          # post-build:
          #   dockerfile: |
          #     EXPOSE 80
          #     CMD /runserver.sh

          # A list of container names or labels created within any run container
          # that buildrunner should clean up.  (Use if you call
          containers:
            - container1
            - container2
        """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_full_confg():
    # Minus template areas
    config_yaml = """
    steps:
      generate_files:
        run:
          image: docker.company.com/abc-xdm-proto-build:latest
          ssh-keys: ["company-github"]
          env:
            GIT_TOKEN: 'blahblahblahblahblahblah'
          cmd: sbt clean generateAwareJsonFiles combineXDM generateProtobufFiles
          artifacts:
            'target/protobufFiles/Database*.proto':
            'target/rawJson/Database*.json':
            'target/AwareJson/Aware.json':
            'target/combinedXDM/complete-schema-template.schema.json':
      build-dev-rpm:
        build:
          inject:
            "buildrunner.results/generate_files/*.proto": "proto/"
            "buildrunner.results/generate_files/A*.json": "json/"
            "db_build/dms.repo.centos7": db_build/dms.repo
          dockerfile: |
            FROM docker-release.dr.corp.company.com/centos-7-x86_64-obuild:latest
            ADD db_build/dms.repo /etc/yum.repos.d/dms.repo
            RUN rpm --rebuilddb; yum clean all; yum install -y db-omniture-libs-protobuf-2.6.1 db-scds-proto-1.0 db-scds-json-1.0
            ADD proto/*.proto /tmp/proto/
            ADD json/*.json /tmp/json/
        run:
          cmds:
            - "chown -R httpd:www /source"
            - "echo ~ Compiling previous proto version..."
            - "mkdir -p /tmp/existingscds && for f in `ls -d /home/omniture/protobuf/scds/*.proto`; do protoc -I=/home/omniture/protobuf --cpp_out /tmp/existingscds $f; done"
            - "echo ~ Compiling current proto version..."
          artifacts:
            # pull the log if rpmbuild fails
            "db_tmp/rpm/TMPDIR/*.log": {type: 'log'}
            # pull the noarch packages
            "db_tmp/rpm/RPMS/noarch/*.noarch.rpm": {platform: 'centos-noarch'}
      build-proto-java:
        build:
          inject:
            "buildrunner.results/generate_files/*.proto": "proto"
          dockerfile: |
            FROM docker.company.com/abc-base-containers/protobuf-builder:java8-2.5.0
            ADD proto/*.proto /tmp/proto/scds/
        run:
          caches:
            maven: "/root/.m2/repository"
          cmds: [
            'mvn package ${BUILDRUNNER_DO_PUSH+deploy} -am -pl proto-java'
          ]
          artifacts:
            '*/target/*.jar':
      download-country:
        build:
          inject:
            "db_build/bin/*": "db_build/bin/"
          dockerfile: |
            FROM docker-release.dr.corp.company.com/centos-7-x86_64-obuild
            ADD db_build/bin/* /tmp/
        run:
          cmds:
            - '/tmp/download_country.sh'
            # strip all quotes
            - "sed -i 's/bogus//g' country_codes.csv"
            # Add missing ?,? because it's not in the DB
            - 'echo "?,?" >> country_codes.csv'
            # keep first 2 columns, uppercase 2nd column
            - 'awk -F, ''{OFS=","; $2 = toupper($2); {print $1,$2}}'' country_codes.csv > country_code_map.csv'
          artifacts:
            'country_code_map.csv':
      build-transform-proto-xdm:
        build:
          inject:
            "buildrunner.results/generate_files/*.proto": "proto"
            "buildrunner.results/generate_files/*.json": "json"
          dockerfile: |
            FROM docker.company.com/abc-base-containers/protobuf-builder:java8-2.5.0
            RUN apt-get update && apt-get -y install openssh-client
            ADD proto/*.proto /tmp/proto/scds/
        run:
          env:
            ARTIFACTORY_USER: 'cool_user'
            ARTIFACTORY_API_TOKEN: 'blahblahblahblahblahblahblah'
          caches:
            maven: "/root/.m2/repository"
          shell: /bin/bash
          cmds: [
            'cp /tmp/json/raw/*json json/raw',
            'mkdir -p csv',
            'cp /tmp/csv/*csv csv',
            'curl -L https://github.com/stedolan/jq/releases/download/jq-1.5/jq-linux64 > jq',
            'chmod +x jq',
          ]
          artifacts:
            'transform-proto-xdm/target/*':
            'transform-proto-xdm-generator/target/*':
            'validator-xdm/target/*':
      generate_docs:
        run:
          image: docker.company.com/abc-xdm-proto-build:latest
          ssh-keys: ["company-github"]
          env:
            GIT_TOKEN: 'blahblahblahblahblahblahblah'
          cmd: "sbt clean generateDocs ${BUILDRUNNER_DO_PUSH+publishGHPages}"
          artifacts:
            'target/docs/*':
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None


def test_github_config():
    # Valid github config
    config_yaml = """
    github:
      company_github:
        endpoint: 'https://git.company.com/api'
        version: 'v3'
        username: 'USERNAME'
        app_token: 'APP_TOKEN'
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert errors is None

    # Invalid github config
    config_yaml = """
    github:
      company_github:
        endpoint: 'https://git.company.com/api'
        version: 'v3'
        username: 'USERNAME'
        app_token: 'APP_TOKEN'
        bogus: 'bogus'
    """
    config = yaml.load(config_yaml, Loader=yaml.Loader)
    errors = validate_config(**config)
    assert isinstance(errors, Errors)
    assert errors.count() == 1
