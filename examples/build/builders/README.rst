==================
Builders Example
==================

This example demonstrates how to use Buildrunner with custom builders and random builder selection.

Platform Builders Configuration
===============================

The ``platform-builders`` configuration allows you to specify which builders to use for different platforms. When multiple builders are available for a platform, Buildrunner will randomly select one to distribute the load.

Configuration Options
---------------------

1. **Multiple builders per platform** (recommended for load balancing):

   .. code-block:: yaml

       platform-builders:
         linux/amd64:
           - builder1
           - builder2
           - builder3
         linux/arm64:
           - builder4
           - builder5

2. **Single builder per platform**:

   .. code-block:: yaml

       platform-builders:
         linux/amd64: builder1
         linux/arm64: builder2


Random Selection
----------------

When multiple builders are configured for a platform, Buildrunner will randomly select one builder for each build. This helps distribute the build load across available builders and can improve build performance by utilizing multiple build resources.

How to Run
==========

1. **Create builders**

   From the base directory, run:

   .. code-block:: sh

       python examples/build/builders/create_builders.sh

2. **Run build with example configuration file**

   From the base directory, run the following command:

   .. code-block:: sh

       ./run-buildrunner.sh -f examples/build/builders/buildrunner.yaml -c examples/build/builders/global-config.yaml

   or

   .. code-block:: sh

       ./run-buildrunner.sh -f examples/build/builders/buildrunner.yaml -c examples/build/builders/global-config-list.yaml

3. **Remove builders**

   From the base directory, run:

   .. code-block:: sh

       python examples/build/builders/remove_builders.sh
