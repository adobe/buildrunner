==================================
Buildrunner Example Configurations
==================================

This directory contains example configuration files for Buildrunner, demonstrating various use cases and best practices. These examples serve as references for users looking to configure and execute Buildrunner effectively.

Running Buildrunner with Example Configuration Files
====================================================

To run Buildrunner using an example configuration file, follow these steps from the root directory of the Buildrunner repository:

1. **Navigate to the Buildrunner repository directory.**

2. **Execute Buildrunner with a specified configuration file:**
    .. code-block:: sh

        PYTHONPATH=. ./bin/buildrunner -f examples/<path-to-config-file>

    *Example:*

    .. code-block:: sh

      PYTHONPATH=. ./bin/buildrunner -f examples/build/basic/buildrunner.yaml

Adding a New Example Configuration File
=======================================

To contribute a new example configuration file, adhere to the following guidelines:

1. **File Location & Naming**
   - Place the new file in the ``examples/`` directory.
   - Ensure the filename ends with ``.buildrunner.yaml`` to allow automatic detection and execution by unit tests.

2. **Configuration Validity**
   - The configuration file must contain a valid Buildrunner configuration.
   - It should execute successfully using the standard instructions provided in this repository without requiring any manual intervention.

3. **Documentation & Additional Files**
   - If necessary, include a ``README.rst`` file in the same directory as the configuration file to provide additional details or instructions.
   - Any supporting files required for the configuration should be placed alongside the configuration file.

Following these best practices ensures consistency, maintainability, and ease of use for all contributors and users.