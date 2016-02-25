===========
BuildRunner
===========

Build and publish Docker images, run builds/tasks within Docker containers or
on remote hosts.

Overview
========

BuildRunner is a tool written on top of Docker and ssh remoting frameworks that
allows engineers to do the following:

- Build and publish Docker images
- Run other build and packaging tools within custom Docker containers while
  collecting the artifacts these tools produce
- Run builds/tasks on remote systems that cannot be done within a Docker
  container
- Creating ad-hoc environments using Docker containers for running automated,
  self-contained integration and functional tests

BuildRunner runs builds and tests by reading configuration files within a given
source tree. This allows build and continuous integration test configurations
to live close to source files, providing engineers the ability to update and
version the build and test configuration right along with the code that is
being built and tested. This also allows build tools and infrastructures to
very easily import and setup builds for new modules and branches (see the
associated BuildRunner Jenkins plugin project located
`here <https://***REMOVED***/***REMOVED***/buildrunner-plugin>`_
for an example).

============
Installation
============

Currently the best way to install BuildRunner is via pip, pointing at the
Release Engineering internal pypi server. This is best done when installing
into a virtual environment using virtualenv. The following commands will create
a new virtual environment, activate it, and install BuildRunner within it::

  virtualenv buildrunner
  source buildrunner/bin/activate
  pip install -i https://pypi.dev.ut1.omniture.com/releng/pypi/ vcsinfo
  pip install -i https://pypi.dev.ut1.omniture.com/releng/pypi/ buildrunner

The buildrunner executable is now available at buildrunner/bin/buildrunner and
can be added to your path.

OS X
====

BuildRunner will work with boot2docker, allowing you to develop on a Mac OS X
machine while still building on linux. BuildRunner honors the environment
variable settings the same way that the docker client does. Get the latest
version of boot2docker here::

  https://github.com/boot2docker/osx-installer/releases

BuildRunner has been verified to work with boot2docker 1.3.0.

====================
Global Configuration
====================

BuildRunner can be configured globally on a given build system to account for
installation specific properties. This feature makes project build
configuration files more portable, allowing specific BuildRunner installations
to map remote hosts and local files to aliases defined in the project build
configuration.

The following example configuration explains what options are available and how
they are used::

  # The 'build-servers' global configuration consists of a map where each key
  # is a server user@host string and the value is a list of host aliases that
  # map to the server. This allows builders to configure BuildRunner to talk to
  # specific servers within their environment on a project by project basis.
  build-servers:
    user@host:
      - alias1
      - alias2

  # The 'ssh-keys' global configuration is a list of ssh key configurations.
  # The file attribute specifies the path to a local ssh private key. If the
  # private key is password protected the password attribute specifies the
  # password. The alias attribute is a list of aliases assigned to the given
  # key (see the "ssh-keys" configuration example of the "run" step attribute
  # below).
  ssh-keys:
  - file: /path/to/ssh/private/key.pem
    password: <password if needed>
    aliases:
      - 'my-github-key'

  # The 'local-files' global configuration consists of a map where each key
  # is a file alias and the value is the path where the file resides on the
  # local server (see the "local-files" configuration example of the "run" step
  # attribute below).
  local-files:
    digitalmarketing.mvn.settings: '/Users/tomkinso/.m2/settings.xml'

  # The 'caches-root' global configuration specifies the directory to use for
  # build caches. The default directory is ~/.buildrunner/caches.
  caches-root: ~/.buildrunner/caches

==================
BuildRunner Builds
==================

A BuildRunner build consists of one or more build steps.

Each step may build a custom Docker image and run a task within a specific
Docker container or run commands on a remote host.

Artifacts can be collected from tasks run within containers or remote hosts
when they have finished running and archived in your build system (Jenkins, for
instance).

Resulting images (either from a build phase or a run phase) can be pushed to
the central or a private Docker image registry for use in other builds or to
run services in other environments.

Build definitions are found in the root of your source tree, either in a file
named 'buildrunner.yaml' or 'gauntlet.yaml'. The build definition is simply a
yaml map defining 'steps'. Each step is given a custom name and must contain
either 'build' and/or 'run' attributes (optionally containing a 'push'
attribute) or a 'remote' attribute::

  steps:
    step1-name:
      build: <build config>
      run: <run config>
      push: <push config>
      # or
      remote: <remote config>
    step2-name:
      build: <build config>
      run: <run config>
      push: <push config>
      # or
      remote: <remote config>

Step names are arbitrary--you can use whatever names you want as long as they
are unique within a given "steps" configuration. Archived artifacts are stored
in a step-specific results directory. To use artifacts generated from a
previous step in a subsequent one you would reference them using the previous
step name. (NOTE: Artifacts from previous steps are not available within remote
builds)

Standard Docker Builds (the 'build' step attribute)
===================================================

BuildRunner allows you to build a Docker image using a standard Dockerfile.
This is done using the top-level 'build' attribute in a step configuration. The
value of the 'build' attribute can either be a single string value indicating
the directory to use for the Docker build context (the directory containing the
Dockerfile) or a map that describes a dynamic build context and/or other build
arguments.

Here is an example of a build definition that would build a Docker image using
the root directory of the source tree as the build context (equivalent to
running 'docker build .' in the root of your source tree)::

  steps:
    build-my-container:
      build: .

If the Dockerfile is in another directory within the source tree just give the
relative path as the argument to the build attribute::

  steps:
    build-my-container:
      build: my/container/build/context

By placing different contexts in different directories a single source tree can
produce multiple Docker images::

  steps:
    build-container-1:
      build: container-1
    build-container-2:
      build: container-2

The value of the 'build' attribute can also be a map. The following example
shows the different configuration options available::

  steps:
    build-my-container:
      build:
        # Define the base context directory (same as string-only value)
        path: my/container/build/context

        # The inject map specifies other files outside the build context that
        # should be included in the context sent to the Docker daemon. Files
        # injected into the build context override files with the same name/path
        # contained in the path configuration above.
        # (NOTE: you do not need to specify a path attribute if you inject all
        # of the files you need, including a Dockerfile)
        inject:
          # Each entry in the map has a glob pattern key that resolves relative
          # to the source tree root with the value being the directory within
          # the build context that the file(s) should be copied to. These files
          # will be available to the Dockerfile at the given location during
          # the Docker build.
          glob/to/files.*: dest/dir
          path/to/file.txt: dest/dir

        # The path to a Dockerfile to use, or an inline Dockerfile declaration.
        # This Dockerfile overrides any provided in the path or inject
        # configurations. If the docker context does not require any additional
        # resources the path and inject configurations are not required.
        dockerfile: path/to/Dockerfile
        <or>
        dockerfile: |
          FROM someimage:latest
          RUN /some/command

        # Whether to use the default Docker image cache for intermediate
        # images--caching images  significantly speeds up the building of
        # images but may not be desired when building images for publishing
        no-cache: true/false (defaults to false)

        # Instead of building import the given tar file as a Docker image. If
        # this value is present all other options are ignored and the resulting
        # image is passed to subsequent steps.
        import: path/to/image/archive.tar

Running Containers (the 'run' step attribute)
=============================================

The 'run' step attribute is used to create and run a Docker container from a
given image.

There are 2 reasons for running a Docker container within a build:

1. To run another build tool or test framework and collect the resulting
   artifacts
2. To run scripts and operations within an existing image to create a new image
   (similar to how Packer creates Docker images)

BuildRunner injects special environment variables and volume mounts into every
run container. The following environment variables are set and available in
every run container:

- BUILDRUNNER_BUILD_NUMBER = the build number
- BUILDRUNNER_BUILD_ID = a unique id identifying the build (includes vcs and
  build number information)
- VCSINFO_BRANCH = the VCS branch
- VCSINFO_NUMBER = the VCS commit number
- VCSINFO_ID = the VCS commit id
- VCSINFO_SHORT_ID = the VCS short commit id
- VCSINFO_MODIFIED = the last file modification timestamp if local changes
  have been made and not committed to the source VCS repository

The following volumes are created within run containers:

- /source = (read-write) maps to a pristine snapshot of the current source
  tree (build directory)
- /artifacts = (read-only) maps to the buildrunner.results directory

The following example shows the different configuration options available::

  steps:
    my-build-step:
      run:
        # A map of additional containers that should be created and linked to
        # the primary run container. These can be used to bring up services
        # (such as databases) that are required to run the step. More details
        # on services below.
        services:
          service-name-1: <service config>
          service-name-2: <service config>

        # The Docker image to run. If empty the image created with the 'build'
        # attribute will be used.
        image: <the Docker image to run>

        # The command(s) to run. If ommitted BuildRunner runs the command
        # configured in the Docker image without modification. If provided
        # BuildRunner always sets the container command to a shell, running the
        # given command here within the shell. If both 'cmd' and 'cmds' are
        # present the command in 'cmd' is run before the commands in the 'cmds'
        # list are run.
        cmd: <a command to run>
        cmds:
          - <command one>
          - <command two>

        # A collection of provisioners to run. Provisioners work similar to the
        # way Packer provisioners do and are always run within a shell.
        # When a provisioner is specified BuildRunner always sets the container
        # command to a shell, running the provisioners within the shell.
        # Currently BuildRunner supports shell and salt provisioners.
        provisioners:
          shell: path/to/script.sh
          salt: <simple salt sls yaml config>

        # The shell to use when specifying the cmd or provisioners attributes.
        # Defaults to /bin/sh. If the cmd and provisioners attributes are not
        # specified this setting has no effect.
        shell: /bin/sh

        # The directory to run commands within. Defaults to /source.
        cwd: /source

        # The user to run commands as. Defaults to the user specified in the
        # Docker image.
        user: <user to run commands as>

        # The hostname assigned to the run container.
        hostname: <the hostname>

        # Custom dns servers to use in the run container.
        dns:
          - 8.8.8.8
          - 8.8.4.4

        # A custom dns search path to use in the run container.
        dns-search: mydomain.com

        # A map specifying additional environment variables to be injected into
        # the container. Keys are the variable names and values are variable
        # values.
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

        # A map specifying cache directories that should be mounted inside the
        # container. The cache directories are maintained between builds and can
        # be used to store files, such as downloaded dependencies, to speed up
        # builds. Caches are shared within a build configuration, meaning that
        # caches with the same name are shared between steps. Caches should be
        # treated as emphemeral and should only store items that can be
        # obtained/generated by subsequent builds.
        caches:
          maven: "/root/.m2/repository"

        # A list specifying service containers (see below) whose exposed
        # volumes should be mapped into the run container's file system.
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
        # Gauntlet) with the accompanying metadata.
        artifacts:
          artifacts/to/archive/*:
            property1: value1
            property2: value2

        # The post-build attribute commits the resulting run container as an
        # image and allows additional Docker build processing to occur. This is
        # useful for adding Docker configuration, such as EXPOSE and CMD
        # instructions, when building an image via the run task that cannot be
        # done without running a Docker build. The post-build attribute
        # functions the same way as the 'build' step attribute does, except
        # that it prepends the commited run container image to the provided
        # Dockerfile ('FROM <image>\n').
        post-build: path/to/build/context
        <or>
        post-build:
          dockerfile: |
            EXPOSE 80
            CMD /runserver.sh

Service Containers
------------------

Service containers allow you to create and start additional containers that
are linked to the primary build container. This is useful, for instance, if
your unit or integration tests require an outside service, such as a database
service. Service containers are instantiated in the order they are listed, and
service containers can rely on previously instantiated service containers.
Service containers have the same injected environment variables and volume
mounts as build containers do, but the /source mount is read-only.

The following example shows the different configuration options available
within service container configuration::

  steps:
    my-build-step
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

            # The command to run. If ommitted BuildRunner runs the command
            # configured in the Docker image without modification. If provided
            # BuildRunner always sets the container command to a shell, running
            # the given command here within the shell.
            cmd: <a command to run>

            # A collection of provisioners to run. Provisioners work similar to
            # the way Packer provisioners do and are always run within a shell.
            # When a provisioner is specified BuildRunner always sets the
            # container command to a shell, running the provisioners within the
            # shell. Currently BuildRunner supports shell and salt
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
            user: <user to run commands as>

            # The hostname assigned to the service container.
            hostname: <the hostname>

            # Custom dns servers to use in the service container.
            dns:
              - 8.8.8.8
              - 8.8.4.4

            # A custom dns search path to use in the service container.
            dns-search: mydomain.com

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
            volumes_from:
              - my-service-container

            # A map specifying ports to expose and link within other containers
            # within the step.
            ports:
              <container port>: <host port>

Here is an example of a 'run' definition that simply runs the default command
from the specified Docker image and archives the given artifacts::

  steps:
    package:
      run:
        image: releng-docker-registry.dev.ut1.omniture.com/***REMOVED***:latest
        artifacts:
          omtr_tmp/artifacts/*.x86_64.rpm: {platform: 'centos-6-x86_64'}

This example builds a custom image using a build context and Dockerfile in a
subdirectory of the project, then uses the resulting image for the run
container::

  steps:
    package:
      build: package-container
      run:
        artifacts:
          omtr_tmp/artifacts/*.x86_64.rpm:

This example uses one step to create a package and another to run an
integration test::

  steps:

    package:
      # This build context contains a Dockerfile that create an image that runs
      # mvn as the default command in the /source directory.
      build: package-container
      run:
        artifacts:
          target/*.war:

    test:
      run:
        services:
          database-server:
            image: mysql:5.7
            ports:
              3306:
          tomcat-server:
            # The build context defined here contains a Dockerfile that
            # installs the war generated in the previous step. The war is
            # available at /artifacts/package/*.war.
            build: tomcat-server-container
            ports:
              8080:
            env:
              # Pass the mysql connection string as an environment variable to
              # the container.
              DB_CONNECT_URL: jdbc:mysql://database-server:3306/dbname
        image: ubuntu:latest
        # Run a simple 'test' to verify the app is responding.
        cmd: 'curl -v http://tomcat-server:8080/myapp/test.html'

Tagging/Pushing Docker Images (the 'push' step attribute)
=========================================================

The 'push' step attribute is used to tag and push a Docker image to a remote
registry.

If a 'run' configuration is present the end state of the run container is
committed, tagged and pushed. If there is no 'run' configuration for a given
step the image produced from the 'build' configuration is tagged and pushed.

Any published Docker images are tagged with source tree branch and commit
information as well as a provided or generated build number for tracking
purposes. Additional tags may be added in the 'push' configuration.

To push the image to a registry, you mush add the --push argument to buildrunner.

The following is an example of a simple 'push' configuration where only the
repository is defined::

  steps:
    build-my-container:
      build: .
      push: releng-docker-registry.dev.ut1.omniture.com/***REMOVED***

The configuration may also specify additional tags to add to the image::

  steps:
    build-my-container:
      build: .
      push:
        repository: releng-docker-registry.dev.ut1.omniture.com/***REMOVED***
        tags: [ 'latest' ]

Remote Builds (the 'remote' step attribute)
===========================================

BuildRunner was built to utilize Docker containers for builds, but there are
times when a build or task needs to be performed within an environment that
cannot be duplicated within a Docker container. In these situations the
'remote' step attribute can be used to perform a build or task on a remote
host. A 'remote' step attribute overrides any other attributes within the step.

The 'remote' step attribute value is a map providing the host to run on, the
command to run, and information about which artifacts should be archived. The
following example shows the configuration options available within a 'remote'
configuration::

  steps:
    my-remote-step:
      remote:
        # A specific host or host alias to run the remote build/task on. A host
        # alias is an arbitrary string that can be configured to map to a
        # specific user@host value within the global buildrunner configuration
        # file. BuildRunner first tries to lookup the host value in the
        # 'build-servers' configuration map. If found the resulting host is
        # used. If not, the string here is used as the remote host.
        host: <user@host or alias to ssh to>

        # The remote command to run. (Required)
        cmd: <remote command to run>

        # A map specifying the artifacts that should be archived for the step.
        # The keys in the map specify glob patterns of files to archive. If a
        # value is present it should be a map of additional properties that
        # should be added to the build artifacts.json file. The artifacts.json
        # file can be used to publish artifacts to another system (such as
        # Gauntlet) with the accompanying metadata.
        # The "type" property may be used to signify what type of artifact
        # it is. While this field is optional and open-ended, anything that
        # ends in -test-results will be processed as test results in Jenkins.
        # Also, the platform property may be used to process RPMs correctly.
        artifacts:
          artifacts/to/archive/*:
            type: 'unit-test-results'
            property1: value1
            property2: value2
          artifacts/to/archive/*.rpm:
            platform: 'centos-6-noarch'

The 'build-servers' global configuration consists of a map where each key is a
server user@host string and the value is a list of host aliases that map to the
server::

  build-servers:
    user@myserver1: [ alias1, alias2 ]
    user@myserver2: [ alias3, alias4 ]

Namespacing aliases allows build configurations to be portable while also
allowing builders to configure BuildRunner to talk to specific servers within
their environment on a project by project basis.
