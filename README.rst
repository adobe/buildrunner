===========
BuildRunner
===========

Overview
========

BuildRunner is a tool written on top of Docker that allows engineers to do the
following:

1. Build and publish Docker images
2. Run other build and packaging tools within custom Docker containers while
   collecting the artifacts these tools produce
3. Creating ad-hoc environments using Docker containers for running automated,
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

BuildRunner Builds
==================

A BuildRunner build consists of one or more build steps.

Each step may build a custom Docker image and/or run a specific image to
perform some task.

Artifacts can be collected from containers when they have finished running and
archived in your build system (Jenkins, for instance).

Resulting images (either from a build phase or a run phase) can be pushed to
the central or private Docker image registries for use in other builds or to
run services in other environments.

Build definitions are found in the root of your source tree, either in a file
named 'buildrunner.yaml' or 'gauntlet.yaml'. The build definition is simply a
yaml map defining 'steps'. Each step is given a custom name and must contain
'build' and/or 'run' attributes and may optionally contain a 'push' attribute::

  steps:
    step1-name:
      build: <build config>
      run: <run config>
      push: <push config>
    step2-name:
      build: <build config>
      run: <run config>
      push: <push config>

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
        # should be included in the context sent to the Docker # daemon
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

        # Whether to use the default Docker image cache for intermediate
        # images--this significantly speeds up building images but may not be
        # desired when building images for publishing
        no-cache: true/false (defaults to false)

Running Docker Containers (the 'run' step attribute)
====================================================

TODO

2 reasons to run Docker containers::

1. Run a build or test and collect the artifacts.
2. Modify an image to be saved as a new version (ala Packer)

Tagging/Pushing Docker Images (the 'push' step attribute)
=========================================================

TODO

Any published Docker images are tagged with source tree branch and commit
information as well as a provided or generated build number for tracking
purposes. The same version and build information is passed to running Docker
containers as environment variables so plugin images can be configured to use
them when producing other types of artifacts.

