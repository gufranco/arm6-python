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
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import singlestep  # noqa: E402

STATE = 40


def state() -> list[int]:
    """One state block, mostly zeros, in a privileged mode."""
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


class TheFilterTest(unittest.TestCase):
    def test_a_case_in_a_mode_this_part_has_is_kept(self) -> None:
        held = singlestep.excluded(case(0xE1A00001), "arm_data_proc_immediate")

        self.assertIsNone(held)

    def test_a_case_in_system_mode_is_excluded(self) -> None:
        one = case(0xE1A00001)
        one = one._replace(initial=(*one.initial[:31], 0x0000001F, *one.initial[32:]))

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
        one = one._replace(initial=(*one.initial[:31], 0x000000F3, *one.initial[32:]))

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

    def test_the_fetch_list_leaves_out_every_file_dropped_whole(self) -> None:
        held = singlestep.wanted()

        dropped = [one for one in held if any(name in one for name in singlestep.WHOLE_FILES)]

        self.assertEqual(dropped, [])

    def test_and_names_every_file_that_is_kept(self) -> None:
        held = singlestep.wanted()

        self.assertEqual(len(held), len(singlestep.ARM_FILES) - len(singlestep.WHOLE_FILES))

    def test_the_file_list_covers_the_whole_corpus(self) -> None:
        record = singlestep.pinned()["suites"][0]

        self.assertEqual(
            len(singlestep.ARM_FILES) * record["casesPerFile"], record["armStateCases"]
        )

    def test_asking_for_the_file_list_prints_it_and_exits_zero(self) -> None:
        said: list[str] = []

        held = singlestep.main(["--files"], say=said.append)

        self.assertEqual((held, len(said)), (0, len(singlestep.wanted())))

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


class SweepingADirectoryTest(unittest.TestCase):
    """The whole run, over a corpus built here rather than fetched.

    A sweep is where the counting happens, and a count is what separates coverage
    from silence, so it is driven over a directory whose contents are known: one
    file the filter keeps and one it drops whole.
    """

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


class ReadingABankedRegisterTest(unittest.TestCase):
    def test_a_low_register_comes_from_the_base_bank(self) -> None:
        one = case(0xE1A00001)

        held = singlestep._visible(one, 3)

        self.assertEqual(held, one.initial[3])

    def test_a_middle_register_comes_from_the_fiq_bank_in_fiq_mode(self) -> None:
        initial = state()
        initial[singlestep.FIQ_LOW_AT + 1] = 0xF1
        initial[9] = 0xB1
        initial[singlestep.CPSR] = 0x000000D1
        one = case(0xE1A00001)._replace(initial=tuple(initial))

        held = singlestep._visible(one, 9)

        self.assertEqual(held, 0xF1)

    def test_and_from_the_base_bank_in_any_other(self) -> None:
        initial = state()
        initial[singlestep.FIQ_LOW_AT + 1] = 0xF1
        initial[9] = 0xB1
        one = case(0xE1A00001)._replace(initial=tuple(initial))

        held = singlestep._visible(one, 9)

        self.assertEqual(held, 0xB1)

    def test_a_stack_pointer_comes_from_the_mode_s_own_bank(self) -> None:
        initial = state()
        initial[singlestep.BANKS_AT["svc"]] = 0x5C
        one = case(0xE1A00001)._replace(initial=tuple(initial))

        held = singlestep._visible(one, 13)

        self.assertEqual(held, 0x5C)

    def test_and_from_the_base_bank_in_a_user_mode(self) -> None:
        initial = state()
        initial[13] = 0xB13
        initial[singlestep.CPSR] = 0x00000010
        one = case(0xE1A00001)._replace(initial=tuple(initial))

        held = singlestep._visible(one, 13)

        self.assertEqual(held, 0xB13)

    def test_the_counter_comes_from_the_base_bank(self) -> None:
        one = case(0xE1A00001)

        held = singlestep._visible(one, 15)

        self.assertEqual(held, one.initial[15])


class EveryRestrictionIsDrivenTest(unittest.TestCase):
    """Each entry of the filter, against a case built to trip it.

    An exclusion can only ever make a run look better, so every one of them is
    driven here rather than trusted.
    """

    def trips(self, opcode: int, stem: str, **named: int) -> str | None:
        return singlestep.excluded(case(opcode, **named), stem)

    def test_r15_as_a_multiply_operand(self) -> None:
        self.assertEqual(self.trips(0xE00F0291, "arm_mul_mla"), "R15 as a multiply operand")

    def test_r15_as_a_swap_operand(self) -> None:
        self.assertEqual(self.trips(0xE102F090, "arm_swp"), "R15 as a swap operand")

    def test_r15_as_the_base_of_a_block_transfer(self) -> None:
        self.assertEqual(
            self.trips(0xE89F0001, "arm_ldm_stm"), "R15 as the base of a block transfer"
        )

    def test_r15_as_a_transfer_s_register_offset(self) -> None:
        self.assertEqual(
            self.trips(0xE791000F, "arm_ldr_str_register_offset"),
            "R15 as a transfer's register offset",
        )

    def test_write_back_onto_r15_as_a_base(self) -> None:
        self.assertEqual(
            self.trips(0xE5BF0000, "arm_ldr_str_immediate_offset"),
            "write-back onto R15 as a transfer's base",
        )

    def test_a_post_indexed_transfer_whose_offset_is_its_base(self) -> None:
        self.assertEqual(
            self.trips(0xE6910001, "arm_ldr_str_register_offset"),
            "a post-indexed transfer whose offset register is its base",
        )

    def test_r15_as_the_destination_of_a_psr_read(self) -> None:
        self.assertEqual(self.trips(0xE10FF000, "arm_mrs"), "R15 as the destination of a PSR read")

    def test_an_spsr_reached_from_a_user_mode(self) -> None:
        initial = state()
        initial[singlestep.CPSR] = 0x00000010
        one = case(0xE14F0000)._replace(initial=tuple(initial), final=tuple(initial))

        self.assertEqual(singlestep.excluded(one, "arm_mrs"), "an SPSR reached from a user mode")

    def test_an_msr_field_mask_the_figure_does_not_print(self) -> None:
        self.assertEqual(
            self.trips(0xE12AF000, "arm_msr_reg"),
            "an MSR field mask Figure 14 does not print",
        )

    def test_r15_as_the_source_of_a_psr_write(self) -> None:
        self.assertEqual(self.trips(0xE129F00F, "arm_msr_reg"), "R15 as the source of a PSR write")

    def test_r15_as_the_register_holding_a_shift_amount(self) -> None:
        self.assertEqual(
            self.trips(0xE1A00F11, "arm_data_proc_register_shift"),
            "R15 as the register holding a shift amount",
        )

    def test_the_s_bit_of_a_block_transfer_outside_a_privileged_mode(self) -> None:
        initial = state()
        initial[singlestep.CPSR] = 0x00000010
        one = case(0xE8D10001)._replace(initial=tuple(initial), final=tuple(initial))

        self.assertEqual(
            singlestep.excluded(one, "arm_ldm_stm"),
            "the S bit of a block transfer set outside a privileged mode",
        )

    def test_base_write_back_with_the_s_bit_set(self) -> None:
        self.assertEqual(
            self.trips(0xE8F10001, "arm_ldm_stm"),
            "base write-back with the S bit of a block transfer set",
        )

    def test_a_case_ending_in_a_mode_this_part_does_not_have(self) -> None:
        one = case(0xE1A00001)
        one = one._replace(final=(*one.final[:31], 0x0000001F, *one.final[32:]))

        self.assertEqual(
            singlestep.excluded(one, "arm_data_proc_immediate"),
            "ends in a mode ARM60 does not have",
        )

    def test_a_mode_the_generator_s_part_cannot_enter(self) -> None:
        initial = state()
        initial[1] = 0x00000000
        one = case(0xE129F001)._replace(initial=tuple(initial), final=tuple(initial))

        self.assertEqual(
            singlestep.excluded(one, "arm_msr_reg"),
            "a mode the generator's part cannot enter written into a PSR",
        )

    def test_and_a_thirty_two_bit_mode_is_not_excluded_for_that_reason(self) -> None:
        initial = state()
        initial[1] = 0x00000013
        one = case(0xE129F001)._replace(initial=tuple(initial), final=tuple(initial))

        self.assertIsNone(singlestep.excluded(one, "arm_msr_reg"))


class WhatIsLeftOutOfAComparisonTest(unittest.TestCase):
    def test_a_multiply_that_sets_flags_leaves_the_carry_out(self) -> None:
        held = singlestep._not_comparable(0xE0100291)

        self.assertEqual(held, singlestep.MEANINGLESS_CARRY)

    def test_a_multiply_that_does_not_set_flags_leaves_nothing_out(self) -> None:
        held = singlestep._not_comparable(0xE0000291)

        self.assertEqual(held, 0)

    def test_a_psr_write_leaves_the_reserved_region_out(self) -> None:
        held = singlestep._not_comparable(0xE128F000)

        self.assertEqual(held, singlestep.RESERVED_ON_A_PSR_WRITE)

    def test_and_so_does_the_whole_form(self) -> None:
        held = singlestep._not_comparable(0xE129F000)

        self.assertEqual(held, singlestep.RESERVED_ON_A_PSR_WRITE)

    def test_an_ordinary_instruction_leaves_nothing_out(self) -> None:
        held = singlestep._not_comparable(0xE1A00001)

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
    """The paths a passing run never takes, driven once so each has run."""

    def test_a_case_a_user_mode_can_legitimately_run_is_kept(self) -> None:
        initial = state()
        initial[singlestep.CPSR] = 0x00000010
        one = case(0xE1A00001)._replace(initial=tuple(initial), final=tuple(initial))

        held = singlestep.excluded(one, "arm_data_proc_immediate")

        self.assertIsNone(held)

    def test_a_swap_naming_no_counter_is_kept(self) -> None:
        held = singlestep.excluded(case(0xE1020091), "arm_swp")

        self.assertIsNone(held)

    def test_a_transfer_with_an_immediate_offset_of_fifteen_is_not_a_register_offset(
        self,
    ) -> None:
        held = singlestep.excluded(case(0xE591000F), "arm_ldr_str_immediate_offset")

        self.assertIsNone(held)

    def test_a_block_transfer_without_the_s_bit_is_kept(self) -> None:
        held = singlestep.excluded(case(0xE8910001), "arm_ldm_stm")

        self.assertIsNone(held)

    def test_a_psr_read_that_names_no_counter_is_kept(self) -> None:
        held = singlestep.excluded(case(0xE10F0000), "arm_mrs")

        self.assertIsNone(held)

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

    def test_the_s_flag_with_the_counter_as_destination_in_a_user_mode(self) -> None:
        initial = state()
        initial[singlestep.CPSR] = 0x00000010
        one = case(0xE1B0F000)._replace(initial=tuple(initial), final=tuple(initial))

        held = singlestep.excluded(one, "arm_data_proc_immediate_shift")

        self.assertEqual(held, "S bit with R15 as destination in a user mode")

    def test_an_immediate_written_into_the_whole_psr(self) -> None:
        held = singlestep.excluded(case(0xE329F0D3), "arm_msr_imm")

        self.assertEqual(held, "an eight bit immediate written into the whole PSR")

    def test_a_psr_write_reaching_an_spsr_from_a_user_mode(self) -> None:
        initial = state()
        initial[singlestep.CPSR] = 0x00000010
        one = case(0xE169F000)._replace(initial=tuple(initial), final=tuple(initial))

        held = singlestep.excluded(one, "arm_msr_reg")

        self.assertEqual(held, "an SPSR reached from a user mode")

    def test_a_block_transfer_with_the_s_bit_and_no_write_back_is_kept(self) -> None:
        held = singlestep.excluded(case(0xE8D10001), "arm_ldm_stm")

        self.assertIsNone(held)

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
