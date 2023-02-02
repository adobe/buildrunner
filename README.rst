#############
 Buildrunner
#############

Build and publish Docker images, run builds/tasks within Docker containers or
on remote hosts.

.. contents::
   :local:

Overview
========

Buildrunner is a tool written on top of Docker and ssh remoting frameworks that
allows engineers to do the following:

- Build and publish Docker images
- Run other build and packaging tools within custom Docker containers while
  collecting the artifacts these tools produce
- Run builds/tasks on remote systems that cannot be done within a Docker
  container
- Creating ad-hoc environments using Docker containers for running automated,
  self-contained integration and functional tests

Buildrunner runs builds and tests by reading configuration files within a given
source tree. This allows build and continuous integration test configurations
to live close to source files, providing engineers the ability to update and
version the build and test configuration right along with the code that is
being built and tested. This also allows build tools and infrastructures to
very easily import and setup builds for new modules and branches.

Installation
============

There are two different options for installing Buildrunner.  Each option
depends on `Docker <http://www.docker.com/getdocker>`_.  Windows also depends
on ``BASH``, which can be found at `Git Bash <https://git-for-windows.github.io/>`_.

Pip
---

If you wish to install buildrunner directly on your local machine, install via
pip. This is best done when installing into a virtual environment using virtualenv.
The following commands will create a new virtual environment, activate it, and
install Buildrunner within it:

.. code:: bash

  virtualenv buildrunner
  source buildrunner/bin/activate
  pip install buildrunner

The buildrunner executable is now available at buildrunner/bin/buildrunner and
can be added to your path.

.. tip::

    If you are getting 404 errors for authenticated registries but you can pull them with
    ``docker pull`` - messages similar to the following:

    docker.errors.NotFound: 404 Client Error: Not Found ("manifest for <image> not found: manifest
    unknown: The named manifest is not known to the registry.")

    then you likely need to downgrade the installed python docker library version with ``pip
    install docker==3.6.0``. Version 3.7.0 broke compatibility with buildrunner and docker credential
    helpers.

Docker Container
----------------

Buildrunner can be run as a Docker container.  This works cross-platform and
is the easiest way to keep up to date.

To install, simply clone the `buildrunner repository
<https://github.com/adobe/buildrunner>`_  and add the
``scripts`` directory to your ``$PATH``.  ``scripts`` contains wrapper scripts
that pass the appropriate context to the Docker container.  There is a `BASH
<https://github.com/adobe/buildrunner/blob/master/scripts/buildrunner>`__
script and a Windows `batch file
<https://github.com/adobe/buildrunner/blob/master/scripts/buildrunner.bat>`_,
which simply calls the ``BASH`` script.

.. note:: WINDOWS USERS: This is the recommended method for Windows users, however, you must make
   sure that you are using the `BASH shell
   <https://www.laptopmag.com/articles/use-bash-shell-windows-10>`_ enhancements for Windows or that
   you have something installed that enables the use of ``sh``, or else this method will not work.
   If you are using WSL and the hyper-v installtion of docker:

   1. Click on the "Expose deamon on tcp://localhost:2375 without tls" from inside of the docker settings 
   2. Use the pip install method inside of the WSL subsystem
   3. Export your docker host ``DOCKER_HOST=tcp://localhost:2375`` inside of WSL

.. note:: MAC USERS: If you are using the docker version of buildrunner and are getting the error
   ``docker-credential-osxkeychain not installed or not available in PATH``, you can do one of 2
   things:

   1. If the authentication information for the docker registry in question is in your
      ``$HOME/.docker/config.json``, remove ``"credsStore" : "osxkeychain"`` and try again
   2. Use this `BASH <https://github.com/adobe/buildrunner/blob/master/scripts/buildrunnerOSXCredStore>`__ script along with this `python
      <https://github.com/adobe/buildrunner/blob/master/scripts/resolve-config.py>`_
      script - this will pull the docker credentials from the OSX
      keychain and inject them into the docker container

Global Configuration
====================

Buildrunner can be configured globally on a given build system to account for
installation specific properties. This feature makes project build
configuration files more portable, allowing specific Buildrunner installations
to map remote hosts and local files to aliases defined in the project build
configuration.

Example Global Configuration
----------------------------

The following example configuration explains what options are available and how
they are used when put into the global configuration file:

.. code:: yaml

  # The 'env' global configuration may be used to set environment variables
  # available to all buildrunner runs that load this config file. Env vars do
  # not need to begin with a prefix to be included in this list (i.e.
  # BUILDRUNNER_ prefix is not needed for variables listed here).
  env:
    ENV_VAR1: 'value1'
    # Values must always be strings
    ENV_VAR2: 'true''

  # The 'build-servers' global configuration consists of a map where each key
  # is a server user@host string and the value is a list of host aliases that
  # map to the server. This allows builders to configure Buildrunner to talk to
  # specific servers within their environment on a project by project basis.
  build-servers:
    user@host:
      - alias1
      - alias2

  # The 'ssh-keys' global configuration is a list of ssh key configurations.
  # The file attribute specifies the path to a local ssh private key. The key
  # attribute provides a ASCII-armored private key. Only one or the other is
  # required. If the private key is password protected the password attribute
  # specifies the password. The alias attribute is a list of aliases assigned
  # to the given key (see the "ssh-keys" configuration example of the "run"
  # step attribute below).
  ssh-keys:
  - file: /path/to/ssh/private/key.pem
    <or>
    key: |
      -----INLINE KEY-----
      ...
    password: <password if needed>
    # If set, prompt for the ssh key password.  Ignored if password is set.
    prompt-password: True/False (defaults to False)
    aliases:
      - 'my-github-key'

  # The "local-files" global configuration consists of a map where each key
  # is a file alias and the value is either the path where the file resides on
  # the local server OR the contents of the file. See the "local-files"
  # configuration example of the "run" step attribute below.  Entries in the
  # master global configuration may specify any "local-files" alias while
  # user configuration files may only specify "local-files" aliases that
  # are in the user's home directory or a path owned by the user.  Home
  # directory expansions (e.g. ``~``, ``~/foo``, ``~username`` and
  # ``~username/foo``) are honored.  The ``~`` and ``~/foo`` cases will map
  # to the home directory of the user executing buildrunner.
  # NOTE: remember to quote ``~`` in YAML files!
  local-files:
    digitalmarketing.mvn.settings: '~/.m2/settings.xml'
    some.other.file.alias: |
      The contents of the file...

  # The 'caches-root' global configuration specifies the directory to use for
  # build caches. The default directory is ~/.buildrunner/caches.
  caches-root: ~/.buildrunner/caches

  # Change the default docker registry, see the FAQ below for more information
  docker-registry: docker-mirror.example.com

  # Change the temp directory used for *most* files
  # Setting the TMP, TMPDIR, or TEMP env vars should do the same thing,
  # but on some systems it may be necessary to use this instead.
  temp-dir: /my/tmp/dir

Configuration Locations
-----------------------

Buildrunner reads the global configuration from files in the following order:

* ``/etc/buildrunner/buildrunner.yaml``
* ``${HOME}/.buildrunner.yaml``
* ``${PWD}/.buildrunner.yaml``

The configuration is read from each file in order. If a main section
exists in more than one file, the last one read in is used.  Some
entries, such as ``local-files`` will be handled differently when
appearing in the master configuration file
(``/etc/buildrunner/buildrunner.yaml`` vs. other configuration files
that can be manipulated by users).


Buildrunner Builds
==================

A Buildrunner build consists of one or more build steps.

Each step may build a custom Docker image and run a task within a specific
Docker container or run commands on a remote host.

Artifacts can be collected from tasks run within containers or remote hosts
when they have finished running and archived in your build system (Jenkins, for
instance).

Resulting images (either from a build phase or a run phase) can be committed or
pushed to the central or a private Docker image registry for use in other
builds or to run services in other environments.

Build definitions are found in the root of your source tree, either in a file
named 'buildrunner.yaml'. The build definition is simply a
yaml map defining 'steps'. Each step is given a custom name and must contain
either 'build' and/or 'run' attributes (optionally containing a 'push'
attribute) or a 'remote' attribute:

.. code:: yaml

  steps:
    step1-name:
      build: <build config>
      run: <run config>
      commit: <commit config>
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
are unique within a given ``steps`` configuration. Archived artifacts are stored
in a step-specific results directory. To use artifacts generated from a
previous step in a subsequent one you would reference them using the previous
step name.

.. note:: Artifacts from previous steps are not available within remote builds

Jinja Templating
================

The 'buildrunner.yaml' file is processed as a 
`Jinja template <http://jinja.pocoo.org/>`_, meaning the build definition can be 
modified dynamically before it is run. In addition to the environment variables 
listed below in `Running Containers`_ and the standard Jinja methods, the list 
below contains available variables and methods.

:``CONFIG_FILE``: the full path to the current file being processed (buildrunner.yaml) 
:``CONFIG_DIR``: the full path to the directory containing the current file being processed
:``read_yaml_file``: a method to read an arbitrary file in the current workspace as yaml and use the
                     contents in the script, note that the file is processed using Jinja as well and
                     that the file must exist before buildrunner is run or else this method will
                     fail

Jinja filters
-------------

:``hash_sha1``: SHA1 hash filter
:``base64encode``:  Base64 encoding filter
:``base64decode``: Base64 decoding filter
:``re_sub``: performs a regular expression replacement on text
:``re_split``: uses a pattern to split text

Steps Dependencies
==========================
Buildrunner supports specifying steps dependencies. To use this 
feature a user must specify the configuration version of ``2.0`` or higher and
also use the configuration keyword ``depends`` in the step configuration. The ``depends``
key takes a list of step names which must be completed before the execution of the 
current step.

.. code:: yaml
  
  version: 2.0
  steps:
    step1:
      run:
        image: {{ DOCKER_REGISTRY }}/ubuntu:latest
        cmd: echo "Hello from step1"
    step2:
      depends:
        - step1
        - step3
      run:
        image: {{ DOCKER_REGISTRY }}/ubuntu:latest
        cmd: echo "Hello from step 2"
    step3: 
      run:
        image: {{ DOCKER_REGISTRY }}/ubuntu:latest
        cmd: echo "Hello from step 3."  
    step4: 
      run: 
        image: {{ DOCKER_REGISTRY }}/ubuntu:latest 
        cmd: echo "Hello from step 4." 

The step execution order will be in the order it appears in the configuration
unless an dependency is defined by using ``depends``, then the order will 
change in order to satisfy the dependencies. The ``graphlib`` library is used 
to generate the directed acyclic graph and there is no guarantee how non-dependent
steps will be ordered.
An example of a step order which satisfies the dependencies in the config above:
``('step1', 'step3', 'step4', 'step2')``. Please note that there are other valid 
permutations as well.

Circular dependencies are not valid. If a circular dependency is in a configuration 
it will produce an exeception and halt the execution of buildrunner.

Standard Docker Builds (the ``build`` step attribute)
=====================================================

Buildrunner allows you to build a Docker image using a standard Dockerfile.
This is done using the top-level 'build' attribute in a step configuration. The
value of the 'build' attribute can either be a single string value indicating
the directory to use for the Docker build context (the directory containing the
Dockerfile) or a map that describes a dynamic build context and/or other build
arguments.

Here is an example of a build definition that would build a Docker image using
the root directory of the source tree as the build context (equivalent to
running 'docker build .' in the root of your source tree):

.. code:: yaml

  steps:
    build-my-container:
      build: .

If the Dockerfile is in another directory within the source tree just give the
relative path as the argument to the build attribute:

.. code:: yaml

  steps:
    build-my-container:
      build: my/container/build/context

By placing different contexts in different directories a single source tree can
produce multiple Docker images:

.. code:: yaml

  steps:
    build-container-1:
      build: container-1
    build-container-2:
      build: container-2

The value of the 'build' attribute can also be a map. The following example
shows the different configuration options available:

.. code:: yaml

  steps:
    build-my-container:
      build:
        # Define the base context directory (same as string-only value)
        path: my/container/build/context

        # The inject map specifies other files outside the build context that
        # should be included in the context sent to the Docker daemon. Files
        # injected into the build context override files with the same name/path
        # contained in the path configuration above.
        #
        # NOTE: you do not need to specify a path attribute if you inject all
        # of the files you need, including a Dockerfile
        #
        # NOTE: if the destination is a directory then it must be indicated with
        # an ending "/" or a "." component.
        inject:
          # Each entry in the map has a glob pattern key that resolves relative
          # to the source tree root with the value being the directory within
          # the build context that the file(s) should be copied to. These files
          # will be available to the Dockerfile at the given location during
          # the Docker build.  Destination directories must have a trailing
          # slash (``/``).
          glob/to/files.*: dest/dir/
          path/to/file1.txt: dest/dir/
          path/to/file2.txt: .
          path/to/file3.txt: dest/filename.txt

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
        # images--caching images significantly speeds up the building of
        # images but may not be desired when building images for publishing
        no-cache: true/false (defaults to false)

        # Specify Docker images to consider as cache sources,
        # similar to the --cache-from option used by Docker.
        # Buildrunner will attempt to pull these images from the remote registry.
        # If the pull is unsuccessful, buildrunner will still pass in the image name
        # into --cache-from, allowing a cache check in the host machine cache
        cache_from:
          - my-images/image:PR-123
          - my-images/image:latest

        # Whether to do a docker pull of the "FROM" image prior to the build.
        # This is critical if you are building from images that are changing
        # with regularity.
        # NOTE: If the image was created from a 'push' or 'commit' earlier in
        #       this ``buildrunner.yaml`` then this will default to false
        # NOTE: The command line argument ``--local-images`` can be used to temporarily
        #       override and assume ``pull: false`` for the build without rewriting
        #       ``buildrunner.yaml``.
        pull: true/false # (default changes depending on if the
                         # image was created via buildrunner or not)

        # Specify a different platform architecture when pulling and building images
        # This is useful if you are building an image for a different architecture than what
        # buildrunner is running on, such as using a linux/amd64 build node to produce an image
        # with a docker manifest compatible with an Apple M1 linux/arm64/v8 architecture
        platform: linux/amd64
        <or>
        platform: linux/arm64/v8 # an apple m1 architecture

        # Specify the build args that should be used when building your image,
        # similar to the --build-args option used by Docker
        buildargs:
          BUILD_ARG_NAME_1: BUILD_ARG_VALUE_1
          BUILD_ARG_NAME_2: BUILD_ARG_VALUE_2

        # Instead of building import the given tar file as a Docker image. If
        # this value is present all other options are ignored and the resulting
        # image is passed to subsequent steps.
        import: path/to/image/archive.tar


.. _Running Containers:

Running Containers (the ``run`` step attribute)
===============================================

The 'run' step attribute is used to create and run a Docker container from a
given image.

There are 2 reasons for running a Docker container within a build:

1. To run another build tool or test framework and collect the resulting
   artifacts
2. To run scripts and operations within an existing image to create a new image
   (similar to how Packer_ creates Docker images)

Buildrunner injects special environment variables and volume mounts into every
run container. The following environment variables are set and available in
every run container:

:``BUILDRUNNER_BUILD_NUMBER``: the build number
:``BUILDRUNNER_BUILD_ID``: a unique id identifying the build (includes vcs and build number
                           information), e.g. "main-1791.Ia09cc5.M0-1661374484"
:``BUILDRUNNER_BUILD_DOCKER_TAG``: identical to ``BUILDRUNNER_BUILD_ID`` but formatted for
                                   use as a Docker tag
:``BUILDRUNNER_BUILD_TIME``: the "unix" time or "epoch" time of the build (in seconds)
:``BUILDRUNNER_STEP_ID``: a UUID representing the step
:``BUILDRUNNER_STEP_NAME``: The name of the Buildrunner step
:``BUILDRUNNER_STEPS``: the list of steps manually specified on the command line,
                        defaults to an empty list
:``BUILDRUNNER_INVOKE_USER``: The username of the user that invoked Buildrunner
:``BUILDRUNNER_INVOKE_UID``: The UID of the user that invoked Buildrunner
:``BUILDRUNNER_INVOKE_GROUP``: The group of the user that invoked Buildrunner
:``BUILDRUNNER_INVOKE_GID``: The GID (group ID) of the user that invoked Buildrunner
:``VCSINFO_NAME``: the VCS repository name without a path, "my-project"
:``VCSINFO_BRANCH``: the VCS branch, e.g. "main"
:``VCSINFO_NUMBER``: the VCS commit number, e.g. "1791"
:``VCSINFO_ID``: the VCS commit id, e.g. "a09cc5c407af605b57a0f16b73f896873bb74759"
:``VCSINFO_SHORT_ID``: the VCS short commit id, e.g. "a09cc5c"
:``VCSINFO_RELEASE``: the VCS branch state, .e.g. "1791.Ia09cc5.M0"
:``VCSINFO_MODIFIED``: the last file modification timestamp if local changes have been made and not
                       committed to the source VCS repository, e.g. "1661373883"

The following volumes are created within run containers:

:``/source``: (read-write) maps to a pristine snapshot of the current source tree (build directory)
:``/artifacts``: (read-only) maps to the buildrunner.results directory

The /source volume is actually a mapped volume to a new source container
containing a copy of the build source tree. This container is created from a
docker image containing the entire source tree. Files can be excluded from this
source image by creating a '.buildignore' file in the root of the source tree.
This file follows the same conventions as a .dockerignore file does when
creating Docker images.

The following example shows the different configuration options available in
the run step:

.. code:: yaml

  # Optional buildrunner configuration syntax version
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
        xfail: <boolean>

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
          <container port>: <host port>

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
            [format: uncompressed]
            [type: tar|zip]
            [compression: gz|bz2|xz|lzma|lzip|lzop|z]
            [push: true|false]
            property1: value1
            property2: value2

        # Whether or not to pull the image from upstream prior to running
        # the step.  This is almost always desirable, as it ensures the
        # most up to date source image.
        # NOTE: If the image was created from a 'push' or 'commit' earlier in
        #       this ``buildrunner.yaml`` then this will default to false
        pull: true/false # (default changes depending on if the
                         # image was created via buildrunner or not)

        # Specify a different platform architecture when pulling and running images.
        # This is useful if you are running an image that was built for a different architecture
        # than what buildrunner is running on, such as using a linux/arm64/v8 Apple M1 architecture
        # development machine to run or test an image built for linux/amd64 architecture.
        platform: linux/amd64
        <or>
        platform: linux/arm64/v8 # an apple m1 architecture

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
        systemd: true/false

        # Docker supports certain kernel capabilities, like 'SYS_ADMIN'.
        # see https://goo.gl/gTQrqW for more infromation on setting these.
        cap_add: 'SYS_ADMIN'
        <or>
        cap_add:
          - 'SYS_ADMIN'
          - 'SYS_RAWIO'

        # Docker can run in a privileged mode. This allows access to all devices
        # on the host. Using privileged is rare, but there are good use cases
        # for this feature. see https://goo.gl/gTQrqW for more infromation on
        # setting these.
        # Default: false
        privileged: true/false

        # The post-build attribute commits the resulting run container as an
        # image and allows additional Docker build processing to occur. This is
        # useful for adding Docker configuration, such as EXPOSE and CMD
        # instructions, when building an image via the run task that cannot be
        # done without running a Docker build. The post-build attribute
        # functions the same way as the 'build' step attribute does, except
        # that it prepends the committed run container image to the provided
        # Dockerfile ('FROM <image>\n').
        post-build: path/to/build/context
        <or>
        post-build:
          dockerfile: |
            EXPOSE 80
            CMD /runserver.sh

        # A list of container names or labels created within any run container
        # that buildrunner should clean up.  (Use if you call
        # 'docker run --name <name>' or 'docker run --label <label>' within a run container.)
        containers:
          - container1
          - container2

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
within service container configuration:

.. code:: yaml

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
            dns-search: mydomain.com

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
              <container port>: <host port>

            # Whether or not to pull the image from upstream prior to running
            # the step.  This is almost always desirable, as it ensures the
            # most up to date source image.  There are situations, however, when
            # this can be set to false as an optimization.  For example, if a
            # container is built at the beginning of a buildrunner file and then
            # used repeatedly.  In this case, it is clear that the cached version
            # is appropriate and we don't need to check upstream for changes.
            pull: true/false (defaults to true)

            # See above
            systemd: true/false

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
            inject-ssh-agent: true/false (defaults to false)

Here is an example of a 'run' definition that simply runs the default command
from the specified Docker image and archives the given artifacts:

.. code:: yaml

  steps:
    package:
      run:
        image: myimages/image-with-cmd:latest
        artifacts:
          build/artifacts/*.x86_64.rpm: {platform: 'centos-8-x86_64'}

This example builds a custom image using a build context and Dockerfile in a
subdirectory of the project, then uses the resulting image for the run
container:

.. code:: yaml

  steps:
    package:
      build: package-container
      run:
        artifacts:
          build/artifacts/*.x86_64.rpm:

This example uses one step to create a package and another to run an
integration test:

.. code:: yaml

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

Tagging/Pushing Docker Images
=============================

The 'commit' or 'push' step attributes are used to tag and push a Docker image
to a remote registry. The 'commit' attribute is used to tag the image to be
used in later steps, while the 'push' attribute is used to tag the image and
push it. Each is configured with the same properties.

If a 'run' configuration is present the end state of the run container is
used for committing or pushing. If there is no 'run' configuration for a given
step the image produced from the 'build' configuration is tagged and pushed.

Any published Docker images are tagged with source tree branch and commit
information as well as a provided or generated build number for tracking
purposes. Additional tags may be added in the 'commit' or 'push' configuration.

To push the image to a registry, you must add the --push argument to buildrunner.

The following is an example of simple configuration where only the repository
is defined:

.. code:: yaml

  steps:
    build-my-container:
      build: .
      # To push the docker image to a registry
      push: myimages/image1
      # OR to just commit it locally to use in subsequent steps
      commit: myimages/image1

The configuration may also specify additional tags to add to the image:

.. code:: yaml

  steps:
    build-my-container:
      build: .
      # To push the docker image to a registry
      push:
        repository: myimages/image1
        tags: [ 'latest' ]
      # OR to just commit it locally to use in subsequent steps
      commit:
        repository: myimages/image1
        tags: [ 'latest' ]

The configuration may also specify multiple repositories with their own tags
(each list entry may be a string or specify additional tags):

.. code:: yaml

  steps:
    build-my-container:
      build: .
      # To push the docker image to multiple repositories
      push:
        - myimages/image1
        - repository: myimages/image2
          tags: [ 'latest' ]
      # OR to just commit it locally to use in subsequent steps
      commit:
        repository: myimages/image1
        tags: [ 'latest' ]

Pushing One Image To Multiple Repositories
------------------------------------------

To push a single image to multiple repositories, use a list for the push or commit
configuration. Note that each list entry may be a string or a dictionary with
additional tags.

.. code:: yaml+jinja

  steps:
    build-my-container:
      build: .
      push:
        - repository: myimages/image1
          tags: [ 'latest' ]
        - myimages/image2
        - repository: myimages/image3
          tags: [ 'latest' ]
      # OR
      commit:
        - repository: myimages/image1
          tags: [ 'latest' ]
        - myimages/image2
        - repository: myimages/image3
          tags: [ 'latest' ]

Pushing To PyPI Repository
==========================
The 'pypi-push' step attribute is used to push a python package to a remote PyPI
repository. If an artifact with a type of ``python-sdist`` is present in the artifacts
for the step, those packages will be pushed.

The push only occurs if the --push argument is used, similar to how pushing docker
images to remote docker registries works

The following is an example of a simple 'pypi-push' configuration where only the
repository index, as defined in the ``~/.pypirc`` file, is defined:

.. code:: yaml

  steps:
    pypi:
      run:
        image: python:2
        cmds:
          - python setup.py sdist
        artifacts:
          "dist/*.tar.gz": { type: 'python-sdist' }
      pypi-push: artifactory-releng

The configuration may also specify repository, username, and password. All must be specified when
doing this:

.. code:: yaml

  steps:
    pypi:
      run:
        image: python:2
        cmds:
          - python setup.py sdist
        artifacts:
          "dist/*.tar.gz": { type: 'python-sdist' }
      pypi-push:
        repository: https://artifactory.example.com/artifactory/api/pypi/pypi-myownrepo
        username: myuser
        password: mypass

Publishing Ports
================

In order to publish ports listed in the 'run' step attribute (not on a service
container), you must pass the --publish-ports argument to buildrunner.

This must never be used on a shared server such as a build server as it could
cause port mapping conflicts.


Remote Builds (the 'remote' step attribute)
===========================================

Buildrunner was built to utilize Docker containers for builds, but there are
times when a build or task needs to be performed within an environment that
cannot be duplicated within a Docker container. In these situations the
'remote' step attribute can be used to perform a build or task on a remote
host. A 'remote' step attribute overrides any other attributes within the step.

The 'remote' step attribute value is a map providing the host to run on, the
command to run, and information about which artifacts should be archived. The
following example shows the configuration options available within a 'remote'
configuration:

.. code:: yaml

  steps:
    my-remote-step:
      remote:
        # A specific host or host alias to run the remote build/task on. A host
        # alias is an arbitrary string that can be configured to map to a
        # specific user@host value within the global buildrunner configuration
        # file. Buildrunner first tries to lookup the host value in the
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
server:

.. code:: yaml

  build-servers:
    user@myserver1: [ alias1, alias2 ]
    user@myserver2: [ alias3, alias4 ]

Namespacing aliases allows build configurations to be portable while also
allowing builders to configure Buildrunner to talk to specific servers within
their environment on a project by project basis.


Fetching Files
==============

Buildrunner has a ``fetch`` facility for retrieving files and artifactes to incorporate into the
build.  The syntax for referencing a back-end uses a simple URL format:

.. code:: yaml

  ``BACKEND://REPOSITORY/PATH``

:``BACKEND``: The fetch back-end to use: ``github``, ``http``, ``file``, *etc*.
:``REPOSITORY``: Which location/repository the ``BACKEND`` will reference.  This is a *label* that
                 is used as a reference into configuration found in Buildrunner configuration files
                 (e.g. ``~/.buildrunner.yaml``) where a full description of connection parameters
                 and available (see specific documentation for each fetch module).
:``PATH``: The unique path or ID of the artifact found in the ``REPOSITORY``.


Fetch Backends
--------------

The available ``fetch`` back-ends are the following:

* Github: fetches files from Github
* File: fetches files from the file system
* HTTP/HTTPS: fetches files from HTTP/HTTPS servers


Github
``````

Files can be retrieved from Github - either central ``github.com`` location or
GitHub Enterprise servers. The fetch syntax is the following:

  ``github://LABEL/GROUP/REPO/PATH``

:``github://``: scheme indicates fetching using the ``github`` facility.
:``LABEL``: a look-up key into Buildrunner configuration that describes connection parameters.  This
            is an arbitrary name but benefits from uniform use across build sources.
:``GROUP``: Github organization/group.
:``REPO``: Git repository in the ``GROUP``.
:``PATH``: path to the file in the Git ``REPO``.

The ``github://`` facility requires the following configuration entries:

.. code:: yaml

  github:
    LABEL:
      endpoint: 'https://HOSTNAME/API_PATH'
      version: 'VERSION'
      username: 'USERNAME'
      app_token: 'APP_TOKEN'

The following is suggested for an entry to reference files for GitHub Enterprise:

.. code:: yaml

  github:
    company_github:
      endpoint: 'https://git.company.com/api'
      version: 'v3'
      username: 'USERNAME'
      app_token: 'APP_TOKEN'

:username: The individual username used to access the Github Enterprise instance.
:app_token: The user-specific application token generated by the user on Github for Buildrunner
            access.  It is a 40 hex digit token.


File
````

Files can be retrieved from the local file system.  The initial ``file://`` scheme is optional.
These two are equivalent:

* ``file:///some/path/to/a/file.ext``
* ``/some/path/to/a/file.ext``

If a relative path from the source directory is to be designated then the ``file://`` scheme cannot
be used:

.. code:: yaml

  relative/path/to/a/file.ext


HTTP/HTTPS
``````````

This is stubbed-out and not yet implemented.


Redirecting ``buildrunner.yaml``
--------------------------------

The ``buildrunner.yaml`` file can be retrieved from a remote location using the ``fetch`` facility.
This allows a collection of builds to have a centrally-managed ``buildrunner.yaml`` which avoids
problems in updating and synchronizing copies to possibly unknown locations.

To redirect ``buildrunner.yaml`` only a single entry should be in the file:

  redirect: 'github://gh-label/org/repo/sample-buildrunner.yaml'

Buildrunner will repeatedly redirect, fetch and interpret the new ``buildrunner.yaml`` until it
finds one that no longer finds a ``redirect`` directive.  At that point it will interpret the final
``buildrunner.yaml``.  It will **not** merge entries from earlier, redirecting ``buildrunner.yaml``
files - all other content is ignored when the ``redirect`` directive is found.

Cleaning Cache
==============

Buildrunner keeps a local cache in the ``~/.buildrunner/caches`` directory, which can be overridden
by the `caches-root` global configuration parameter, that will grow over time and should be cleaned
out periodically. There are two methods for cleaning this cache.

clean-cache parameter
---------------------

You can pass in the ``--clean-cache`` parameter with any execution of ``buildrunner``, and the cache
will be cleaned out prior to the build.

.. code:: bash

  buildrunner --clean-cache

buildrunner_cleanup command
---------------------------

There is a stand-alone command that just cleans up the cache. This command takes no parameters.

.. code:: bash

  buildrunner_cleanup

Common Issues
=============

**WARNING**: Always update to the latest version of buildrunner before troubleshooting as new features
may be required.

Docker Hub rate limit
---------------------

In November 2020, Docker Hub added rate limiting for all docker images to 100 pulls every 6 hours.
Sometimes it is necessary to use a different upstream registry instead of the default Docker Hub
registry (docker.io). This requires that any references to images that would be pulled from Docker
Hub instead reference a variable for the configured upstream docker registry.

To configure which registry is used, add the following line to the global configuration file:
(typically ``~/.buildrunner.yaml``):

.. code:: yaml

    docker-registry: docker-mirror.example.com

This will point to the Docker Hub proxy located at docker-mirror.example.com. Note that this registry
does not actually exist and is just an example.

To use this registry, see the following examples. Each example assumes the image to be pulled is
``busybox:latest``.

To use the registry in ``buildrunner.yaml``:

.. code:: yaml+jinja

    steps:
      step1:
        run:
          image: {{ DOCKER_REGISTRY }}/busybox:latest

To use the registry in a ``Dockerfile``:

.. code:: dockerfile

    ARG DOCKER_REGISTRY
    FROM $DOCKER_REGISTRY/busybox:latest

Caution when using ``latest`` tag
---------------------------------

A race condition exists when pushing a docker image with a static tag such as ``latest``.

The Scenario
````````````

Not every project will be impacted by this problem, and understanding the problem will help you know if you need to
account for it. The basic scenario is as follows:

- job 1 builds the docker image ``XYZ`` and tags it latest
- job 2 starts and pulls the ``XYZ:latest`` image, overwriting the newly built ``XYZ:latest`` image
- job 1 pushes the older ``XYZ:latest`` image, because it was overwritten by job 2

Solutions
`````````

A couple of potential solutions are:

- tag the image as ``latest`` as the last step/steps
- tag and pushing ``latest`` outside of buildrunner after it is done (e.g. in a subsequent deployment pipeline, etc)

Neither of these solutions are perfect, but both significantly shrink the chance of encountering the race condition.

Contributing
============

Pull requests are welcome to the project, please see the
`contribution guidelines <.github/CONTRIBUTING.md>`_.

The test suite is located in the `tests subdirectory <tests>`_. These tests are invoked
on every PR build and every build.

The test suite can be invoked manually from the top of the source directory by using
``pytest`` after installing all of the requirements and test requirements with ``pip``.


.. Links
.. _Packer: https://www.packer.io/
