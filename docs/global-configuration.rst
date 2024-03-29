######################
 Global Configuration
######################

Buildrunner can be configured globally on a given build system to account for
installation specific properties. This feature makes project build
configuration files more portable, allowing specific Buildrunner installations
to map remote hosts and local files to aliases defined in the project build
configuration.

.. contents::
   :local:

Example Global Configuration
============================

The following example configuration explains what options are available and how
they are used when put into the global configuration file:

.. code:: yaml

  # The 'env' global configuration may be used to set environment variables
  # available to all buildrunner runs that load this config file. Env vars do
  # not need to begin with a prefix to be included in this list (i.e.
  # BUILDRUNNER_ prefix is not needed for variables listed here).
  env:
    ENV_VAR1: 'value1'
    # Values must always be strings
    ENV_VAR2: 'true''

  # The 'build-servers' global configuration consists of a map where each key
  # is a server user@host string and the value is a list of host aliases that
  # map to the server. This allows builders to configure Buildrunner to talk to
  # specific servers within their environment on a project by project basis.
  build-servers:
    user@host:
      - alias1
      - alias2

  # The 'ssh-keys' global configuration is a list of ssh key configurations.
  # The file attribute specifies the path to a local ssh private key. The key
  # attribute provides a ASCII-armored private key. Only one or the other is
  # required. If the private key is password protected the password attribute
  # specifies the password. The alias attribute is a list of aliases assigned
  # to the given key (see the "ssh-keys" configuration example of the "run"
  # step attribute below).
  ssh-keys:
  - file: /path/to/ssh/private/key.pem
    <or>
    key: |
      -----INLINE KEY-----
      ...
    password: <password if needed>
    # If set, prompt for the ssh key password.  Ignored if password is set.
    prompt-password: True/False (defaults to False)
    aliases:
      - 'my-github-key'

  # The "local-files" global configuration consists of a map where each key
  # is a file alias and the value is either the path where the file resides on
  # the local server OR the contents of the file. See the "local-files"
  # configuration example of the "run" step attribute below.  Entries in the
  # master global configuration may specify any "local-files" alias while
  # user configuration files may only specify "local-files" aliases that
  # are in the user's home directory or a path owned by the user.  Home
  # directory expansions (e.g. ``~``, ``~/foo``, ``~username`` and
  # ``~username/foo``) are honored.  The ``~`` and ``~/foo`` cases will map
  # to the home directory of the user executing buildrunner.
  # NOTE: remember to quote ``~`` in YAML files!
  local-files:
    digitalmarketing.mvn.settings: '~/.m2/settings.xml'
    some.other.file.alias: |
      The contents of the file...

  # Specifies the directory to use for the build caches, the default directory
  # is ~/.buildrunner/caches
  caches-root: ~/.buildrunner/caches

  # Change the default docker registry, see the FAQ below for more information
  docker-registry: docker-mirror.example.com

  # Change the temp directory used for *most* files
  # Setting the TMP, TMPDIR, or TEMP env vars should do the same thing,
  # but on some systems it may be necessary to use this instead.
  temp-dir: /my/tmp/dir

  # Overrides the 'platforms' configuration (a.k.a. multi-platform builds)
  # in order to build only single-platform image builds regardless of
  # the configuration in the buildrunner.yaml file.
  disable-multi-platform: true/false (defaults to false)

  # Optionally uses a registry for temporary multi-platform builds
  # If not specified or set to "local", uses a temporary registry Docker container
  # which only lives for the duration of the build
  build-registry: docker-build.example.com

  # Overrides the buildx builder used when doing multi-platform builds. Buildx
  # does not provide the capability to auto-select the builder based on the platform
  # and therefore this must be configured in buildrunner itself to perform builds
  # across multiple builders for different platforms. Any platform not specified
  # here will use the default configured buildx builder.
  platform-builders:
    platform1: builder1

  # Configures caching *for multi-platform builds only*
  docker-build-cache:
    # An optional list of builders to apply caching options to
    # NOTE: These caching options do not work for the default (docker) buildx driver,
    #       so be careful which builders they are configured for as this could cause
    #       build failures
    builders:
    - builder1
    # See https://docs.docker.com/build/cache/backends/ for information on how to
    # configure the caching backend. These may be strings or dictionaries (both are
    # shown below).
    to: type=local,dest=/mnt/docker-cache
    from:
      type: local
      src: /mnt/docker-cache

  security-scan:
    # Set to "true" to enable automatic security scans of pushed images
    enabled: false
    # Only trivy is currently supported
    scanner: "trivy"
    # The version of the trivy image to pull
    version: "latest"
    # The local cache directory for the scanner (used if supported by the scanner)
    cache-dir: null
    config:
      # Timeout after 20 minutes by default
      timeout: 20m
      # Do not error on vulnerabilities by default
      exit-code: 0
    # Set to a float to fail the build if the maximum score
    # is greater than or equal to this number
    max-score-threshold: null

Configuration Locations
=======================

Buildrunner reads the global configuration from files in the following order:

* ``/etc/buildrunner/buildrunner.yaml``
* ``${HOME}/.buildrunner.yaml``
* ``${PWD}/.buildrunner.yaml``

The configuration is read from each file in order. If a main section
exists in more than one file, the last one read in is used.  Some
entries, such as ``local-files`` will be handled differently when
appearing in the master configuration file
(``/etc/buildrunner/buildrunner.yaml`` vs. other configuration files
that can be manipulated by users).
