#!/bin/bash

# This script will run the local buildrunner code from the root of the project
#
# To get help, run the following command:
#   ./run-buildrunner.sh --help
#
# To run the buildrunner with a specific configuration file, run the following command:
#   ./run-buildrunner.sh -f examples/build/basic/buildrunner.yaml
PYTHONPATH=. ./bin/buildrunner --cleanup-images "$@"