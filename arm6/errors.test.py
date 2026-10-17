from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arm6  # noqa: E402

EVERY_ERROR = [
    getattr(arm6, name)
    for name in arm6.__all__
    if isinstance(getattr(arm6, name), type) and issubclass(getattr(arm6, name), Exception)
]


class EveryFailureDescendsFromOneRootTest(unittest.TestCase):
    def test_the_root_is_an_exception(self) -> None:
        # Arrange
        root = arm6.Arm6Error

        # Act
        descends = issubclass(root, Exception)

        # Assert
        self.assertTrue(descends)

    def test_and_every_other_error_the_package_exports_descends_from_it(self) -> None:
        # Arrange
        named = [one for one in EVERY_ERROR if one is not arm6.Arm6Error]

        # Act
        stray = [one.__name__ for one in named if not issubclass(one, arm6.Arm6Error)]

        # Assert
        self.assertEqual(stray, [])

    def test_there_are_classes_to_check(self) -> None:
        # Arrange
        named = EVERY_ERROR

        # Act
        held = sorted(one.__name__ for one in named)

        # Assert
        self.assertEqual(
            held,
            [
                "Arm6Error",
                "BadWaits",
                "ClockClosed",
                "EmptyRegisterList",
                "NoCoprocessor",
                "RunLimit",
                "Truncated",
                "UnknownMode",
                "UnknownModelError",
                "UnspecifiedEncoding",
                "WaitsRequired",
            ],
        )


class NothingHereReachesBackIntoThePackageTest(unittest.TestCase):
    def test_the_module_imports_nothing_from_its_own_package(self) -> None:
        # Arrange
        source = (ROOT / "arm6" / "errors.py").read_text()

        # Act
        reaching = [
            line
            for line in source.splitlines()
            if line.startswith(("from arm6", "import arm6", "from ."))
        ]

        # Assert
        self.assertEqual(reaching, [])


class EveryClassSaysWhatItHoldsTest(unittest.TestCase):
    def test_no_error_the_package_exports_kept_a_dictionary(self) -> None:
        # Arrange
        named = EVERY_ERROR

        # Act
        unslotted = [one.__name__ for one in named if "__slots__" not in vars(one)]

        # Assert
        self.assertEqual(unslotted, [])


class RaisedAndCaughtByNameTest(unittest.TestCase):
    def test_an_unknown_model_is_caught_as_the_root(self) -> None:
        # Arrange
        name = "nothing goes by this"

        # Act
        with self.assertRaises(arm6.Arm6Error) as caught:
            arm6.Cpu(name)

        # Assert
        self.assertIsInstance(caught.exception, arm6.UnknownModelError)

    def test_a_run_limit_is_its_own_class(self) -> None:
        # Arrange
        part = arm6.Cpu("arm60", fill=0).reset()

        # Act
        with self.assertRaises(arm6.Arm6Error) as caught:
            part.run_until(lambda _: False, limit=1)

        # Assert
        self.assertIsInstance(caught.exception, arm6.RunLimit)

    def test_a_closed_clock_is_its_own_class(self) -> None:
        # Arrange
        clock = arm6.Clock(arm6.Cpu("arm60", fill=0).reset())
        clock.close()

        # Act
        with self.assertRaises(arm6.Arm6Error) as caught:
            clock.tick()

        # Assert
        self.assertIsInstance(caught.exception, arm6.ClockClosed)

    def test_a_missing_wait_figure_is_its_own_class(self) -> None:
        # Arrange
        tally = arm6.Cycles(s=1)

        # Act
        with self.assertRaises(arm6.Arm6Error) as caught:
            tally.ticks(None)

        # Assert
        self.assertIsInstance(caught.exception, arm6.WaitsRequired)

    def test_an_impossible_wait_figure_is_its_own_class(self) -> None:
        # Arrange
        figure = 0

        # Act
        with self.assertRaises(arm6.Arm6Error) as caught:
            arm6.Waits(sequential=figure, nonsequential=1, internal=1, coprocessor=1)

        # Assert
        self.assertIsInstance(caught.exception, arm6.BadWaits)

    def test_a_truncation_says_where_the_listing_ran_out(self) -> None:
        # Arrange
        offset = 8

        # Act
        held = arm6.Truncated(offset)

        # Assert
        self.assertEqual((held.offset, str(held)), (8, "no whole instruction at offset 8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
