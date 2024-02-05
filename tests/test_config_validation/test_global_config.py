import pytest


@pytest.mark.parametrize(
    "config_yaml, error_matches",
    [
        (
            """
    env:
      ENV_VAR1: 'value1'
      ENV_VAR2: 'true'
    build-servers:
      user@host:
        - alias1
        - alias2
    ssh-keys:
      key: |
        -----INLINE KEY-----
        ...
      password: <password if needed>
      prompt-password: True
      aliases:
        - 'my-github-key'
    local-files:
      digitalmarketing.mvn.settings: '~/.m2/settings.xml'
      some.other.file.alias: |
        The contents of the file...
    caches-root: ~/.buildrunner/caches
    docker-registry: docker-mirror.example.com
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
            ["Extra inputs are not permitted"],
        ),
        # Valid github config
        (
            """
        github:
          company_github:
            endpoint: 'https://git.company.com/api'
            version: 'v3'
            username: 'USERNAME'
            app_token: 'APP_TOKEN'
        """,
            [],
        ),
        # Invalid github config
        (
            """
        github:
          company_github:
            endpoint: 'https://git.company.com/api'
            version: 'v3'
            username: 'USERNAME'
            app_token: 'APP_TOKEN'
            bogus: 'bogus'
        """,
            ["Extra inputs are not permitted"],
        ),
    ],
)
def test_config_data(
    config_yaml, error_matches, assert_generate_and_validate_global_config_errors
):
    assert_generate_and_validate_global_config_errors(config_yaml, error_matches)
