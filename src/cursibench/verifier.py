"""Exact state validation for legacy fixtures, not a GUI benchmark evaluator."""
from copy import deepcopy
from .model import Task


def verify(task: Task, state: dict) -> tuple[float, list[str]]:
    if not isinstance(state, dict):
        return 0.0, ['invalid state']
    errors = []
    def compare(expected, actual, path):
        if type(expected) is not type(actual):
            errors.append(path + ': type mismatch')
        elif isinstance(expected, dict):
            if expected.keys() != actual.keys():
                errors.append(path + ': unexpected or missing fields')
            for key in expected.keys() & actual.keys():
                compare(expected[key], actual[key], path + '.' + key)
        elif isinstance(expected, list):
            if len(expected) != len(actual):
                errors.append(path + ': length mismatch')
            for index, (left, right) in enumerate(zip(expected, actual)):
                compare(left, right, path + f'[{index}]')
        elif expected != actual:
            errors.append(path + ': value mismatch')
    compare(task.expected, state, 'state')
    # No partial score can hide an unintended side effect in these small fixtures.
    return (0.0 if errors else 1.0), errors


def expected_state(task: Task) -> dict:
    return deepcopy(task.expected)
