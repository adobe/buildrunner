################
 Fetching Files
################

**WARNING**: Always update to the latest version of buildrunner before troubleshooting as new features
may be required.

.. contents::
   :local:

Docker Hub rate limit
#####################

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

``latest`` tag race conditions
##############################

A race condition exists when pushing a docker image with a static tag such as ``latest``.

The Scenario
============

Not every project will be impacted by this problem, and understanding the problem will help you know if you need to
account for it. The basic scenario is as follows:

- job 1 builds the docker image ``XYZ`` and tags it latest
- job 2 starts and pulls the ``XYZ:latest`` image, overwriting the newly built ``XYZ:latest`` image
- job 1 pushes the older ``XYZ:latest`` image, because it was overwritten by job 2

Solutions
=========

A couple of potential solutions are:

- tag the image as ``latest`` as the last step/steps
- tag and pushing ``latest`` outside of buildrunner after it is done (e.g. in a subsequent deployment pipeline, etc)

Neither of these solutions are perfect, but both significantly shrink the chance of encountering the race condition.

Container cleanup on build abort
#################################

When a build is interrupted (e.g. a CI system sends ``SIGTERM`` to abort a superseded PR build),
buildrunner needs to clean up the Docker containers it started. Without proper cleanup, containers
running ``/usr/sbin/init`` (systemd) or ``/run.sh`` (sshd) will remain running indefinitely,
accumulating over time and consuming disk, memory, and network resources on the build agent.

How cleanup works
=================

Buildrunner tracks every Docker container it starts in a global registry. Cleanup happens in two ways:

1. **Normal exit**: Each build step has a ``finally`` block that calls ``cleanup()`` on all containers
   it created (the build container, service containers, SSH agent, Docker daemon proxy, and source
   container). These ``finally`` blocks run on normal completion, exceptions, and ``sys.exit()``.

2. **Signal-based cleanup**: A ``SIGTERM`` or ``SIGINT`` handler is installed at startup. When the
   signal is received, the handler force-removes all registered containers via
   ``docker remove --force`` and then calls ``os._exit()`` to terminate immediately. This covers
   the case where the process is killed externally before ``finally`` blocks can run.

The signal handler uses ``os._exit()`` (not ``sys.exit()``) to avoid triggering ``finally`` blocks
after cleanup has already been performed, which would cause race conditions and double-removal
attempts.

Limitations
===========

- ``SIGKILL`` (``kill -9``) cannot be caught by any handler. If the process is killed with
  ``SIGKILL``, containers will be orphaned. CI systems should always send ``SIGTERM`` first and
  allow time for cleanup before escalating to ``SIGKILL``.

- Containers started *inside* a buildrunner container (e.g. via testcontainers or direct
  ``docker run`` commands within a build step) are not tracked by the cleanup registry. These
  child containers must be cleaned up by the code that started them.

- If the Docker daemon is unreachable when the signal handler runs, cleanup will fail silently
  and a warning will be printed to stderr.

Diagnosing orphaned containers
==============================

Containers started by buildrunner are labeled with the labels passed via ``--container-labels``.
To find orphaned buildrunner containers on an agent:

.. code:: bash

    # List all containers with buildrunner labels (adjust label key to match your setup)
    docker ps -a --filter label=com.example.build.source=buildrunner

    # Force-remove all orphaned buildrunner containers
    docker ps -q --filter label=com.example.build.source=buildrunner | xargs -r docker rm -f

Utilizing multi-platform base images
####################################

At times, you may want to build a base multi-platform image and then use that base image to build
another multi-platform image. Consider the following example:

.. code:: yaml

    steps:
      build-base:
        build:
          dockerfile: |
            FROM {{ DOCKER_REGISTRY }}/busybox:latest
            CMD /do-something-cool
          platforms:
            - linux/amd64
            - linux/arm64/v8
        push: test-image1

      build-from-base:
        build:
          dockerfile: |
            FROM test-image1:{{ BUILDRUNNER_BUILD_DOCKER_TAG }}
            CMD /do-something-else
          platforms:
            - linux/amd64
            - linux/arm64/v8
        push: test-image2

In this case, the ``build-from-base`` step will likely fail for platforms that are not
configured (via Docker buildx) to run on the local machine since the base image will not exist.

The solution in this case is to use a single multi-stage Dockerfile instead. For example:

.. code:: dockerfile

    # Put this in a common Dockerfile used by both build steps below
    FROM {{ DOCKER_REGISTRY }}/busybox:latest AS stage1
    CMD /do-something-cool
    FROM stage1 AS stage2
    CMD /do-something-else

.. code:: yaml


.. code:: yaml

    steps:
      build-base:
        build:
          path: .
          platforms:
            - linux/amd64
            - linux/arm64/v8
          target: stage1
        push: test-image1

      build-from-base:
        build:
          path: .
          platforms:
            - linux/amd64
            - linux/arm64/v8
          target: stage2
        push: test-image2
