#!/bin/bash

# This script will run the local buildrunner code from the root of the project
# ./run-buildrunner.sh --help
# ./run-buildrunner.sh -f examples/build/basic/buildrunner.yaml
PYTHONPATH=. ./bin/buildrunner --cleanup-images "$@"