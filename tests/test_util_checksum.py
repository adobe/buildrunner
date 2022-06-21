import os
from buildrunner import checksum

test_dir_path = os.path.realpath(os.path.dirname(__file__))


def test_checksum():
    files = [
        f"{test_dir_path}/test-files/checksum/test1.txt",
        f"{test_dir_path}/test-files/checksum/test2.txt",
    ]

    with open(f"{test_dir_path}/test-files/checksum/test1.test2.sha1") as checksum_file:
        expected_checksum = checksum_file.read().strip()

        checksum_value = checksum(files)
        assert expected_checksum == checksum_value

        files.reverse()
        checksum_value = checksum(files)
        assert expected_checksum == checksum_value
