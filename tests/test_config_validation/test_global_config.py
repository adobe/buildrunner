import os
import pytest

from buildrunner.config import loader


@pytest.fixture(name="override_master_config_file")
def fixture_override_master_config_file(tmp_path):
    original = loader.MASTER_GLOBAL_CONFIG_FILE
    file_path = tmp_path / "file1"
    loader.MASTER_GLOBAL_CONFIG_FILE = str(file_path)
    yield file_path
    loader.MASTER_GLOBAL_CONFIG_FILE = original


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
        (
            """
          disable-multi-platform: True
          """,
            [],
        ),
        (
            """
          disable-multi-platform: False
          """,
            [],
        ),
        (
            """
          disable-multi-platform: bogus
          """,
            [
                "disable-multi-platform:  Input should be a valid boolean, unable to interpret input (bool_parsing)"
            ],
        ),
    ],
)
def test_config_data(
    config_yaml, error_matches, assert_generate_and_validate_global_config_errors
):
    assert_generate_and_validate_global_config_errors(config_yaml, error_matches)


def test_local_files_merged(override_master_config_file, tmp_path):
    file_path1 = __file__
    file_path2 = os.path.dirname(__file__)
    file_path3 = os.path.dirname(file_path2)
    override_master_config_file.write_text(
        f"""
    local-files:
      key1: {file_path1}
      key2: |
        The contents of the file...
      key3: {file_path2}
    """
    )
    file2 = tmp_path / "file2"
    file2.write_text(
        f"""
    local-files:
      key3: {file_path1}
      key4: {file_path3}
    """
    )
    config = loader.load_global_config_files(
        build_time=123,
        global_config_files=[str(override_master_config_file), str(file2)],
        global_config_overrides={},
    )
    assert "local-files" in config
    assert config.get("local-files") == {
        "key1": file_path1,
        "key2": "The contents of the file...\n",
        "key3": file_path1,
        "key4": file_path3,
    }


def test_overrides(override_master_config_file, tmp_path):
    override_master_config_file.write_text(
        """
    security-scan:
      scanner: scan1
      config:
        k1: v1
        k2: v2.1
    """
    )
    file2 = tmp_path / "file2"
    file2.write_text(
        """
    security-scan:
      config:
        k2: v2.2
        k3: v3.1
    """
    )
    config = loader.load_global_config_files(
        build_time=123,
        global_config_files=[str(override_master_config_file), str(file2)],
        global_config_overrides={
            "security-scan": {"version": "1.2.3", "config": {"k3": "v3.2", "k4": "v4"}}
        },
    )
    assert "security-scan" in config
    assert config.get("security-scan") == {
        "scanner": "scan1",
        "version": "1.2.3",
        "config": {
            "k1": "v1",
            "k2": "v2.2",
            "k3": "v3.2",
            "k4": "v4",
        },
    }
