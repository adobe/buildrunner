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
