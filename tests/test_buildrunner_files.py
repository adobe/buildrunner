import os
import pytest
import sys
from typing import List, Optional, Tuple

from tests import test_runner


test_dir_path = os.path.realpath(os.path.dirname(__file__))
test_dir = os.path.basename(os.path.dirname(__file__))
top_dir_path = os.path.realpath(os.path.dirname(test_dir_path))


def _get_test_args(file_name: str) -> Optional[List[str]]:
    if file_name == 'test-timeout.yaml':
        # Set a short timeout here for the timeout test
        return ['-t', '15']

    # No additional args for this test file
    return None


def _get_exit_code(file_name: str) -> int:
    if file_name.startswith('test-xfail'):
        return os.EX_CONFIG
    return os.EX_OK


def _get_test_runs() -> List[Tuple[str, Optional[List[str]], int]]:
    file_names = sorted([
        file_name for file_name in os.listdir(test_dir)
        if file_name.startswith('test-') and file_name.endswith('.yaml')
    ])
    return [(file_name, _get_test_args(file_name), _get_exit_code(file_name)) for file_name in file_names]


@pytest.mark.parametrize('file_name, args, exit_code', _get_test_runs())
def test_buildrunner_file(file_name, args, exit_code):
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

