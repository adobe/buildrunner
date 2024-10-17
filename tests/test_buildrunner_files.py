import os
import pytest
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from tests import test_runner

# This should match what is in the dot-buildrunner.yaml file
TEST_SSH_KEY_FILE = "/tmp/buildrunner-test-id_rsa"

test_dir_path = os.path.realpath(os.path.dirname(__file__))
TEST_DIR = os.path.dirname(__file__)
top_dir_path = os.path.realpath(os.path.dirname(test_dir_path))

serial_test_files = [
    "test-general-buildx.yaml",
    "test-general.yaml",
    "test-push-artifact-buildx.yaml",
    "test-security-scan.yaml",
]


@pytest.fixture(autouse=True, scope="session")
def setup_buildrunner_test_ssh_key():
    key_file_path = Path(TEST_SSH_KEY_FILE)
    key_file_path.unlink(missing_ok=True)
    subprocess.run(
        [
            "ssh-keygen",
            "-t",
            "ecdsa",
            "-m",
            "PEM",
            "-N",
            "",
            "-f",
            TEST_SSH_KEY_FILE,
        ],
        check=True,
    )
    # Set the public key in an environment variable to use in the test buildrunner files
    os.environ["BUILDRUNNER_TEST_SSH_PUB_KEY"] = (
        Path(f"{TEST_SSH_KEY_FILE}.pub").read_text().strip()
    )
    yield
    # Cleanup
    del os.environ["BUILDRUNNER_TEST_SSH_PUB_KEY"]
    key_file_path.unlink()


def _get_test_args(file_name: str) -> Optional[List[str]]:
    if file_name == "test-timeout.yaml":
        # Set a short timeout here for the timeout test
        return ["-t", "15"]

    if file_name == "test-platform-override-amd.yaml":
        # Override platform to arm
        return ["--platform", "linux/arm64/v8"]

    if file_name == "test-platform-override-arm.yaml":
        # Override platform to amd
        return ["--platform", "linux/amd64"]

    if file_name == "test-local-images-and-platform.yaml":
        # Override platform to amd and use local images
        return ["--local-images", "--platform", "linux/amd64"]

    if file_name == "test-security-scan.yaml":
        # Override to enable security scanning
        return ["--security-scan-enabled", "true"]

    # No additional args for this test file
    return None


def _get_exit_code(file_name: str) -> int:
    if file_name.startswith("test-xfail-security-scan"):
        return 1

    if file_name.startswith("test-xfail"):
        return os.EX_CONFIG

    if file_name.startswith("test-inject-nonexistent-dir"):
        return os.EX_CONFIG

    if file_name.startswith("test-docker-pull-failure"):
        return os.EX_CONFIG

    return os.EX_OK


def _get_test_runs(
    test_dir: str, serial_tests: bool
) -> List[Tuple[str, str, Optional[List[str]], int]]:
    file_names = []
    for file_name in os.listdir(test_dir):
        if serial_tests:
            if file_name in serial_test_files:
                file_names.append(file_name)
        else:
            if (
                file_name.startswith("test-")
                and file_name.endswith(".yaml")
                and file_name not in serial_test_files
            ):
                file_names.append(file_name)

    return [
        (test_dir, file_name, _get_test_args(file_name), _get_exit_code(file_name))
        for file_name in file_names
    ]


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
    "test_dir, file_name, args, exit_code",
    _get_test_runs(test_dir=f"{TEST_DIR}/test-files", serial_tests=False),
)
def test_buildrunner_dir(test_dir: str, file_name, args, exit_code):
    _test_buildrunner_file(test_dir, file_name, args, exit_code)


@pytest.mark.serial
@pytest.mark.parametrize(
    "test_dir, file_name, args, exit_code",
    _get_test_runs(test_dir=f"{TEST_DIR}/test-files", serial_tests=True),
)
def test_serial_buildrunner_dir(test_dir: str, file_name, args, exit_code):
    _test_buildrunner_file(test_dir, file_name, args, exit_code)


@pytest.mark.skipif(
    "arm64" not in platform.uname().machine,
    reason="This test should only be run on arm64 architecture",
)
@pytest.mark.parametrize(
    "test_dir, file_name, args, exit_code",
    _get_test_runs(test_dir=f"{TEST_DIR}/test-files/arm-arch", serial_tests=False),
)
def test_buildrunner_arm_dir(test_dir: str, file_name, args, exit_code):
    _test_buildrunner_file(test_dir, file_name, args, exit_code)


@pytest.mark.serial
@pytest.mark.skipif(
    "arm64" not in platform.uname().machine,
    reason="This test should only be run on arm64 architecture",
)
@pytest.mark.parametrize(
    "test_dir, file_name, args, exit_code",
    _get_test_runs(test_dir=f"{TEST_DIR}/test-files/arm-arch", serial_tests=True),
)
def test_serial_buildrunner_arm_dir(test_dir: str, file_name, args, exit_code):
    _test_buildrunner_file(test_dir, file_name, args, exit_code)
