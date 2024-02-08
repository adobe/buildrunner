###############
 Remote Builds
###############

Buildrunner was built to utilize Docker containers for builds, but there are
times when a build or task needs to be performed within an environment that
cannot be duplicated within a Docker container. In these situations the
'remote' step attribute can be used to perform a build or task on a remote
host. A 'remote' step attribute overrides any other attributes within the step.

Usage
#####

The 'remote' step attribute value is a map providing the host to run on, the
command to run, and information about which artifacts should be archived. The
following example shows the configuration options available within a 'remote'
configuration:

.. code:: yaml

  steps:
    my-remote-step:
      remote:
        # A specific host or host alias to run the remote build/task on. A host
        # alias is an arbitrary string that can be configured to map to a
        # specific user@host value within the global buildrunner configuration
        # file. Buildrunner first tries to lookup the host value in the
        # 'build-servers' configuration map. If found the resulting host is
        # used. If not, the string here is used as the remote host.
        host: <user@host or alias to ssh to>

        # The remote command to run. (Required)
        cmd: <remote command to run>

        # A map specifying the artifacts that should be archived for the step.
        # The keys in the map specify glob patterns of files to archive. If a
        # value is present it should be a map of additional properties that
        # should be added to the build artifacts.json file. The artifacts.json
        # file can be used to publish artifacts to another system (such as
        # Gauntlet) with the accompanying metadata.
        # The "type" property may be used to signify what type of artifact
        # it is. While this field is optional and open-ended, anything that
        # ends in -test-results will be processed as test results in Jenkins.
        # Also, the platform property may be used to process RPMs correctly.
        artifacts:
          artifacts/to/archive/*:
            type: 'unit-test-results'
            property1: value1
            property2: value2
          artifacts/to/archive/*.rpm:
            platform: 'centos-6-noarch'

The 'build-servers' global configuration consists of a map where each key is a
server user@host string and the value is a list of host aliases that map to the
server:

.. code:: yaml

  build-servers:
    user@myserver1: [ alias1, alias2 ]
    user@myserver2: [ alias3, alias4 ]

Namespacing aliases allows build configurations to be portable while also
allowing builders to configure Buildrunner to talk to specific servers within
their environment on a project by project basis.