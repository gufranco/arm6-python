"""That every exception this package raises is one class, reachable by name.

An exception defined twice under one name is a trap that looks like it works,
and one that cannot be imported can only be handled by catching everything. Both
are cheap to check and expensive to meet in a caller's code, so they are checked
here rather than left to a reader of the source.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import errors  # noqa: E402


class EveryFailureDescendsFromOneRootTest(unittest.TestCase):
    def test_the_root_is_an_exception(self) -> None:
        root = errors.Arm6Error

        descends = issubclass(root, Exception)

        self.assertTrue(descends)

    def test_and_every_other_class_here_descends_from_it(self) -> None:
        named = [
            value
            for value in vars(errors).values()
            if isinstance(value, type)
            and issubclass(value, Exception)
            and value is not errors.Arm6Error
        ]

        stray = [one.__name__ for one in named if not issubclass(one, errors.Arm6Error)]

        self.assertEqual(stray, [])

    def test_there_are_classes_to_check(self) -> None:
        named = [
            value
            for value in vars(errors).values()
            if isinstance(value, type) and issubclass(value, Exception)
        ]

        self.assertGreater(len(named), 1)


class NothingHereReachesBackIntoThePackageTest(unittest.TestCase):
    def test_the_module_imports_nothing_from_its_own_package(self) -> None:
        source = (ROOT / "arm6" / "errors.py").read_text()

        reaching = [
            line
            for line in source.splitlines()
            if line.startswith(("from arm6", "import arm6", "from ."))
        ]

        self.assertEqual(reaching, [])


class EveryClassSaysWhatItHoldsTest(unittest.TestCase):
    def test_no_class_here_kept_a_dictionary(self) -> None:
        named = [
            value
            for value in vars(errors).values()
            if isinstance(value, type) and issubclass(value, Exception)
        ]

        unslotted = [one.__name__ for one in named if "__slots__" not in vars(one)]

        self.assertEqual(unslotted, [])


class RaisedAndCaughtByNameTest(unittest.TestCase):
    def test_an_unknown_model_is_caught_as_the_root(self) -> None:
        with self.assertRaises(errors.Arm6Error):
            raise errors.UnknownModelError("nothing goes by that name")

    def test_a_run_limit_is_its_own_class(self) -> None:
        with self.assertRaises(errors.RunLimit):
            raise errors.RunLimit("gave up")

    def test_a_closed_clock_is_its_own_class(self) -> None:
        with self.assertRaises(errors.ClockClosed):
            raise errors.ClockClosed("shut down")

    def test_a_missing_wait_figure_is_its_own_class(self) -> None:
        with self.assertRaises(errors.WaitsRequired):
            raise errors.WaitsRequired("the board has not said")

    def test_an_impossible_wait_figure_is_its_own_class(self) -> None:
        with self.assertRaises(errors.BadWaits):
            raise errors.BadWaits("below one mclk")


if __name__ == "__main__":
    unittest.main(verbosity=2)
