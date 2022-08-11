from collections import OrderedDict
import unittest
import copy
import graphlib

from buildrunner import BuildRunnerConfig


class TestDependencies(unittest.TestCase):
    config = OrderedDict([
        ('steps', OrderedDict([
            ('step1', OrderedDict([
                ('run', OrderedDict([('image', 'docker.io/ubuntu:latest'),
                                     ('cmd', 'echo "Hello from step 1"')]))])),
            ('step2', OrderedDict([
                ('depends', ['step3', 'step4']),
                ('run', OrderedDict([('image', 'docker.io/ubuntu:latest'),
                                     ('cmd', 'echo "Hello from step 2"')]))])),
            ('step3', OrderedDict([
                ('run', OrderedDict([('image', 'docker.io/ubuntu:latest'),
                                     ('cmd', 'echo "Hello from step 3"')]))])),
            ('step4', OrderedDict([
                ('run', OrderedDict([('image', 'docker.io/ubuntu:latest'),
                                     ('cmd', 'echo "Hello from step 4"')]))]))]))])

    KEYWORD_VERSION = 'version'
    KEYWORD_STEPS = 'steps'
    KEYWORD_DEPENDS = 'depends'


    def check_steps_equal(self, steps, expected_step_names):
        for actual_step_name, actual_step in steps[self.KEYWORD_STEPS].items():
            self.assertEqual(next(expected_step_names), actual_step_name)

            expected_step = copy.deepcopy(self.config[self.KEYWORD_STEPS][actual_step_name])
            if self.KEYWORD_DEPENDS in expected_step:
                del expected_step[self.KEYWORD_DEPENDS]
            self.assertDictEqual(expected_step, actual_step)


    def test_reorder_steps(self):
        config = copy.deepcopy(self.config)
        config[self.KEYWORD_VERSION] = 2.0
        expected_step_names = iter(['step1', 'step3', 'step4', 'step2'])

        reordered_steps = BuildRunnerConfig._reorder_dependency_steps(config)

        self.check_steps_equal(reordered_steps, expected_step_names)


    def test_reorder_steps_higher_version(self):
        config = copy.deepcopy(self.config)
        config[self.KEYWORD_VERSION] = 2.1
        expected_step_names = iter(['step1', 'step3', 'step4', 'step2'])

        reordered_steps = BuildRunnerConfig._reorder_dependency_steps(config)

        self.check_steps_equal(reordered_steps, expected_step_names)

        config = copy.deepcopy(self.config)
        config[self.KEYWORD_VERSION] = 3.1
        expected_step_names = iter(['step1', 'step3', 'step4', 'step2'])

        reordered_steps = BuildRunnerConfig._reorder_dependency_steps(config)

        self.check_steps_equal(reordered_steps, expected_step_names)


    def test_no_reorder(self):
        config = copy.deepcopy(self.config)
        config[self.KEYWORD_VERSION] = 2.0

        # Remove any steps with 'depends' attribute
        for name, step in config[self.KEYWORD_STEPS].items():
            if self.KEYWORD_DEPENDS in step:
                del step[self.KEYWORD_DEPENDS]

        reordered_steps = BuildRunnerConfig._reorder_dependency_steps(config)

        self.assertDictEqual(config, reordered_steps)


    def test_not_supported_version(self):
        config = copy.deepcopy(self.config)
        config[self.KEYWORD_VERSION] = 1.9

        reordered_steps = BuildRunnerConfig._reorder_dependency_steps(config)

        del reordered_steps[self.KEYWORD_VERSION]
        self.assertDictEqual(self.config, reordered_steps)


    def test_missing_version(self):
        config = copy.deepcopy(self.config)

        reordered_steps = BuildRunnerConfig._reorder_dependency_steps(config)

        self.assertDictEqual(self.config, reordered_steps)


    def test_cycle_dependency(self):
        config = copy.deepcopy(self.config)
        config[self.KEYWORD_VERSION] = 2.0
        config[self.KEYWORD_STEPS]['step4'][self.KEYWORD_DEPENDS] = ['step3', 'step2']

        self.assertRaises(graphlib.CycleError, BuildRunnerConfig._reorder_dependency_steps, config)


    def test_not_defined_dependency(self):
        config = copy.deepcopy(self.config)
        config[self.KEYWORD_VERSION] = 2.0
        config[self.KEYWORD_STEPS]['step4'][self.KEYWORD_DEPENDS] = ['step1-typo']

        self.assertRaises(KeyError, BuildRunnerConfig._reorder_dependency_steps, config)
