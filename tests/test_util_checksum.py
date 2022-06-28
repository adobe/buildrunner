import os
from buildrunner import checksum

test_dir_path = os.path.realpath(os.path.dirname(__file__))


def test_checksum():
    with open(f"{test_dir_path}/test-files/checksum/test1.test2.sha1") as checksum_file:
        expected_checksum = checksum_file.read().strip()

        checksum_value = checksum(
            f"{test_dir_path}/test-files/checksum/test1.txt",
            f"{test_dir_path}/test-files/checksum/test2.txt",
        )
        assert expected_checksum == checksum_value

        checksum_value = checksum(
            f"{test_dir_path}/test-files/checksum/test2.txt",
            f"{test_dir_path}/test-files/checksum/test1.txt",
        )
        assert expected_checksum == checksum_value
