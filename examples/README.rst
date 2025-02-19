==================================
Buildrunner Example Configurations
==================================

This directory contains several example configuration files for Buildrunner.

Running Buildrunner with Example Configuration Files
""""""""""""""""""""""""""""""""""""""""""""""""""""

To run Buildrunner using the example configuration files, execute the following commands from
the top-level directory within the Buildrunner repository.


1. **Install Buildrunner:**

   .. code-block:: sh

      pip install .

2. **Run Buildrunner:**

   .. code-block:: sh

      ./bin/buildrunner -f examples/<name_of_config_file>

   For example:

   .. code-block:: sh

      ./bin/buildrunner -f examples/configs/build/basic/buildrunner.yaml

Adding New Example Configuration Files
""""""""""""""""""""""""""""""""""""""
To add a new example configuration file, add a new file under the `examples/` directory. The new file should end with ``buildrunner.yaml`` to ensure that
the unit tests can automatically detect and run the new example configuration file. The new file should contain a valid Buildrunner configuration and should be able
to run successfully using the instructions provided above with no other manual setup. If needed, add a README.rst file to the same directory as the configuration file
to provide additional information. Any additional files needed by the configuration should be colocated with the configuration file.