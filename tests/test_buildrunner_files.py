import os
import sys
import unittest

import tests.test_runner as tr


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

        br_files = sorted([f for f in os.listdir(test_dir) if f.startswith('test-') and f.endswith('.yaml')])
        for br_file in br_files:
            print(f'\n>>>> Testing Buildrunner file: {br_file}')
            args = self._get_test_args(br_file)
            command_line = [
                'buildrunner-test',
                '-d', top_dir_path,
                '-f', os.path.join(test_dir, br_file),
                '--push',
            ]
            if args:
                command_line.extend(args)

            if br_file.startswith('test-xfail'):
                assert_func = self.assertNotEqual
            else:
                assert_func = self.assertEqual

            assert_func(
                tr.run_tests(
                    command_line,
                    master_config_file = f'{test_dir_path}/test-data/etc-buildrunner.yaml',
                    global_config_files = [
                        f'{test_dir_path}/test-data/etc-buildrunner.yaml',
                        f'{test_dir_path}/test-data/dot-buildrunner.yaml',
                    ]
                ),
                os.EX_OK,
            )


if __name__ == '__main__':
    unittest.main(argv=sys.argv)
