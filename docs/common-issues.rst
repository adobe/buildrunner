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
