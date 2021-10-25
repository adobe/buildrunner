import os
import pytest
import sys
from typing import List, Optional, Tuple

from tests import test_runner


TEST_DIR_PATH = os.path.realpath(os.path.dirname(__file__))
TEST_DIR = os.path.basename(os.path.dirname(__file__))
TOP_DIR_PATH = os.path.realpath(os.path.dirname(TEST_DIR_PATH))


def _get_test_args(file_name: str) -> Optional[List[str]]:
    if file_name == 'test-timeout.yaml':
        # Set a short timeout here for the timeout test
        return ['-t', '15']

    if file_name == 'test-platform-override-amd.yaml':
        # Override platform to arm
        return ['--platform', 'linux/arm64/v8']

    if file_name == 'test-platform-override-arm.yaml':
        # Override platform to amd
        return ['--platform', 'linux/amd64']

    # No additional args for this test file
    return None


def _get_exit_code(file_name: str) -> int:
    if file_name.startswith('test-xfail'):
        return os.EX_CONFIG
    return os.EX_OK


def _get_test_runs(test_dir_path: str, test_dir: str, top_dir: str) -> List[Tuple[str, str, str, str, Optional[List[str]], int]]:
    file_names = sorted([
        file_name for file_name in os.listdir(test_dir)
        if file_name.startswith('test-') and file_name.endswith('.yaml')
    ])
    return [(test_dir_path, test_dir, top_dir, file_name, _get_test_args(file_name), _get_exit_code(file_name)) for file_name in file_names]


def _test_buildrunner_file(test_dir_path, test_dir, top_dir_path, file_name, args, exit_code):
    print(f'\n>>>> Testing Buildrunner file: {file_name}')
    command_line = [
        'buildrunner-test',
        '-d', top_dir_path,
        '-f', os.path.join(test_dir, file_name),
        # Do not push in tests
    ]
    if args:
        command_line.extend(args)

    assert exit_code == \
        test_runner.run_tests(
            command_line,
            master_config_file = f'{test_dir_path}/test-data/etc-buildrunner.yaml',
            global_config_files = [
                f'{test_dir_path}/test-data/etc-buildrunner.yaml',
                f'{test_dir_path}/test-data/dot-buildrunner.yaml',
            ]
        )

@pytest.mark.parametrize('test_dir_path, test_dir, top_dir_path, file_name, args, exit_code',
                         _get_test_runs(TEST_DIR_PATH, TEST_DIR, TOP_DIR_PATH))
def test_buildrunner_dir(test_dir_path: str, test_dir: str, top_dir_path: str, file_name, args, exit_code):
    _test_buildrunner_file(test_dir_path, test_dir, top_dir_path, file_name, args, exit_code)

