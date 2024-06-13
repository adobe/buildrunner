import pytest


@pytest.mark.parametrize(
    "config_yaml, error_matches",
    [
        (
            """
            steps:
              build-remote:
                remote:
                  host: myserver.ut1
                  cmd: docker build -t mytest-reg/buildrunner-test .
                  artifacts:
                    bogus/path/to/artifacts/*:
                      type: tar
                      compression: lzma
            """,
            [],
        ),
        (
            """
            steps:
              build-run:
                run:
                  artifacts:
                    bogus/path/to/artifacts/*:
                      type: zip
                      compression: lzma
            """,
            [],
        ),
        # Valid compression
        (
            """
            steps:
              build-remote:
                remote:
                  host: myserver.ut1
                  cmd: docker build -t mytest-reg/buildrunner-test .
                  artifacts:
                    bogus/path/to/artifacts/*:
                      type: tar
                      compression: gz
            """,
            [],
        ),
        # Valid run format
        (
            """
            steps:
              build-run:
                run:
                  artifacts:
                    bogus/path/to/artifacts/*:
                      format: uncompressed
            """,
            [],
        ),
        #  Checks zip type
        (
            """
            steps:
              build-run:
                run:
                  artifacts:
                    bogus/path/to/artifacts/*:
                      type: zip
            """,
            [],
        ),
        # Checks tar type
        (
            """
            steps:
              build-run:
                run:
                  artifacts:
                    bogus/path/to/artifacts/*:
                      type: tar
            """,
            [],
        ),
        #  Push must be a boolean
        (
            """
            steps:
              build-run:
                run:
                  artifacts:
                    bogus/path/to/artifacts/*:
                      push: bogus
            """,
            ["Input should be a valid boolean"],
        ),
        # Artifact may be a blank string
        (
            """
            steps:
              build-run:
                run:
                  artifacts:
                    bogus/path/to/artifacts/*: ''
                    bogus/path/to/this_thing: ''
            """,
            [],
        ),
        # Valid push
        (
            """
            steps:
              build-run:
                run:
                  artifacts:
                    bogus/path/to/artifacts/*:
                      push: True
            """,
            [],
        ),
        # Valid extra properties
        (
            """
            steps:
              build-run:
                run:
                  artifacts:
                    bogus/path/to/artifacts/*:
                      push: True
                      something_else: awesome data
                      something_else2: True
                      something_else3: 123
            """,
            [],
        ),
        # Rename
        (
            """
            steps:
              build-run:
                run:
                  artifacts:
                    bogus/path/to/artifacts/my-artifact.txt:
                      rename: my-artifact-renamed.txt
            """,
            [],
        ),
    ],
)
def test_config_data(
    config_yaml, error_matches, assert_generate_and_validate_config_errors
):
    assert_generate_and_validate_config_errors(config_yaml, error_matches)
