import pytest


@pytest.mark.parametrize(
    "config_yaml, error_matches",
    [
        (
            """
    # The 'env' global configuration may be used to set environment variables
    # available to all buildrunner runs that load this config file. Env vars do
    # not need to begin with a prefix to be included in this list (i.e.
    # BUILDRUNNER_ prefix is not needed for variables listed here).
    env:
      ENV_VAR1: 'value1'
      # Values must always be strings
      ENV_VAR2: 'true'

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
    # - file: /path/to/ssh/private/key.pem
    # <or>
      key: |
        -----INLINE KEY-----
        ...
      password: <password if needed>
      # If set, prompt for the ssh key password.  Ignored if password is set.
      prompt-password: True
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

    # The 'caches-root' global configuration specifies the directory to use for
    # build caches. The default directory is ~/.buildrunner/caches.
    caches-root: ~/.buildrunner/caches

    # Change the default docker registry, see the FAQ below for more information
    docker-registry: docker-mirror.example.com

    # Change the temp directory used for *most* files
    # Setting the TMP, TMPDIR, or TEMP env vars should do the same thing,
    # but on some systems it may be necessary to use this instead.
    temp-dir: /my/tmp/dir
        """,
            [],
        ),
        (
            """
    ssh-keys:
      - file: /path/to/ssh/private/key.pem
        """,
            [],
        ),
        (
            """
    ssh-keys:
      key: |
        -----INLINE KEY-----
        ...
      password: <password if needed>
      # If set, prompt for the ssh key password.  Ignored if password is set.
      prompt-password: True
      aliases:
        - 'my-github-key'
      bogus-attribute: 'bogus'
        """,
            ["Extra inputs are not permitted", "Input should be a valid list"],
        ),
    ],
)
def test_config_data(
    config_yaml, error_matches, assert_generate_and_validate_config_errors
):
    assert_generate_and_validate_config_errors(config_yaml, error_matches)
