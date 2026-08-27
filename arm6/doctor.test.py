"""That the doctor reports what is here rather than what ought to be.

A skip and a pass print the same thing, which is the whole reason this exists. A
reader who fetched no documents gets a green test run and reads it as
confirmation, when what it confirms is that the checks ran over what was there,
which was nothing.

So every check below is driven against something broken as well as against
something whole, because the branch that reports a fault runs only when there is
one and is therefore the branch least likely to have run.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import doctor  # noqa: E402


class OneFindingTest(unittest.TestCase):
    def test_a_finding_that_passed_reads_as_passing(self) -> None:
        held = doctor.Finding("thing", True, "all present").line

        self.assertIn("ok", held)

    def test_a_finding_that_did_not_says_so(self) -> None:
        held = doctor.Finding("thing", False, "absent").line

        self.assertIn("!", held)

    def test_a_failing_finding_carries_its_advice(self) -> None:
        held = doctor.Finding("thing", False, "absent", "fetch it").report

        self.assertIn("fetch it", held)

    def test_a_passing_one_does_not_repeat_advice_nobody_needs(self) -> None:
        held = doctor.Finding("thing", True, "present", "fetch it").report

        self.assertNotIn("fetch it", held)

    def test_a_failing_finding_with_nothing_to_advise_still_reports(self) -> None:
        held = doctor.Finding("thing", False, "absent").report

        self.assertIn("absent", held)

    def test_a_finding_says_what_it_is_when_printed(self) -> None:
        held = repr(doctor.Finding("thing", True, "present"))

        self.assertIn("thing", held)


class TheVersionIsReadRatherThanImportedTest(unittest.TestCase):
    def test_it_is_found_in_the_file_beside_the_doctor(self) -> None:
        held = doctor._version()

        self.assertRegex(held, r"^\d+\.\d+\.\d+")

    def test_a_file_with_no_version_in_it_is_reported_rather_than_crashed_on(self) -> None:
        empty = Path(__file__).resolve().parent / "decode.py"

        held = doctor._version(empty)

        self.assertEqual(held, "unknown")


class WhatIsActuallyOnThisMachineTest(unittest.TestCase):
    def test_the_python_it_is_running_on_is_reported(self) -> None:
        held = doctor._python()

        self.assertEqual(held.name, "python")

    def test_the_package_names_itself_and_its_version(self) -> None:
        held = doctor._package()

        self.assertIn("arm6", held.detail)

    def test_a_part_that_builds_and_runs_is_reported_as_working(self) -> None:
        held = doctor._processor("arm60")

        self.assertTrue(held.ok)

    def test_and_the_report_says_what_it_actually_drove(self) -> None:
        held = doctor._processor("arm60")

        self.assertIn("cycles", held.detail)

    def test_and_it_says_where_the_reset_left_the_counter(self) -> None:
        held = doctor._processor("arm60")

        self.assertIn("reset to 0x00000000", held.detail)

    def test_a_part_that_builds_and_will_not_reset_is_reported_as_broken(self) -> None:
        class WillNotReset:
            def reset(self) -> None:
                raise RuntimeError("no")

        held = doctor._processor("arm60", build=lambda name: WillNotReset())

        self.assertFalse(held.ok)

    def test_a_part_that_will_not_build_is_reported_with_what_stopped_it(self) -> None:
        def refuse(name: str) -> object:
            raise RuntimeError("no")

        held = doctor._processor("arm60", build=refuse)

        self.assertFalse(held.ok)

    def test_and_the_failure_is_named_by_type(self) -> None:
        def refuse(name: str) -> object:
            raise RuntimeError("no")

        held = doctor._processor("arm60", build=refuse)

        self.assertIn("RuntimeError", held.detail)


class TheDocumentsThisRepositoryCannotCarryTest(unittest.TestCase):
    def test_a_directory_that_is_not_there_is_not_the_same_as_an_empty_one(self) -> None:
        absent = doctor._documents(Path("/nowhere/at/all"))
        empty = doctor._documents(Path(__file__).resolve().parent)

        self.assertNotEqual(absent.detail, empty.detail)

    def test_an_absent_directory_is_reported_as_absent_rather_than_broken(self) -> None:
        held = doctor._documents(Path("/nowhere/at/all"))

        self.assertIn("not there", held.detail)

    def test_a_directory_holding_nothing_says_it_holds_nothing(self) -> None:
        held = doctor._documents(Path(__file__).resolve().parent / "version.py")

        self.assertIn("not there", held.detail)

    def test_a_directory_with_documents_in_it_counts_and_names_them(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            (Path(where) / "a-datasheet.pdf").write_bytes(b"x")

            held = doctor._documents(Path(where))

            self.assertIn("1 in", held.detail)

    def test_and_names_what_it_found(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            (Path(where) / "a-datasheet.pdf").write_bytes(b"x")

            held = doctor._documents(Path(where))

            self.assertIn("a-datasheet.pdf", held.detail)

    def test_a_directory_that_is_there_and_holds_nothing_says_none(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            held = doctor._documents(Path(where))

            self.assertIn("none", held.detail)


class TheRecogniserThisMembersDocumentNeedsTest(unittest.TestCase):
    def test_a_machine_with_both_tools_is_reported_as_able_to_check_quotes(self) -> None:
        held = doctor._recogniser(lambda name: "/usr/bin/" + name)

        self.assertTrue(held.ok)

    def test_a_machine_with_neither_says_which_is_missing(self) -> None:
        held = doctor._recogniser(lambda name: None)

        self.assertIn("tesseract", held.detail)

    def test_and_is_not_reported_as_working(self) -> None:
        held = doctor._recogniser(lambda name: None)

        self.assertFalse(held.ok)

    def test_a_machine_with_only_one_of_them_still_fails(self) -> None:
        held = doctor._recogniser(lambda name: None if name == "tesseract" else "/usr/bin/x")

        self.assertFalse(held.ok)


class TheReportAsAWholeTest(unittest.TestCase):
    def test_it_looks_at_more_than_one_thing(self) -> None:
        held = doctor.examine()

        self.assertGreater(len(held), 3)

    def test_a_clean_run_says_how_many_checks_it_made(self) -> None:
        held = doctor.report([doctor.Finding("a", True, "fine")])

        self.assertIn("1 checks", "\n".join(held))

    def test_a_run_with_a_fault_counts_the_faults(self) -> None:
        held = doctor.report([doctor.Finding("a", True, "fine"), doctor.Finding("b", False, "not")])

        self.assertIn("1 of 2", "\n".join(held))

    def test_the_report_opens_with_something_a_reader_can_paste(self) -> None:
        held = doctor.report([doctor.Finding("a", True, "fine")])

        self.assertIn("arm6", held[0])

    def test_a_clean_run_exits_zero(self) -> None:
        held = doctor.main(examine=lambda: [doctor.Finding("a", True, "fine")], say=lambda _: None)

        self.assertEqual(held, 0)

    def test_a_run_with_a_fault_exits_non_zero(self) -> None:
        held = doctor.main(examine=lambda: [doctor.Finding("a", False, "no")], say=lambda _: None)

        self.assertEqual(held, 1)

    def test_the_report_is_printed_rather_than_kept(self) -> None:
        said: list[str] = []

        doctor.main(examine=lambda: [doctor.Finding("a", True, "fine")], say=said.append)

        self.assertGreater(len(said), 1)


class TheDoctorRunsWhereThePackageMightNotImportTest(unittest.TestCase):
    def test_it_puts_the_repository_on_the_path_when_nothing_else_has(self) -> None:
        kept = list(sys.path)
        try:
            sys.path[:] = [one for one in sys.path if one != str(ROOT)]

            held = doctor._default_build("arm60")

            self.assertEqual(held.model.name, "arm60")
        finally:
            sys.path[:] = kept


if __name__ == "__main__":
    unittest.main(verbosity=2)
