"""That the corpus reader reads, the filter filters, and both fail when they should.

The corpus is not carried here: it is nearly a gigabyte and it belongs to its own
project. So every check in this file works from a case built in memory rather
than from the files, and the run against the real thing is a step of its own that
reports how many cases it read.

The filter is the part worth checking hardest. Every entry in it removes cases
from a comparison, which is the one kind of change that can only ever make a run
look better, so each one is driven against a case built to trip it and against a
case built not to.
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import singlestep  # noqa: E402

STATE = 40


def state(**named: int) -> tuple[int, ...]:
    """One state block, mostly zeros, with the named words set."""
    held = [0] * STATE
    held[singlestep.CPSR] = 0x000000D3
    for name, value in named.items():
        held[getattr(singlestep, name.upper()) if name.isupper() else int(name[1:])] = value
    return tuple(held)


def case(opcode: int, base: int = 0x1000, **named: int) -> singlestep.Case:
    initial = list(state())
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


class TheFilterTest(unittest.TestCase):
    def test_a_case_in_a_mode_this_part_has_is_kept(self) -> None:
        held = singlestep.excluded(case(0xE1A00001), "arm_data_proc_immediate")

        self.assertIsNone(held)

    def test_a_case_in_system_mode_is_excluded(self) -> None:
        one = case(0xE1A00001)
        one = one._replace(initial=one.initial[:31] + (0x0000001F,) + one.initial[32:])

        held = singlestep.excluded(one, "arm_data_proc_immediate")

        self.assertEqual(held, "system mode")

    def test_a_multiply_whose_destination_differs_from_its_multiplicand_is_kept(self) -> None:
        held = singlestep.excluded(case(0xE0010293), "arm_mul_mla")

        self.assertIsNone(held)

    def test_a_multiply_whose_destination_is_its_multiplicand_is_excluded(self) -> None:
        held = singlestep.excluded(case(0xE0010291), "arm_mul_mla")

        self.assertEqual(held, "Rd equals Rm")

    def test_and_that_rule_applies_only_to_the_multiply_file(self) -> None:
        held = singlestep.excluded(case(0xE0010291), "arm_data_proc_immediate")

        self.assertIsNone(held)

    def test_a_block_transfer_naming_registers_is_kept(self) -> None:
        held = singlestep.excluded(case(0xE8910001), "arm_ldm_stm")

        self.assertIsNone(held)

    def test_a_block_transfer_naming_none_is_excluded(self) -> None:
        held = singlestep.excluded(case(0xE8910000), "arm_ldm_stm")

        self.assertEqual(held, "empty register list")

    def test_a_multiply_encoding_with_bit_five_set_is_excluded(self) -> None:
        held = singlestep.excluded(case(0xE00002B1), "arm_mul_mla")

        self.assertEqual(held, "undefined multiply encoding")

    def test_a_case_with_the_thumb_bit_set_is_excluded(self) -> None:
        one = case(0xE1A00001)
        one = one._replace(initial=one.initial[:31] + (0x000000F3,) + one.initial[32:])

        held = singlestep.excluded(one, "arm_data_proc_immediate")

        self.assertEqual(held, "bit 5 of the CPSR set")

    def test_a_file_the_figure_has_no_row_for_is_dropped_whole(self) -> None:
        held = singlestep.dropped("arm_bx")

        self.assertEqual(held, "no such row in Figure 28")

    def test_a_coprocessor_file_is_dropped_whole_too(self) -> None:
        held = singlestep.dropped("arm_cdp")

        self.assertEqual(held, "no coprocessor attached")

    def test_a_file_this_part_does_have_a_row_for_is_not_dropped(self) -> None:
        held = singlestep.dropped("arm_b_bl")

        self.assertIsNone(held)

    def test_every_file_the_filter_drops_is_named_in_the_record(self) -> None:
        record = singlestep.pinned()
        named = {one for entry in record["filter"]["wholeFiles"] for one in entry["files"]}

        self.assertEqual(named, set(singlestep.WHOLE_FILES))


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
