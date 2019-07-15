from __future__ import print_function

import os
import shutil
import tempfile
import unittest

from buildrunner import cli


class Test_buildrunner_files(unittest.TestCase):


    def test_buildrunner_files(self):
        test_dir_path = os.path.realpath(os.path.dirname(__file__))
        test_dir = os.path.basename(os.path.dirname(__file__))
        top_dir_path = os.path.realpath(os.path.dirname(test_dir_path))

        br_files = sorted([f for f in os.listdir(test_dir) if f.endswith('.yaml')])
        for br_file in br_files:
            print('\n>>>> Testing Buildrunner file: {0}'.format(br_file))
            self.assertEqual(
                cli.main([
                    'buildrunner-test',
                    '-d', top_dir_path,
                    '-f', os.path.join(test_dir, br_file),
                    '--push',
                ]),
                os.EX_OK,
            )


if __name__ == '__main__':
    unittest.main()
