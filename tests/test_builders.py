import os
from unittest import mock
import uuid
import pytest
import tempfile

import yaml

from buildrunner.docker.image_info import BuiltImageInfo, BuiltTaggedImage
from tests import test_runner


test_dir_path = os.path.realpath(os.path.dirname(__file__))
TEST_DIR = os.path.dirname(__file__)
top_dir_path = os.path.realpath(os.path.dirname(test_dir_path))


def _test_buildrunner_file(test_dir, file_name, args, exit_code):
    print(f"\n>>>> Testing Buildrunner file: {file_name}")
    with tempfile.TemporaryDirectory(prefix="buildrunner.results-") as temp_dir:
        command_line = [
            "buildrunner-test",
            "-d",
            top_dir_path,
            "-b",
            temp_dir,
            # Since we are using a fresh temp directory, don't delete it first
            "--keep-step-artifacts",
            "-f",
            os.path.join(test_dir, file_name),
            # Do not push in tests
        ]
        if args:
            command_line.extend(args)

        assert exit_code == test_runner.run_tests(
            command_line,
            master_config_file=f"{test_dir_path}/config-files/etc-buildrunner.yaml",
            global_config_files=[
                f"{test_dir_path}/config-files/etc-buildrunner.yaml",
                f"{test_dir_path}/config-files/dot-buildrunner.yaml",
            ],
        )


@pytest.fixture(autouse=True)
def fixture_set_env():
    # Sets an environment variable that can be used from a buildrunner file
    os.environ["IS_BR_TEST"] = "true"
    # Also sets an environment variable that is available in regular jinja without using the `env` instance
    os.environ["BUILDRUNNER_IS_TEST"] = "true"
    yield
    # Cleanup
    del os.environ["IS_BR_TEST"]
    del os.environ["BUILDRUNNER_IS_TEST"]


@pytest.mark.parametrize(
    "description, use_legacy_builder, config,",
    [
        (
            "Use buildx builder with platform",
            False,
            """
            use-legacy-builder: false
            steps:
                build-container-single-platform:
                    build:
                        path: .
                        dockerfile: |
                            FROM python:3.10
                            CMD python3
                        platform: linux/arm64
            """,
        ),
        (
            "Use buildx builder",
            False,
            """
            use-legacy-builder: false
            steps:
                build-container-single-platform:
                    build:
                        path: .
                        dockerfile: |
                            FROM python:3.10
                            CMD python3
            """,
        ),
        (
            "Overwrite use-legacy-builder with platforms",
            False,
            """
            use-legacy-builder: true
            steps:
                build-container-single-platform:
                    build:
                        path: .
                        dockerfile: |
                            FROM python:3.10
                            CMD python3
                        platforms:
                            - linux/amd64
                            - linux/arm64
            """,
        ),
        (
            "Use buildx builder with platforms",
            False,
            """
            use-legacy-builder: false
            steps:
                build-container-single-platform:
                    build:
                        path: .
                        dockerfile: |
                            FROM python:3.10
                            CMD python3
                        platforms:
                            - linux/amd64
                            - linux/arm64
            """,
        ),
        (
            "Default builder with platforms",
            False,
            """
            steps:
                build-container-single-platform:
                    build:
                        path: .
                        dockerfile: |
                            FROM python:3.10
                            CMD python3
                        platforms:
                            - linux/amd64
                            - linux/arm64
            """,
        ),
        (
            "Default builder",
            True,
            """
            steps:
                build-container-single-platform:
                    build:
                        path: .
                        dockerfile: |
                            FROM python:3.10
                            CMD python3
            """,
        ),
        (
            "Use legacy builder with platform",
            True,
            """
            use-legacy-builder: true
            steps:
                build-container-single-platform:
                    build:
                        path: .
                        dockerfile: |
                            FROM python:3.10
                            CMD python3
                        platform: linux/arm64
            """,
        ),
        (
            "Use legacy builder with use-legacy-builder",
            True,
            """
            use-legacy-builder: true
            steps:
                build-container-single-platform:
                    build:
                        path: .
                        dockerfile: |
                            FROM python:3.10
                            CMD python3
            """,
        ),
    ],
)
@mock.patch(
    "tests.test_runner.buildrunner.steprunner.tasks.build.legacy_builder.build_image"
)
@mock.patch(
    "tests.test_runner.buildrunner.steprunner.MultiplatformImageBuilder.build_multiple_images"
)
def test_builders(
    mock_buildx_builder,
    mock_legacy_build,
    description,
    use_legacy_builder,
    config,
):
    _ = description
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmp_filename = f"{tmpdirname}/config.yaml"
        with open(tmp_filename, "w") as f:
            f.write(config)

        args = None
        exit_code = 0

        #  legacy builder args
        mock_legacy_build.return_value = "52fc1c92b555"

        config = yaml.load(config, Loader=yaml.SafeLoader)

        # default builder args
        if config.get("steps", {}):
            for step_name, step in config.get("steps", {}).items():
                built_image = BuiltImageInfo(id=str(uuid.uuid4()))
                if step.get("build", {}).get("platforms"):
                    for platform in step.get("build", {}).get("platforms", []):
                        built_image.add_platform_image(
                            platform,
                            BuiltTaggedImage(
                                repo=f"repo-{platform}",
                                tag=f"tag-{platform}",
                                digest=f"digest-{platform}",
                                platform="linux/arm64",
                            ),
                        )
                else:
                    if step.get("build", {}).get("platform"):
                        platform = step.get("build", {}).get("platform")
                        built_image.add_platform_image(
                            platform,
                            BuiltTaggedImage(
                                repo=f"repo-{platform}",
                                tag=f"tag-{platform}",
                                digest=f"digest-{platform}",
                                platform=platform,
                            ),
                        )
                    else:
                        platform = "linux/arm64"
                        built_image.add_platform_image(
                            "linux/arm64",
                            BuiltTaggedImage(
                                repo=f"repo-{platform}",
                                tag=f"tag-{platform}",
                                digest=f"digest-{platform}",
                                platform=platform,
                            ),
                        )
                mock_buildx_builder.return_value = built_image

        _test_buildrunner_file(tmpdirname, tmp_filename, args, exit_code)

        if use_legacy_builder:
            mock_buildx_builder.assert_not_called()
            mock_legacy_build.assert_called()
        else:
            mock_buildx_builder.assert_called()
            mock_legacy_build.assert_not_called()
