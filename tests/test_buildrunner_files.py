from __future__ import print_function

import os
import shutil
import tempfile
import unittest

import test_runner as tr

class Test_buildrunner_files(unittest.TestCase):

    def _get_test_args(self, br_file):
        if br_file == 'test-timeout.yaml':
            # Set a short timeout here for the timeout test
            return ['-t', '15']
        # No additional args for this test file
        return None

    def test_buildrunner_files(self):

        test_dir_path = os.path.realpath(os.path.dirname(__file__))
        test_dir = os.path.basename(os.path.dirname(__file__))
        top_dir_path = os.path.realpath(os.path.dirname(test_dir_path))

        br_files = sorted([f for f in os.listdir(test_dir) if f.endswith('.yaml')])
        for br_file in br_files:
            print('\n>>>> Testing Buildrunner file: {0}'.format(br_file))
            args = self._get_test_args(br_file)
            command_line = [
                'buildrunner-test',
                '-d', top_dir_path,
                '-f', os.path.join(test_dir, br_file),
                '--push',
            ]
            if args:
                command_line.extend(args)
            self.assertEqual(
                tr.run_tests(
                    command_line,
                    master_config_file = '{0}/test-data/etc-buildrunner.yaml'.format(test_dir_path),
                    global_config_files = [
                        '{0}/test-data/etc-buildrunner.yaml'.format(test_dir_path),
                        '{0}/test-data/dot-buildrunner.yaml'.format(test_dir_path),
                    ]
                ),
                os.EX_OK,
            )


if __name__ == '__main__':
    unittest.main()
