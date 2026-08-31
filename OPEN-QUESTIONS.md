# Open questions

What this project does not know for certain, and what it would take to find out.

Everything here is a place where being faithful to the silicon is still a claim
rather than a measurement. The record that drives this file is
[`conformance/divergences.json`](conformance/divergences.json); this document is
the same content written for a reader rather than for a test.

The settled surface is not small. Every figure the ARM60 datasheet prints about
this part is quoted in [`conformance/hardware.json`](conformance/hardware.json)
with the page it appears on, checked against a rendered image of that page rather
than against a text layer the document does not have. Every instruction form's
cost is held to Table 20, and the whole processor state is compared after every
instruction against a filtered corpus. What follows is the residue.

## The ceiling above all of these

### Nothing here rests on a measurement of real silicon

Rung two of the family ladder is a measurement on real hardware and rung three is
a simulation of the die. Both are empty. No ARM60 has been probed for this
package, and no implementation of this architecture in reconfigurable logic is
known to exist to compare against. Every claim below rests on a document, or on a
recording taken from a later part.

That is not a gap somebody can close by reading harder. It needs a logic analyser
on the pins of a real part, or a die photograph read into a netlist, and until
one of those exists this member is held to paper and to one recording.

## What the documents leave open

### What the extra cycle of a register-specified shift is

Two chapters of one datasheet disagree, and the disagreement is worth stating
carefully because it is the sharpest thing this project found.

Table 5 gives a data operation with a register-specified shift two rows. Their
pins read `seq=0, Nmreq=1` and then `seq=1, Nmreq=0`, which Table 3 names an
internal cycle followed by a sequential one: `1S+1I`. Table 20 costs the same
form at `1S` plus `1S for SHIFT(Rs)`, which is `2S`.

The count agrees. Only the type differs. This package follows Table 5, for two
reasons: a per-cycle table states the pins rather than summarising them, and the
same two rows appear again in Table 6 for a multiply by 0 or 1, which Table 20
itself costs at `1S+1I`. Two of the three readings in that one document say
internal.

A later issue of the datasheet would settle it, or a measurement of `Nmreq`
during a register-shifted data operation.

### What the shifter carry is after an immediate operand is rotated

Nothing disagrees here; the document stops. Section 7.3.3 gives the immediate
value and the rotate applied to it and says nothing about the shifter's carry
output, while section 7.3.1 says a logical operation takes its C flag from the
barrel shifter. So every logical operation with an immediate operand and the S
bit set writes a C flag the datasheet does not specify.

This package follows the corpus: a rotate of zero passes the old flag through and
any other rotate takes bit 31 of the result. That is rung four, and it is named
as rung four in the record.

### What the encodings that do not trap actually do

The note beneath Figure 28 says that some instruction codes are not defined but
do **not** cause the undefined instruction trap, and gives a multiply with bit 5
or bit 6 set as its example. It does not say what they do.

Application Note 11 says the behaviour of an unobserved restriction is the ARM2aS
macrocell's. The document that would answer each case is therefore the VTI data
book for that macrocell, which is not pinned here.

So this package refuses these encodings and names the word it could not answer
for. Choosing a behaviour would mean inventing one.

### What Ntrans does during a store register

Table 8 heads a column `Ntrans` and prints no values beneath it, in either of its
two rows. Every other column in that table is filled, and Table 8 is the only
instruction table that heads that column at all, so the one place the datasheet
chose to draw attention to the pin is the one place it left blank.

This package follows the signal chapter, which gives `Ntrans` as LOW when the
processor is in user mode, so the pin follows the mode rather than the
instruction. Table 12 corroborates it: exception entry prints `Ntrans` HIGH for
all three of its cycles, which is what a change into a privileged mode looks like.

### The AC parameters are preliminary data and the datasheet says so

Chapter 12 opens by calling its own figures preliminary data subject to change
when device characterisation is complete. That bounds one claim and not another:
the cycle counts in chapter 10 carry no such warning and are used freely, while
the clock rate derived from `Tckl` and `Tckh` is provisional and is only ever
printed as a comparison, never used to compute anything.

## The parts with no document

### The ARM600 has no datasheet anybody has published

The core is the same. The ARM610 datasheet says outright that the CPU within
ARM610 is the ARM6, and gives the ARM600 delta as five items, every one of them a
bus or packaging difference rather than a core one. So the instruction set would
carry across unchanged.

What is missing is the bus, which is what this family models a clocked part down
to. An ARM600 datasheet with a chapter at the resolution of ARM60's chapter 10
would settle it, and nothing else would.

### The ARM610 bus is a different machine from the one ARM60 documents

The ARM610 datasheet is pinned here and is a good second witness for the
instruction set, which is exactly what makes this worth writing down: the
temptation is to model the part from it.

Its chapter 10 gives two input clocks rather than one, two cycle types rather
than four, `SEQ` derived from `nMREQ` rather than driven independently, the clock
a cycle runs on decided by whether the cache hit, and sequential runs interrupted
on a 256 word boundary so the memory management unit can check the next sub-page.
There is no instruction cycle chapter in that document, and ARM60's cannot be
carried across, because the bus it describes is not that part's bus.

### ARM61 is a real part with no datasheet found

The ARM60 datasheet names it twice, once in the list of parts without selectable
endianness and once in the list of parts supporting the early abort mechanism.
Nothing else about it has been found.

## Where the question is a scope boundary, not an unknown

### Which way round the bigend pin is tied

The pin is an input and a board ties it, so the part has no default and the
datasheet names none. It matters more than it sounds: an unaligned word load, a
byte load and a byte store all get separate treatment in the two configurations,
each with its own section.

Both are modelled and either can be asked for. The default is little endian,
because that is what the parts without the pin are and because a store has to be
constructible without a board attached.

Reading both sections closely produced one small result worth recording: the two
configurations describe the rotation differently and rotate by the same amount.
In little endian the addressed byte ends up in bits 0 to 7, in big endian at 31
to 24 or 15 to 8 depending on the offset, and in both cases the word is rotated
right by eight times the offset.

So this is listed as a boundary rather than a gap: nothing about the part is
unknown here, and a reader who found it under the document's open questions
would reasonably think something was.

## What is deliberately not modelled

Four things are absent on purpose rather than unknown, and each is written down
so the omission reads as a decision rather than an oversight.

**The 26 bit program space configuration is not modelled.** Chapter 9 says the
remainder of the document describes ARM60 configured for a 32 bit program and
data space and recommends that configuration for all new designs, so that is what
this package models. The four 26 bit *modes* are modelled, because they are
reachable from a 32 bit configuration and Application Note 11 gives their
encodings. The 26 bit *configuration*, with `prog32` LOW, is not, and neither is
the address exception vector at `0x14` that exists only in it.

**No coprocessor is attached and none is modelled.** Section 10.15 states what
happens when a coprocessor cannot perform an instruction: it must not drive `cpa`
or `cpb` LOW, they remain HIGH, and the undefined instruction trap is taken. That
is exactly what an absent coprocessor looks like on this bus, so all three
coprocessor rows of Figure 28 take that trap and the busy-wait count Table 20
calls `b` is always zero. Attaching one would need a document describing a
particular coprocessor, and none is pinned here.

**The abort pin is not driven and the two abort vectors are not reached.** The
datasheet describes both aborts fully, including which instructions are
restartable and what `lateabt` changes. What is missing is a memory system that
can refuse an access, and that is a caller's to supply rather than something this
package can invent.

**Boundary scan is documented and deliberately not modelled.** Chapter 13 covers
the whole of it, including the four bit instruction register and eight public
instructions. This package models the core rather than the test port.

## What is not in question

Everything the ARM60 datasheet prints about this part, because it was read page
by page rather than searched, and because every sentence quoted in the record was
checked against a rendered image of the page it is cited to.

That check is worth a sentence of its own. The document carries no text layer at
all: asking `pdftotext` for its contents returns one newline per page and nothing
else. A search of the text layer would therefore have found nothing and the
absence would have meant nothing. Every one of the passages in
[`conformance/hardware.json`](conformance/hardware.json) was placed by rendering
the page and reading it, and the checker that holds them there does the same.

Two contradictions inside the document were found and both are settled rather
than open. The register count on page 1 disagrees with page 10; the block diagram
and the ARM610 datasheet both agree with page 10, and 27 is the figure the earlier
part had, carried over when the text was adapted. The signal chapter prints two
consecutive rows both named `Nrw` and gives `tms` and `tdi` the same pin number;
the packaging chapter gives the right answers to both, and the mislabelled row's
own description is of a byte and word transfer, which is `Nbw`. Neither is
findable by searching. Both come out of reading the document to the end.
