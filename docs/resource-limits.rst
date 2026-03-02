####################################
 CPU and Memory Resource Limits
####################################

Overview
========

This feature adds the ability to specify CPU and memory limits for Docker containers in buildrunner configurations. These limits are passed to Docker's ``create_host_config`` method, allowing fine-grained control over container resource usage.

.. contents::
   :local:

Configuration Options
=====================

The following resource limit fields are available for both run steps and service containers:

- ``mem-limit``: Memory limit (string like "512m", "1g" or integer in bytes)
- ``cpu-shares``: CPU shares (relative weight, default is 1024)
- ``cpu-period``: CPU period in microseconds (default is 100000)
- ``cpu-quota``: CPU quota in microseconds

Usage Examples
==============

Memory Limit
------------

.. code:: yaml

  steps:
    my-step:
      run:
        image: ubuntu:20.04
        mem-limit: "512m"  # or 536870912 for bytes
        cmd: echo "Running with memory limit"

CPU Limits
----------

.. code:: yaml

  steps:
    my-step:
      run:
        image: ubuntu:20.04
        cpu-shares: 512      # Relative weight (default 1024)
        cpu-period: 100000   # Period in microseconds
        cpu-quota: 50000     # Quota in microseconds (50% of one CPU)
        cmd: echo "Running with CPU limits"

Combined Limits
---------------

.. code:: yaml

  steps:
    my-step:
      run:
        image: ubuntu:20.04
        mem-limit: "1g"
        cpu-shares: 1024
        cpu-period: 100000
        cpu-quota: 100000
        cmd: echo "Running with all limits"

Service Container Limits
-------------------------

.. code:: yaml

  steps:
    my-step:
      run:
        image: ubuntu:20.04
        services:
          database:
            image: postgres:13
            mem-limit: "256m"
            cpu-shares: 512
            env:
              POSTGRES_PASSWORD: example
        cmd: echo "Main container with limited database service"

Docker Resource Limit Parameters
=================================

Memory Limit (``mem-limit``)
-----------------------------

- **Accepts**: String (e.g., "512m", "1g", "2g") or integer (bytes)
- **Description**: Sets the maximum amount of memory the container can use
- **Behavior**: Docker will enforce this limit and may kill the container if exceeded

CPU Shares (``cpu-shares``)
----------------------------

- **Accepts**: Integer
- **Default**: 1024
- **Description**: Relative weight for CPU time allocation
- **Behavior**: Higher values get more CPU time when there's contention

CPU Period (``cpu-period``)
----------------------------

- **Accepts**: Integer (microseconds)
- **Default**: 100000 (100ms)
- **Description**: Defines the period for CPU quota enforcement

CPU Quota (``cpu-quota``)
--------------------------

- **Accepts**: Integer (microseconds)
- **Description**: Limits CPU time within the period
- **Example**: quota=50000, period=100000 = 50% of one CPU core

Implementation Details
======================

Configuration Model
-------------------

Resource limit fields are defined in the ``RunAndServicesBase`` class in ``buildrunner/config/models_step.py``. These fields are inherited by both ``StepRun`` and ``Service`` configurations.

Docker Runner
-------------

The ``DockerRunner.start()`` method in ``buildrunner/docker/runner.py`` accepts resource limit parameters and passes them to Docker's ``create_host_config`` method.

Run Task Integration
--------------------

The run task layer in ``buildrunner/steprunner/tasks/run.py`` extracts resource limits from step and service configurations and passes them to the Docker runner for both main containers and service containers.

See Also
========

- :doc:`global-configuration` - Global buildrunner configuration options
- ``examples/resource-limits-example.yaml`` - Complete working examples

