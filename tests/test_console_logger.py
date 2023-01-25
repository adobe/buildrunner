import tempfile
from buildrunner import ConsoleLogger

def test_open_stream():
    with tempfile.TemporaryDirectory() as temp_dir:
        log_file_path = f"{temp_dir}/temp.txt"
        test_string = "This is is a test."
        with open(log_file_path, 'w') as log_file:
            log = ConsoleLogger(None, log_file)
            assert log is not None
            log.write(test_string)

        with open(log_file_path, 'r') as log_file:
            assert test_string in log_file.readline()


def test_closed_stream():
    with tempfile.TemporaryDirectory() as temp_dir:
        log_file_path = f"{temp_dir}/temp.txt"
        test_string = "This is is a test."
        test_bogus_string = "This should not be in the log file."

        with open(log_file_path, 'w') as log_file:
            log = ConsoleLogger(None, log_file)
            assert log is not None
            log.write(test_string)

        # Tests that no exception has occurred
        log.write(test_bogus_string)

        with open(log_file_path, 'r') as log_file:
            assert test_string in log_file.readline()
            assert test_bogus_string not in log_file.readline()