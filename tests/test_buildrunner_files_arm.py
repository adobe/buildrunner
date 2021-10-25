import os
import pytest

from tests.test_buildrunner_files import _get_test_runs, _test_buildrunner_file
import platform

TEST_DIR_PATH = os.path.realpath(os.path.dirname(__file__))
TEST_DIR = f'{os.path.basename(os.path.dirname(__file__))}/arm-arch'
TOP_DIR_PATH = os.path.realpath(os.path.dirname(TEST_DIR_PATH))


@pytest.mark.skipif("arm64" not in platform.uname().machine,
                    reason="This test should only be run on arm64 architecture")
@pytest.mark.parametrize('test_dir_path, test_dir, top_dir_path, file_name, args, exit_code',
                         _get_test_runs(TEST_DIR_PATH, TEST_DIR, TOP_DIR_PATH))
def test_buildrunner_dir(test_dir_path: str, test_dir: str, top_dir_path: str, file_name, args, exit_code):
    _test_buildrunner_file(test_dir_path, test_dir, top_dir_path, file_name, args, exit_code)
