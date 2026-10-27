from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import singlestep  # noqa: E402

STATE = 40


def state() -> list[int]:
    held = [0] * STATE
    held[singlestep.CPSR] = 0x000000D3
    return held


def case(opcode: int, base: int = 0x1000, **named: int) -> singlestep.Case:
    initial = state()
    initial[15] = base + 8
    for name, value in named.items():
        initial[int(name[1:])] = value
    return singlestep.Case(
        initial=tuple(initial),
        final=tuple(initial),
        reads=(),
        opcode=opcode,
        base=base,
    )


class ReadingTheBinaryFormatTest(unittest.TestCase):
    def built(self, opcode: int, transactions: list[tuple[int, ...]]) -> bytes:
        initial = [0] * STATE
        initial[15] = 0x1008
        initial[singlestep.CPSR] = 0x000000D3
        final = list(initial)
        blocks = b""
        for kind, payload in ((1, initial), (2, final)):
            blocks += struct.pack("<II", 8 + len(payload) * 4, kind)
            blocks += struct.pack(f"<{len(payload)}I", *payload)
        flat: list[int] = [len(transactions)]
        for one in transactions:
            flat.extend(one)
        blocks += struct.pack("<II", 8 + len(flat) * 4, 3) + struct.pack(f"<{len(flat)}I", *flat)
        blocks += struct.pack("<II", 16, 4) + struct.pack("<II", opcode, 0x1000)
        record = struct.pack("<I", 4 + len(blocks)) + blocks
        return struct.pack("<II", singlestep.MAGIC, 1) + record

    def test_a_file_yields_the_cases_its_header_claims(self) -> None:
        held = list(singlestep.cases_in(self.built(0xE1A00001, [])))

        self.assertEqual(len(held), 1)

    def test_a_case_carries_the_opcode_and_the_address_it_sits_at(self) -> None:
        held = next(iter(singlestep.cases_in(self.built(0xE1A00001, []))))

        self.assertEqual((held.opcode, held.base), (0xE1A00001, 0x1000))

    def test_a_case_carries_its_initial_and_final_state(self) -> None:
        held = next(iter(singlestep.cases_in(self.built(0xE1A00001, []))))

        self.assertEqual((len(held.initial), len(held.final)), (STATE, STATE))

    def test_a_read_transaction_becomes_a_seeded_word_of_memory(self) -> None:
        held = next(
            iter(singlestep.cases_in(self.built(0xE1A00001, [(1, 4, 0x2000, 0xABCD, 1, 0)])))
        )

        self.assertEqual(held.reads, ((4, 0x2000, 0xABCD),))

    def test_an_instruction_fetch_is_seeded_too(self) -> None:
        held = next(
            iter(singlestep.cases_in(self.built(0xE1A00001, [(0, 4, 0x1008, 0x1234, 1, 2)])))
        )

        self.assertEqual(held.reads, ((4, 0x1008, 0x1234),))

    def test_a_write_transaction_is_not_read_as_memory_the_case_started_with(self) -> None:
        held = next(
            iter(singlestep.cases_in(self.built(0xE1A00001, [(2, 4, 0x2000, 0xABCD, 1, 0)])))
        )

        self.assertEqual(held.reads, ())

    def test_a_file_whose_magic_is_wrong_is_refused_rather_than_misread(self) -> None:
        bad = struct.pack("<II", 0xDEADBEEF, 1) + b"\x00" * 32

        with self.assertRaises(singlestep.NotACorpus):
            list(singlestep.cases_in(bad))


class ReplayingACaseTest(unittest.TestCase):
    def test_a_move_reaches_the_same_state_the_corpus_recorded(self) -> None:
        one = case(0xE1A00001, r1=0x1234)
        final = list(one.initial)
        final[0] = 0x1234
        final[15] = one.initial[15] + 4
        one = one._replace(final=tuple(final))

        held = singlestep.compare(one)

        self.assertEqual(held, [])

    def test_a_state_the_model_does_not_reach_is_reported(self) -> None:
        one = case(0xE1A00001, r1=0x1234)
        final = list(one.initial)
        final[0] = 0xDEAD
        final[15] = one.initial[15] + 4
        one = one._replace(final=tuple(final))

        held = singlestep.compare(one)

        self.assertNotEqual(held, [])

    def test_and_the_report_names_the_register_that_differed(self) -> None:
        one = case(0xE1A00001, r1=0x1234)
        final = list(one.initial)
        final[0] = 0xDEAD
        final[15] = one.initial[15] + 4
        one = one._replace(final=tuple(final))

        held = singlestep.compare(one)

        self.assertIn("R0", held[0])

    def test_the_counter_is_compared_against_the_corpus_prefetch_offset(self) -> None:
        one = case(0xEA000000)
        final = list(one.initial)
        final[15] = one.initial[15] + 8
        one = one._replace(final=tuple(final))

        held = singlestep.compare(one)

        self.assertEqual(held, [])

    def test_a_case_whose_memory_the_corpus_recorded_is_seeded_from_it(self) -> None:
        one = case(0xE5910000, r1=0x2000)
        one = one._replace(reads=((4, 0x2000, 0xCAFEBABE),))
        final = list(one.initial)
        final[0] = 0xCAFEBABE
        final[15] = one.initial[15] + 4
        one = one._replace(final=tuple(final))

        held = singlestep.compare(one)

        self.assertEqual(held, [])

    def test_a_case_the_model_refuses_outright_is_reported_rather_than_crashing(self) -> None:
        one = case(0xE0812394)

        held = singlestep.compare(one)

        self.assertIn("UnspecifiedEncoding", held[0])


class TheReportTest(unittest.TestCase):
    def test_a_run_that_compared_nothing_says_so_rather_than_passing(self) -> None:
        held = singlestep.report(singlestep.Tally())

        self.assertIn("no corpus", "\n".join(held))

    def test_a_run_that_compared_cases_says_how_many(self) -> None:
        tally = singlestep.Tally()
        tally.compared = 100

        held = singlestep.report(tally)

        self.assertIn("100", "\n".join(held))

    def test_a_run_with_a_disagreement_says_how_many_of_those(self) -> None:
        tally = singlestep.Tally()
        tally.compared = 100
        tally.disagreed = 3

        held = singlestep.report(tally)

        self.assertIn("3", "\n".join(held))

    def test_a_run_prints_what_it_left_out_rather_than_dropping_it_quietly(self) -> None:
        tally = singlestep.Tally()
        tally.compared = 10
        tally.excluded["system mode"] = 7

        held = singlestep.report(tally)

        self.assertIn("system mode", "\n".join(held))

    def test_a_clean_run_exits_zero(self) -> None:
        tally = singlestep.Tally()
        tally.compared = 10

        self.assertEqual(singlestep.verdict(tally), 0)

    def test_a_run_with_a_disagreement_exits_one(self) -> None:
        tally = singlestep.Tally()
        tally.compared = 10
        tally.disagreed = 1

        self.assertEqual(singlestep.verdict(tally), 1)

    def test_a_run_that_found_no_corpus_exits_zero(self) -> None:
        self.assertEqual(singlestep.verdict(singlestep.Tally()), 0)


class ThePinTest(unittest.TestCase):
    def test_the_manifest_pins_the_corpus_at_the_commit_the_definition_names(self) -> None:
        # Arrange
        manifest = json.loads((ROOT / "artifacts.manifest.json").read_text())["external"]
        suites = json.loads((ROOT / "conformance" / "suites.json").read_text())["suites"]

        # Act
        pinned = {
            one["repository"]: one["commit"]
            for one in manifest.values()
            if one.get("kind") == "checkout"
        }

        # Assert
        self.assertEqual(pinned, {suite["repository"]: suite["commit"] for suite in suites})

    def test_the_record_names_a_repository(self) -> None:
        held = singlestep.pinned()["suites"][0]

        self.assertIn("github.com", held["repository"])

    def test_and_pins_it_by_commit(self) -> None:
        held = singlestep.pinned()["suites"][0]

        self.assertRegex(held["commit"], r"^[0-9a-f]{40}$")

    def test_and_says_the_repository_is_one_somebody_can_still_push_to(self) -> None:
        held = singlestep.pinned()["suites"][0]

        self.assertFalse(held["archived"])

    def test_the_record_says_what_it_never_reads(self) -> None:
        held = singlestep.pinned()["whatIsRead"]["neverRead"]

        self.assertGreater(len(held), 2)

    def test_the_per_criterion_counts_add_up_to_what_was_removed(self) -> None:
        record = singlestep.pinned()["filter"]

        self.assertEqual(
            sum(one["cases"] for one in record["perCase"]),
            record["counted"]["removed"],
        )

    def test_and_the_usable_count_is_what_is_left(self) -> None:
        held = singlestep.pinned()["filter"]["counted"]

        self.assertEqual(held["casesInTheRemainingFiles"] - held["removed"], held["usable"])

    def test_the_whole_file_counts_add_up_to_what_the_corpus_holds(self) -> None:
        record = singlestep.pinned()

        self.assertEqual(
            sum(one["cases"] for one in record["filter"]["wholeFiles"])
            + record["filter"]["counted"]["casesInTheRemainingFiles"],
            record["suites"][0]["armStateCases"],
        )

    def test_every_criterion_names_the_sentence_behind_it(self) -> None:
        silent = [
            one["criterion"]
            for one in singlestep.pinned()["filter"]["perCase"]
            if len(one.get("why", "")) < 40
        ]

        self.assertEqual(silent, [])


class SweepingADirectoryTest(unittest.TestCase):
    def corpus(self, where: Path, name: str, opcodes: list[int]) -> None:
        records = b""
        for opcode in opcodes:
            initial = [0] * STATE
            initial[15] = 0x1008
            initial[singlestep.CPSR] = 0x000000D3
            final = list(initial)
            final[15] = 0x100C
            blocks = b""
            for kind, payload in ((1, initial), (2, final)):
                blocks += struct.pack("<II", 8 + len(payload) * 4, kind)
                blocks += struct.pack(f"<{len(payload)}I", *payload)
            blocks += struct.pack("<II", 12, 3) + struct.pack("<I", 0)
            blocks += struct.pack("<II", 16, 4) + struct.pack("<II", opcode, 0x1000)
            records += struct.pack("<I", 4 + len(blocks)) + blocks
        header = struct.pack("<II", singlestep.MAGIC, len(opcodes))
        (where / f"{name}.json.bin").write_bytes(header + records)

    def test_a_sweep_compares_the_cases_it_finds(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            self.corpus(Path(where), "arm_data_proc_immediate", [0xE3A00000, 0xE3A01000])

            held = singlestep.sweep(Path(where), say=lambda _: None)

            self.assertEqual((held.compared, held.disagreed), (2, 0))

    def test_a_disagreement_is_counted_and_an_example_kept(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            self.corpus(Path(where), "arm_data_proc_immediate", [0xE3A0002A])

            held = singlestep.sweep(Path(where), say=lambda _: None)

            self.assertEqual((held.disagreed, len(held.examples)), (1, 1))

    def test_a_file_dropped_whole_is_counted_rather_than_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            self.corpus(Path(where), "arm_bx", [0xE12FFF10])

            held = singlestep.sweep(Path(where), say=lambda _: None)

            self.assertIn("arm_bx: no such row in Figure 28", held.excluded)

    def test_and_none_of_its_cases_are_compared(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            self.corpus(Path(where), "arm_bx", [0xE12FFF10])

            held = singlestep.sweep(Path(where), say=lambda _: None)

            self.assertEqual(held.compared, 0)

    def test_counting_reads_the_cases_without_running_them(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            self.corpus(Path(where), "arm_data_proc_immediate", [0xE3A0002A])

            held = singlestep.sweep(Path(where), counting=True, say=lambda _: None)

            self.assertEqual((held.compared, held.disagreed), (1, 0))

    def test_a_limit_stops_a_file_early(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            self.corpus(Path(where), "arm_data_proc_immediate", [0xE3A00000] * 6)

            held = singlestep.sweep(Path(where), limit=2, say=lambda _: None)

            self.assertEqual(held.compared, 2)

    def test_a_sweep_says_what_it_read_rather_than_only_the_total(self) -> None:
        said: list[str] = []
        with tempfile.TemporaryDirectory() as where:
            self.corpus(Path(where), "arm_data_proc_immediate", [0xE3A00000])

            singlestep.sweep(Path(where), say=said.append)

            self.assertIn("arm_data_proc_immediate", "\n".join(said))


class TheCommandLineTest(unittest.TestCase):
    def test_a_directory_that_is_not_there_reports_no_corpus_and_exits_zero(self) -> None:
        said: list[str] = []

        held = singlestep.main(["/nowhere/at/all"], say=said.append)

        self.assertEqual((held, "no corpus" in "\n".join(said)), (0, True))

    def test_a_directory_with_a_corpus_in_it_is_swept(self) -> None:
        said: list[str] = []
        with tempfile.TemporaryDirectory() as where:
            SweepingADirectoryTest().corpus(Path(where), "arm_swi", [0xE3A00000])

            held = singlestep.main([where], say=said.append)

            self.assertEqual(held, 0)

    def test_a_limit_can_be_given_on_the_command_line(self) -> None:
        said: list[str] = []
        with tempfile.TemporaryDirectory() as where:
            SweepingADirectoryTest().corpus(Path(where), "arm_swi", [0xE3A00000] * 4)

            singlestep.main([where, "--limit", "1"], say=said.append)

            self.assertIn("1 usable", "\n".join(said))

    def test_counting_can_be_asked_for_on_the_command_line(self) -> None:
        said: list[str] = []
        with tempfile.TemporaryDirectory() as where:
            SweepingADirectoryTest().corpus(Path(where), "arm_swi", [0xE3A00000])

            held = singlestep.main([where, "--count"], say=said.append)

            self.assertEqual(held, 0)

    def test_a_run_with_no_path_looks_where_the_usage_says(self) -> None:
        said: list[str] = []

        held = singlestep.main([], say=said.append)

        self.assertEqual(held, 0)


class ComparingTheBanksTest(unittest.TestCase):
    def test_a_banked_register_the_model_does_not_reach_is_reported(self) -> None:
        one = case(0xE1A00001)
        final = list(one.initial)
        final[15] = one.initial[15] + 4
        final[singlestep.BANKS_AT["fiq"]] = 0xDEAD
        one = one._replace(final=tuple(final))

        held = singlestep.compare(one)

        self.assertIn("R13_fiq", held[0])

    def test_a_fiq_low_register_the_model_does_not_reach_is_reported(self) -> None:
        one = case(0xE1A00001)
        final = list(one.initial)
        final[15] = one.initial[15] + 4
        final[singlestep.FIQ_LOW_AT] = 0xDEAD
        one = one._replace(final=tuple(final))

        held = singlestep.compare(one)

        self.assertIn("R8_fiq", held[0])

    def test_a_saved_status_register_the_model_does_not_reach_is_reported(self) -> None:
        one = case(0xE1A00001)
        final = list(one.initial)
        final[15] = one.initial[15] + 4
        final[singlestep.SPSR_AT] = 0xDEAD
        one = one._replace(final=tuple(final))

        held = singlestep.compare(one)

        self.assertIn("SPSR_fiq", held[0])


class TheRemainingBranchesTest(unittest.TestCase):
    def test_a_byte_read_is_seeded_at_byte_width(self) -> None:
        one = case(0xE5D10000, r1=0x2000)._replace(reads=((1, 0x2000, 0x9C),))
        final = list(one.initial)
        final[0] = 0x9C
        final[15] = one.initial[15] + 4
        one = one._replace(final=tuple(final))

        held = singlestep.compare(one)

        self.assertEqual(held, [])

    def test_a_counter_the_model_does_not_reach_is_reported(self) -> None:
        one = case(0xE1A00001)
        one = one._replace(final=(*one.initial[:15], 0xDEAD, *one.initial[16:]))

        held = singlestep.compare(one)

        self.assertIn("R15", held[0])

    def test_a_status_register_the_model_does_not_reach_is_reported(self) -> None:
        one = case(0xE1A00001)
        final = list(one.initial)
        final[15] = one.initial[15] + 4
        final[singlestep.CPSR] = 0x000000D2
        one = one._replace(final=tuple(final))

        held = singlestep.compare(one)

        self.assertIn("CPSR", held[0])

    def test_a_case_the_filter_removes_is_counted_by_the_sweep(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            SweepingADirectoryTest().corpus(Path(where), "arm_data_proc_immediate", [0xE3A00000])
            data = bytearray((Path(where) / "arm_data_proc_immediate.json.bin").read_bytes())
            at = 8 + 4 + 8 + singlestep.CPSR * 4
            data[at : at + 4] = (0x0000001F).to_bytes(4, "little")
            (Path(where) / "arm_data_proc_immediate.json.bin").write_bytes(bytes(data))

            held = singlestep.sweep(Path(where), say=lambda _: None)

            self.assertEqual((held.compared, held.excluded.get("system mode")), (0, 1))

    def test_only_the_first_few_disagreements_are_kept_as_examples(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            SweepingADirectoryTest().corpus(
                Path(where), "arm_data_proc_immediate", [0xE3A0002A] * 9
            )

            held = singlestep.sweep(Path(where), say=lambda _: None)

            self.assertEqual((held.disagreed, len(held.examples)), (9, singlestep.EXAMPLES))


if __name__ == "__main__":
    unittest.main(verbosity=2)
