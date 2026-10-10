# Known limitations — `iupac_namer` (this fork)

What this engine gets wrong, measured rather than guessed. Every entry was
reproduced, and every "should be" name was verified by parsing it back with
OPSIN and comparing the structure on canonical SMILES **and** full InChIKey.

Severity, used consistently here and in the regression suite:

| | meaning |
|---|---|
| **A** | wrong molecule — the name denotes something else |
| **B** | right molecule, non-preferred name |
| **C** | style / dead code |

The live list is `tests/test_namer_known_defects.py`. Open defects there are
`xfail(strict=True)`, so fixing one **fails** the suite and forces this
document and that table to be updated rather than silently drifting.

## The failure shape worth understanding first

`charge_perception.detect()` returns `None` when no classifier claims a
charged molecule, or when a classifier claims it but the renderer cannot
compose a name. `None` does **not** mean "no name": the engine falls through
to the generic plan search, which *neutralizes* the molecule and names the
neutral skeleton. So a missing rule surfaces as a confident wrong structure —
the benzyl cation as `methylbenzene`, which is toluene — with nothing in the
output to suggest a problem.

This is why these defects cannot be found by reading the code: the code that
produces the wrong answer is working exactly as written. Set
`IUPAC_NAMER_DEBUG=1`, or open a `diagnostics.capture()` scope, to record
every such fall-through attributed to the gate that let it go. See
`iupac_namer/diagnostics.py`.

Two of those fall-through reasons now raise instead of neutralizing — see
*The refusal guard* below for which, and why the third must not.

## Open defects (severity A — wrong molecule)

**None.** Every severity-A defect found by the sweeps, the benchmark and the
corpus extension has been fixed; the table in
`tests/test_namer_known_defects.py` holds 491 rows over 77 distinct defect
numbers (after naming round 4): each defect's own rows, and the converse and
non-regression rows guarding the paths its fix could have stolen from.

That is a statement about what has been *looked for*, not a claim that none
exists. The instrument that found most of them is still in the box: set
`IUPAC_NAMER_DEBUG=1`, or open a `diagnostics.capture()` scope, and sweep a
corpus. The `OPEN` list in the defect table is deliberately kept, empty, so a
newly found defect can be added as `xfail(strict=True)` — fixing it then FAILS
the suite and forces this document and that table to be updated together.

The last one to go, D-024, is worth keeping as a worked example because the
two obvious fixes were both wrong:

> A ring N-oxide in substituent position came out as
> `(pyridin-4-yl)methan-1-ylium 1-oxide`, which OPSIN cannot parse. Additive
> nomenclature produces a two-word name, and a substituent has to end in
> `-yl` for its parent to attach to it — there is nothing to attach to the end
> of the word "oxide".
>
> A curated ring entry keyed on the N-oxide ring is **dead data**: the
> additive path strips the exocyclic `[O-]` *before* ring lookup, so the ring
> reaching the table is plain pyridine. Composing the name by hand from parts
> the engine does give means reimplementing substituent assembly for one
> molecular shape.
>
> What actually worked was one condition: the additive path declines in
> SUBSTITUENT output form. The substitutive path already knew how to render
> it — `1-(oxido)pyridin-1-ium-4-yl` — it was simply never reached. Standalone
> output is untouched, so `pyridine 1-oxide` and
> `pyridine-4-carboxylate 1-oxide` keep the additive form correct for them.

### Observed, no verified target

`[C-]1C=CC=C1` names as `cyclopenta-2,4-dien-1-ide`, dropping the unpaired
electron. This is the cyclopentadienyl **radical anion** — a different species
from cyclopentadienide, with a different InChIKey. `cyclopentadienide` was
tried as the target name and rejected by the round-trip check: it denotes the
closed-shell anion. No name was found that OPSIN parses back to the radical
anion, so none is stated. Not in the defect table, which requires a verified
target.

## Benchmark: the standing 4 of 124

On the original 124-row corpus the engine scores 120/124. All four rows were
characterised; two were called "not engine errors at all", and that turned out
to be **true of one of them and wrong about the other** — see below.

(The corpus has since grown to 181 rows and now covers ring N-oxides,
substituted guanidiniums and tautomer pairs — the families the last few fixes
landed in, none of which the corpus could previously see. Current score
**180/181**: zero wrong structures, zero refusals, zero unparsable names, and
one `gate_disagreement` (metformin, below).)

### Tautomers — three different situations, not one

An earlier version of this document said the two standing tautomer failures
were "not engine errors at all". That was **wrong for one of them**, and the
mistake is worth recording: a matching InChIKey was read as proof the engine
was right, when all it proves is that InChI declines to distinguish mobile
hydrogens. Agreement from a gate that cannot see the difference is not
evidence.

Tested properly, the three cases separate:

**1,2,3-triazole — a real defect, fixed (D-026).** The ring table entry for
`c1cn[nH]n1` was labelled `1H-1,2,3-triazole`, which is the *other* tautomer
(OPSIN parses 1H- to `c1c[nH]nn1`), and the 1H form had no entry at all. So
both inputs came back as the 1H structure: the indicated hydrogen the caller
supplied was discarded. Same class as silently flattening stereochemistry.
The 1,2,4-triazole and tetrazole entries beside it already distinguished their
tautomers correctly, so this was an outlier rather than a policy.

The corroboration was sitting in the corpus the whole time: that row's PubChem
ground truth reads `2H-triazole`. An independent source had the tautomer right
while the engine, the ring table and a test in this repository all agreed on the wrong
one — they agreed because the test was written from the table. Agreement
between things with a common ancestor is not corroboration.

**Purine — deliberate, and left alone.** All four tautomers are labelled
`9H-purine`, the IUPAC preferred parent, with `atom_locants` built so N9 gets
locant 9 whatever the canonical SMILES does. `data_loader.py` states the
reasoning, and the whole xanthine/caffeine family is numbered off it. Giving
`c1ncc2nc[nH]c2n1` the name `9H-purine` does lose which tautomer was supplied,
and that is a known consequence of a decision taken on purpose.

**Metformin — not a defect, and not fixable by naming.** The engine emits
`1,1-dimethylbiguanide`. `biguanide` is an IUPAC retained name for the
substance and carries no tautomer information at all — `1H-biguanide` and
`2H-biguanide` do not parse, unlike `1H-`/`2H-triazole`. OPSIN simply has to
pick a depiction when it emits SMILES. Both depictions share an InChIKey, and
both get the same correct name. This is precisely what `gate_disagreement`
exists to surface: same substance, different depiction, a human decides.

### Genuine wrong structures

**None remain.** Every row that used to sit here is fixed: the novel
pyrazolone (D-022), diazomethane (D-019), and the triazole above (D-026).
Every molecule in the corpus that the engine names, it names with a name
denoting the molecule it was given.

Diazomethane is worth one note in the other direction. It is named
`methanidyldiazonium`, and the canonical SMILES gate *disagrees* with the
corpus entry — `[CH2-][N+]#N` versus `C=[N+]=[N-]` — because those are two
Lewis structures of one substance, identical InChIKey
`YXHKONLOYHBTNS-UHFFFAOYSA-N`. Here the InChIKey gate is the one that sees
correctly and the SMILES gate is fooled; with the triazole it was the reverse.
Neither gate is the stronger one, which is the whole argument for running two:
where they disagree, something needs a human, and that is the only reliable
signal either of them gives about its own blind spot.

## Severity B — right molecule, non-preferred name

| input | emits | preferred | rule |
|---|---|---|---|
| `ClC(=O)C(=O)Cl` | `ethane-1,2-dioyl chloride` | `oxalyl dichloride` | `oxalyl` IS the PIN acyl group (P-65.1.7.2.1); the `di` multiplier is also missing |

The acyl-halide case is **not** a matter of adding a table entry. Instrumenting
`_acid_name_to_acyl` over 200+ molecules showed only two distinct acid names
ever reach it, and the acyl-halide name is not built through it at all — so
routing it through the retained lookup is a structural change to that path, not
a data fix. Deferred rather than attempted.

`malonamide` -> `propanediamide` and `malonaldehyde` -> `propanedial` were
fixed: both came from `retained_pins` in
`data/retained_names_expanded.json` tagged `"source": "algorithm.py", "rule":
"various"` — i.e. unvetted — and both contradicted the engine's own acid path,
which already emitted `butanediamide` and `butanedial` for the next homologue.

**`succinimide` in the same file is a genuine PIN** with a correct P-66.2
citation and must not be "corrected" to match.

### Unaudited data

261 of the 292 `retained_pins` entries carry `"rule": "various"`, meaning
no rule was ever cited for them, and 161 were harvested from OPSIN's
dictionary. Round 3 audited 18, chosen from those a benchmark name reaches (see
`CHANGELOG.md`, D-036; `isobutane` was one, now `2-methylpropane`). The
other 274 carry no `pin_status` -- not known to be wrong, but not known to
be right either, and that is the honest description.

## Severity C

`_RETAINED_ACID_TO_ACYL` (`engine.py`) carries four unreachable non-PIN keys
(`malonic`/`succinic`/`glutaric`/`adipic acid`) that the acid path never
produces, the same dead-key pattern already removed from
`_RETAINED_DIACID_TO_DIACYLIUM`.

## The refusal guard (resolved)

Two of the dispatcher's decline reasons now **raise** rather than falling
through to the neutralizer. The split was measured over the benchmark corpus
plus the 69-probe charged-species sweep — 193 molecules:

| reason | occurrences | behaviour | why |
|---|---|---|---|
| `render_failed` | 0 | **raises** | a classifier engaged and could not finish; the coverage gate has already proved every charge is claimed, so falling through can only name a different molecule |
| `partial_claim` | 1 | **raises** | as above; the one live case is D-019 |
| `unclaimed` | 35 | falls through | **not** a defect signal — pyridinium, sulfonium, betaine, nitrobenzene and phenylium all land here and are all named correctly by other paths |

Making `unclaimed` fatal would have broken dozens of correct names. Making the
other two fatal cost nothing on the day and converts any future gap from a
wrong molecule into a visible failure.

The visible effect: `name_smiles("[CH2-][N+]#N")` now raises instead of
returning `(azanylidyne)(methyl)azanium`. On the benchmark diazomethane moved
`wrong_structure -> no_prediction`; the score is unchanged at 120/124 because
both are failures, but one of them was lying.

## Substituent locants the tree cannot supply (engine side CLOSED, round 4)

`carve_substituent` now stamps each fragment atom with the atom it was
carved from, from the map it already checks for injectivity and element
identity; `extraction.fragment_origin` reads it back, and every `PrefixEntry`
carries it as `atom_origin` -- level-local, so a cached subtree reused for an
identical fragment stays correct. A consumer composes the maps down the tree
(OpenChem Studio's annotation layer does, and it corrected a naproxen
numbering that a ring-table guess had mirrored). Indole's 3a/7a are filled by
`ring_naming/fusion_locants.py` in the built ring table. The record of the
problem as it stood follows.


A ring system inside a SUBSTITUENT gets no atom locants out of the name tree,
so a consumer drawing numbering on a structure numbers a fentanyl's acetyl
chain and neither its piperidine nor its phenyls. Three measured reasons:

* The nested prefix subtree DOES carry a numbering, and it is FRAGMENT-LOCAL.
  Measured on acetyl fentanyl, the piperidinyl subtree numbers its own atoms
  `{13: 1, 9: 2, 6: 3, 5: 4, 7: 5, 10: 6}` - indices of the carved fragment,
  not of the molecule.
* The tree exposes NO fragment-to-parent map. `named_parent.candidate` carries
  fragment-local indices too, and no node holds the carved mol, so the mapping
  would have to be re-derived by inference.
* The curated ring table cannot fill the gap: 302 of its 371 entries carry an
  `atom_locants` map, and PIPERIDINE and BENZENE are not among them
  (pyrrolidine has no entry keyed by its ring SMILES at all). For benzene a
  skeleton numbering would be arbitrary anyway - every position is equivalent
  until a substituent breaks the tie.

Fixing it properly means having `carve_substituent` return its
fragment-to-parent map alongside the fragment, which is a change to the
extraction layer's contract. Inferring it instead is how a numbering ends up
confident and wrong.

Indole is a smaller instance of the same shape: its table entry numbers 7 of
its 9 ring atoms, so 3a and 7a are missing. That one is a data gap in
`atom_locants` rather than an algorithm.

## An indicated hydrogen dropped from a substituent name (CLOSED in round 4, D-040)

Fixed with the carbazole numbering (an `[nH]` pins the tautomer, not the
orientation): the example below now names `4-(1H-indol-2-yl)benzoic acid`.


`OC(=O)c1ccc(cc1)c1cc2ccccc2[nH]1` is named `4-(indol-2-yl)benzoic acid`,
where the PIN carries the indicated hydrogen: `4-(1H-indol-2-yl)benzoic acid`.
Severity B - OPSIN resolves a bare `indol-2-yl` to the 1H form, so the name
round-trips and denotes the right molecule. The N-substituted case is already
correct (`4-(1-methyl-1H-indol-2-yl)benzoic acid`), which places the gap in
the unsubstituted-N path rather than in the indicated-hydrogen machinery.
Found while fixing D-029; it predates it.

## Open after P-45.2.3 (2026-10-06)

P-45.2.3, "the lower locant set for substituent groups in order of citation in the name" (BlueBookV2.pdf p. 419), is applied ACROSS parent structures that tie on the preference key (`engine._senior_by_citation_locants`, called from `_break_parent_tie`), where it used to be plan order and so the order the SMILES atoms were written in. The book prints fifteen examples (pp. 420-422); fourteen are decided by it (1 to 12, 14, 15; 6 and 9 only since P-44.4.1.1: the book's name on 13 of 13 spellings, from 4 to 10 of 13 before for the ten that could be named then, and 11 and 12 only since D-191 and D-192 made the engine name a `[PH4]` group with its lambda number and a labelled bromine with its label), 13 was already the book's name on every spelling (the book frames it as a choice between two numberings of one chain),  The engine writes `lambda5` where the book prints the glyph. It reaches achiral molecules; `CHANGELOG.md`, 2026-10-06, has the table and the census. What is left, each measured:

* **P-44.4.1.1 is implemented (naming round 27, 2026-10-07): the principal chain has the greater number of multiple bonds.** `strategy._parent_selection_score` counts the bonds the unsaturation infixes name; P-45.2.3 examples 6 and 9 are the book's name on 13 of 13 spellings (`vendor/CHANGELOG.md`, 2026-10-07, has the census, panel and sweep numbers). **P-44.4.1.2 (the greater number of DOUBLE bonds, `hepta-1,6-diene` before `hept-1-en-6-yne`, p. 402) is not:** `C=CCCC(CCC=C)CCC#C` is three names over 12 spellings (`5-(but-3-yn-1-yl)nona-1,8-diene` is the book's), all reading back exact, pinned as a strict xfail in `tests/test_namer_multiple_bonds_parent.py`. P-44.4.1.3 to P-44.4.1.11 (nonstandard bonding numbers across parents, indicated hydrogen, ...) were not examined.
* **P-45.5 is implemented (naming round 27, 2026-10-07): of parents that tie on P-45.2.3, the name earlier in alphanumerical order (`bromo` before `dibromo`).** `engine._senior_by_alphanumerical_order` compares `_alphanumerical_letters`: the finished name's letters in order, with locants, descriptors, element symbols, fusion descriptors and hydro/dehydro prefixes (not alphabetized, pdf p. 75) removed. The book's examples 1, 2 and 4 are its name on 13 of 13 spellings (7, 7 and 10 of 13 before); the numerical-locants half of the rule needs nothing, since P-45.2.3 has made them equal. **Not covered:** example 3 is a cyclophane the engine does not name. Example 5 carries nuclides: it was two names while the rule declined a name with a nuclide, and P-45.3 and P-45.4 are applied since round 29, so it is the book's name now; the rule still declines a name with a BONDING number (how the book alphabetizes the lambda is not stated) or an embedded `NAMING ERROR`.
* **Two parents are compared only when they have the same name once prefixes and descriptors are set aside, and at most twelve DISTINCT hypotheses are named.** The preference key does not hold every criterion that tells two different parents apart, and a lower locant must not stand in for one (the guard `_choose_by_configuration` already had for P-45.6); a molecule with more than `_PARENT_TIE_HYPOTHESES` (12, since #235; hypotheses `_plan_identity` shows to name the molecule identically count once) tied parent choices is left to plan order as before. Over the 2000 census rows the rule was reached on 176 calls (at every recursion depth) and every one was the same parent, so the guard has never declined on that population, and what happens when it does is tested only on made-up trees.
* **P-45.2.3 reads the prefixes' locants with the descriptors set aside (`assembly.descriptors_set_aside`), as the book does ("ignoring the configuration symbols", P-45.6.2, p. 426).** It did not at first, and the two features did not compose: read with their descriptors, the arms of a quaternary carbon merged differently (`4,4-bis[...]` against `4-[...]-4-[...]`), the flattened locants of P-92.5.2.2 example 5's four parent choices were `4,4,6,6` and `4,6,4,6`, and the rule ruled two of the four out before the configuration comparison, which is the one that should choose (found by #235's `test_nine_chains_are_four_choices` reading 2 where it expects 4; the name was still the book's on 40 of 40 spellings, by that artefact). Fixed, and pinned by `test_p_45_2_3_cannot_tell_the_four_choices_apart`. The book's own order is P-45.2.3, then P-45.3 to P-45.5, then P-45.6, and this engine's agrees for P-45.2.3, P-45.5 and P-45.6 (P-45.5 since round 27, and it runs between the other two); P-45.3 and P-45.4 are applied between them since round 29, so all four agree.

## Open after D-191 and D-192 (2026-10-06)

D-191 (a group past its standard bonding number lost its lambda number) and D-192 (a nuclide on a one-atom prefix was dropped) are closed in `CHANGELOG.md`, 2026-10-06. What they leave open, each measured on the tree that closes them (OPSIN read-back; every target below is read back to its input on canonical SMILES and InChIKey):

* **D-193 (a nuclide the name dropped, wrong molecule) is closed, and what it was is now a refusal (naming round 28, 2026-10-07).** The cause was general, not four cases: `collect_isotope_labels` dropped a label for any atom it could not locate ("drop the label rather than emit a guess") and every route that builds a name from parts of the molecule (a retained parent that numbers nothing, a multi-atom prefix, an ether oxygen, the hypohalous-amide route, a hydroxy or amino prefix) could do the same, so each read back as the UNLABELLED compound. `engine._check_nuclides_named` now refuses any name that cites fewer atoms of a nuclide than the molecule has (`_nuclides_named` reads the isotope brackets, multiplied by the multiplier that encloses them: `1,2-di[(81Br)bromo]ethane` is two atoms), and the routes that can label their atoms do: `(15N)aniline`, `(18O)phenol`, `(15N)benzonitrile`, `(15N)cyanoacetic acid`, `3-[(81Br)bromocarbonyl]propanoic acid`, `(18O)methoxyacetic acid`, `dimethyl(81Br)hypobromous amide`, `3-[(O-2H)hydroxy]propanoic acid`, `3-[(N-2H)amino]propanoic acid`. A bare symbol is used only when the element is ALONE in the group it modifies (P-82.6.1.2): `(13C)benzonitrile` is refused because OPSIN calls it ambiguous among seven carbons, and so are two nitrogens of one retained name, an `[18O-][N+](=O)` nitro oxygen, `CN([2H])CCC(=O)O` and `[2H]N([2H])c1ccccc1`. The application shows a refusal as a `NamingError`. Measured on 400 census molecules with one atom labelled (13C, 15N, 18O, or a deuterium on a heteroatom; fixed seed): master 89 exact, 86 WRONG MOLECULE, 205 OPSIN-unreadable, 20 naming errors; now 290 exact, 2 wrong, 40 unreadable, 20 naming errors and 48 refusals, with no name that was exact before changed; the census (2000 rows) moves 0. **What is still wrong in that sample:** the two are a label's locant on a bridged or polycyclic retained parent (a morphinan, a tetracyclo ring), where the engine's numbering is not OPSIN's and the label now lands on another atom (the same locant was invisible before because the name was unreadable); the application's read-back withholds such a name. A third, an ether prefix with two oxygens, was fixed by requiring the element to be alone. The 40 unreadable are right-molecule names in placements OPSIN cannot read (an amide or ester carbonyl label, `(1-15N)propanamide`, a label inside a hydro-named heterocycle), not changed in this round.
* **P-45.3 and P-45.4 are applied across parents (naming round 29, 2026-10-08); D-194c is closed.** `engine._senior_by_substituent_modification` compares one key in the book's order, between P-45.2.3 and P-45.5: P-45.3.1 the maximum number of prefixes directly bonded through an atom of nonstandard bonding number (then the higher number first, `lambda6` before `lambda4`), P-45.3.2 their lower locants, P-45.4.1 the lowest locants of the isotopically modified prefixes (a nuclide anywhere in the prefix), P-45.4.2 those holding the nuclide of higher atomic number, P-45.4.3 of higher mass number. D-194c's ether `2-bromo-1-{[2-(81Br)bromopentyl]oxy}pentane` was 24 and 16 of 40 spellings and is one name; the book's other examples were 7 and 6 of 13 (P-45.3.1 example 1, example 3 and P-45.4.1), and 8 and 5 and 11 and 2 THE WRONG WAY ROUND for P-45.4.2 and P-45.4.3; each is one name over 16 spellings now, and P-45.5's example 5, which carries nuclides, is the book's name on all 16 (9 and 4 of 13 before). **Not covered:** P-45.3.1 example 2 and P-45.3.2 (`2lambda5-diphosphan-1-yl`) are not reached because the engine drops the lambda number of a MULTI-atom group (`4-diphosphanyl-2-(2-diphosphanylethyl)butanenitrile` for the book's `4-(2lambda5-diphosphan-1-yl)-...`), a defect of its own that the rule cannot show. **Read as text:** a prefix is 'directly bonded through a hypervalent atom' when its leaf text, or its tree's own parent name, starts with `lambdaN-`; and a prefix is 'isotopically modified' when its assembled name cites a nuclide, so a form the engine spells differently from the book is compared on the engine's spelling.
* **D-195 is closed (naming round 28): a hypervalent centre with NO hydrogen and only single bonds takes its lambda number.** `CP(C)(C)(C)C` is `pentamethyl-lambda5-phosphane`, `COP(OC)(OC)(OC)OC` the book's `pentamethoxy-lambda5-phosphane (PIN)` (p. 770), `pentaphenyl-lambda5-phosphane` and `pentamethyl-lambda5-arsane`, and as a substituent `(tetramethyl-lambda5-phosphanyl)acetic acid`. A centre with a double bond (`trimethyl-lambda5-phosphanone`) already said its number, and a sulfur or halogen centre (`(pentamethylsulfanyl)methane`, `FS(F)(F)(F)(F)F`) goes through other routes and is unchanged.
* **Isotopic label placement and labelled rings (naming round 29, phase 2, 2026-10-08).** Of the 40 names OPSIN could not read after round 28, 35 were the label's PLACEMENT (the name with the bracket removed read fine), and a fifth cause sat under them: a nuclide anywhere in a ring made the ring unrecognisable (`ring_naming.common._nuclide_free` now looks a ring up without its nuclides), so labelled benzene was `cyclohexa-1,3,5-triene`, labelled pyridine `azine`, labelled naphthalene a naming error and labelled tetralin a `bicyclo[4.4.0]` name for ANOTHER molecule. The placements: a suffix whose locant is left out is written with it, `butan-1-(18O)amide`, `propan-1-(18O)al`, `propane-1-(15N)nitrile` (a retained name keeps the bare label after the prefixes, `2-chloro-N-phenyl(15N)acetamide`); the bracket follows the hydro prefixes, `3,4-dihydro(4-13C)quinolin-1(2H)-yl`, `2,3-dihydro(1-15N)-1H-indole`; it goes before the `amino` it modifies, `3-[benzoyl(N-2H)amino]propanoic acid`; and before the `oxy` of a compound alkoxy on the uncontracted form, `[(phenylmethyl)(18O)oxy]`. Each form is the one OPSIN reads (tested against its rivals). Measured on the same 400 labelled census molecules (round 28 -> now): exact 290 -> 331, OPSIN-unreadable 40 -> 10, naming errors 20 -> 8, wrong molecule 2 -> 2 (one fixed, one new), refused 48 -> 49, nothing exact regressed; census 0 moved. **Still unreadable (10):** the two oxygens of an ester or acid component (below), a label among two suffix groups (`heptane-2,4-dione`), an N-substituted piperidinyl whose ring nitrogen is also the attachment atom, and a label on a ring with a prefix before `(1-13C)phenyl`. **The two wrong molecules** are a label's locant on a retained or hydro-named ring where the engine's numbering is not OPSIN's: the morphinan (`4,5-epoxy...(4-13C)morphinan-6-one`) and a deuterium on the ring nitrogen of a hydro-purinone (`(9-2H)-5,9-dihydro-2H-purin-6-one`); the second was hidden while its name was unreadable. **D-197, found and NOT fixed:** the carbonyl and the alkoxy oxygen of an ester are one name, `methyl (1-18O)acetate`, for two different molecules, and OPSIN reads neither; pinned open in `tests/test_namer_known_defects.py` with the forms OPSIN does read for each (`-1-(18O)oate`, `-1-(O-18O)oate`), whose agreement with the book is not known. **Corrected in naming round 30 (next entry): D-197 is closed, and two of the diagnoses above were wrong (the morphinan is exact when compared without stereo; the hydro-purinone's label is right and its unlabelled name is the defect).**
* **Carboxyl oxygens, a ketone's neighbours, and a nuclide in a fused ring (naming round 30, 2026-10-08; D-197, D-200, D-201, D-202).** D-197 is closed: the carbonyl and the hydroxyl oxygen of an acid (the latter is also an ester's alkoxy oxygen) are two names, `methyl (18O)acetate` and `methyl (O-18O)acetate`, `methyl prop-2-en-1-(18O)oate` and `methyl prop-2-en-1-(O-18O)oate`, `(18O)acetic acid` and `(O-18O)acetic acid`, each read back exact. D-200 was a WRONG MOLECULE: a ketone's group lists its two neighbours, so the ring nitrogen of `CC(=O)[15N]1CCCCC1` was cited by the ring AND by `-one` (`ethan-1-(15N)one`); only what is double-bonded to the anchor is the suffix's now. D-201: `prop-2-en-1-(18O)amide`, the infix's e before a vowel with the bracket between. D-202: a nuclide in a fused, bridged or spiro ring made the ring a naming error or a von Baeyer name; `ring_naming.name_ring_system` looks every ring up without its nuclides. 300 census molecules with one ring nitrogen labelled, master -> now: exact 269 -> 295, unreadable 16 -> 2, naming errors 11 -> 0, wrong molecule 3 -> 2; the 400 labelled molecules of rounds 28 and 29: exact 331 -> 348, unreadable 10 -> 3, naming errors 8 -> 0; census (2000) and panel (1712) 0 moved. **Still open, found here:** (1) a label on ONE oxygen of a multiplied suffix (`(2-18O)hexane-2,4-dione`) has no form OPSIN reads (only the unconventional `hexane-2-(18O)one-4-one`), so there is no target to pin; (2) the hydro-purinone `[2H]N1C(SC)=NC2C(=O)N=CN=C21` is named `8-(methylsulfanyl)-5,9-dihydro(9-2H)-2H-purin-6-one` and its UNLABELLED name `...-5,9-dihydro-2H-purin-6-one` is already another molecule (OPSIN reads `...-5,9-dihydro-6H-purin-6-one` as the structure): the indicated hydrogen is put at 2, not at the oxo carbon 6; three more unlabelled names OPSIN cannot read turned up (a 6-azauridine, a pentacyclo imide, a bis-dioxolopyran), each its own shape; (3) the morphinan label was never wrong: OPSIN reads a morphinan name WITH stereo the input lacks, so a sweep must compare without stereo for these. The wrong diagnosis `azin-3-yl` was only a labelled pyridine before round 29's ring fix. **Update (naming round 31): item (2), the hydro-purinone's indicated hydrogen, is closed as D-203 (next entry).**
* **The indicated hydrogen of a hydro-named ring ketone (naming round 31, 2026-10-08; D-203).** `8-(methylsulfanyl)-5,9-dihydro-2H-purin-6-one` was another molecule (OPSIN reads a CH2 at C2); it is `...-5,9-dihydro-6H-purin-6-one`. The retained lookup writes the curated parent's DEFAULT indicated hydrogen into its text, and `indicated_hydrogen_p58._resolve` declined the planner's correct answer because that placeholder was not among the atoms the plan described; it now ignores the old indicated labels and still requires the hydro positions to agree. Seven purin-6-one tautomers were wrong, all exact now; census 2 names moved (both mismatch_formula -> exact), panel 0. **Still open, found here:** enol and imidol tautomers (`C(O)=N`, `C(=C(O)O)`) of ring systems are named as hydroxy/azinane parents that OPSIN reads as another molecule or cannot read: 5 wrong and 4 unreadable of 178 odd tautomers, each its own shape and none this defect.
* **A benzo-fused bridged ring system with a ring heteroatom (naming round 32, 2026-10-08; D-204).** `benzo_fused_bridged` names a CARBOCYCLE (`5,9-methanobenzocycloocten-7-one`) and never read an element, so the O and N of a 2,6-methano-1,3-benzoxazocin-4-one were dropped: a different molecule, both census rows of the shape. It declines a system with a ring O, N or S now and the generic bridged path names it (`8-oxa-10-azatricyclo[7.3.1.0^{2,7}]trideca-2,4,6-trien-11-one`, exact). 114 heteroatom variants, wrong 89 -> 0. **Still open:** the PREFERRED name is the fusion-bridged one (P-25.4, `2,6-methano-1,3-benzoxazocine`), not built; and the carbocycle names this module writes carry odd hydro multipliers (`5,6,7,8,9-pentahydro-5,9-methanobenzocycloheptene`) that OPSIN reads but P-31.1.4.2.4 does not allow.
* **The cation of a fused ring system, and a ring fused on purine (naming round 33, 2026-10-09; D-205, D-206).** A protonated fused heteroaromatic (`c1c[n+]2c([nH]1)[nH]c1ccccc12`) was a `NAMING ERROR` because no table holds its cation; a ring system with nothing to offer that has an aromatic nitrogen cation is retried on its neutral twin (`ring_naming._neutral_twin`), and the `-ium` is rendered from the full molecule. D-206: a ring fused on purine was lettered by sorting purine's locants, but its periphery runs 1,2,3,4,9,8,7,5,6, so N7-C8 is `f`, not `g` (`imidazo[2,1-f]purine`, not `imidazo[1,2-g]purine`); `fusion_general._periphery_order` walks the periphery now. 32 purine-fused systems exact 21 -> 32; 300 protonated fused heteroaromatics: naming errors 8 -> 0; census 3 rows `NAMING ERROR` -> exact. **Still open, found here:** (1) the cation is LOST for protonated 2-amidothiazoles, tetrahydrobenzothiazoles and pyrazolo[1,5-a]pyrimidines (9 of 300 protonated molecules are still wrong); (2) a NON-aromatic cation (`C1C[N+]2=C(CCCCC2)NC1`, a bicyclic amidinium) is a visible `NAMING ERROR`, and `C[N+]1=C(C)NCC1` is named `2,3-dimethyl-1,3-diazol-3-ium` without its hydro prefixes (a different molecule); (3) 5 census rows are still `NAMING ERROR`: two neutral tetracyclic fused systems (`Cc1nn(-c2ccccc2)c2c1cc1c(=O)n(C)c(=O)nc-1n2-c1ccccc1F`, `C=CCn1cnc2c(c1=O)c1nc3ccccc3nc1n2CCC1=CCCCC1`), the amidinium, and two spiro-oxindole pyrano[2,3-c]pyrazoles; (4) three `sulfonamidate` census rows are OPSIN reading a correct anion name as the neutral sulfonamide, not an engine defect.
* **A partly saturated ring cation (naming round 34, 2026-10-09; D-207).** A cyclic iminium or amidinium lost its hydro prefixes and named the aromatic or the saturated ring (`2,3-dimethyl-1,3-diazol-3-ium` for `C[N+]1=C(C)NCC1`): `monocyclic._collect_hydro_locants` and `retained_lookup._try_derive_hydro_retained` refused a ring at its first charged atom, before asking whether it was in the double bond. 1151 such cations: wrong molecule 1005 -> 0. **Still open, found here:** the names are exact but use the Hantzsch-Widman parent (`3,4-dihydro-2H-azol-1-ium`, `4,5-dihydro-1H-1,3-diazol-3-ium`) where the neutral ring takes the retained one (`pyrrole`, `imidazole`); a ring cation with an exocyclic double bond on a ring carbon (`C=C1CCC[NH+]=C1`) is `5-methylideneazinan-1-ium`, a different molecule.
* **A ring cation on a curated fused parent (naming round 35, 2026-10-09; D-208).** Six curated ring tables listed no locant for their heteroatoms, so the `-ium` had no place and the cation was named as the NEUTRAL parent (`2-methyl-4,5,6,7-tetrahydro-1,3-benzothiazole`); the tables are complete and a cationic ring atom with no locant now fails its plan. 700 cations: wrong molecule 528 -> 0. **Still open:** thirteen more curated entries (octahydro-oxazolo-pyrrolo-pyrazine, hexahydropyrido[2,1-a]isoquinoline and kin, 1,2-benzodithiete, ...) list no locant for a ring heteroatom; their cations are named by the next plan (a von Baeyer name where one exists) rather than by the retained parent.
* **D-196 is closed (naming round 28): the parent's nuclide is cited before the part it modifies.** `[13CH3]CCCBr` is `1-bromo(4-13C)butane` and `4-chloro(15N)aniline` (the bracket goes after the prefixes, before the parent name, with a hyphen only where a locant follows); a nuclide on the heteroatom of a suffix group is cited before the suffix word, `1-phenylethan-1-(18O)one` (P-82.2.1, p. 853), when the parent is systematic and the suffix carries a locant. **Still at the front of the name**, as before and OPSIN-unreadable: a suffix with no locant to follow (`(1-18O)ethanol`, `(1-18O)acetaldehyde`, `(1-18O)acetic acid`, where the book prints no place and OPSIN has not been shown to read one). The hypohalous amide and ether routes are listed with D-193 above.
* **A sulfine, `C=S=O`, is a visible naming error before and after** (`[NAMING ERROR: Substitutive plan for parent 'methane' leaves heavy atoms [2] unclaimed]` on the base, `{[NAMING ERROR: No valid naming plan found for O=[SH2]]}methane` now: the group is carved as `=S(=O)` and no plan names it). The application refuses a name that embeds the error.
* **Where the numbering key is shadowed.** `_alphanumerical_locant_key` orders prefixes by `(sort name, isotope key, stereo key, name)`, so as to agree with the order assembly prints them in. The isotope key is shadowed there by the last element: a labelled prefix's name starts with `(` or `[`, which sorts before a letter, so removing the key changed no test (mutant M19 of the matrix in the changelog survived). It is kept so that the numbering criterion cannot disagree with the printed order if a label ever sits later in a name.

## Open after P-14.4 (j) and "R precedes S" elsewhere (2026-10-06)

P-14.4 (j) decides between numberings of ONE parent (`_break_alphanumerical_tie`), which includes the `-diyl` group of a polyol's diester since naming round 26. Three more choices that used to go by atom order are decided now (`CHANGELOG.md`, 2026-10-06, "R precedes S beyond the numbering"): the order two prefixes that differ only in their descriptors are cited in (P-45.6.3), which half of a meso diether or diamide is the parent (P-45.6.2, and like before unlike for a parent that carries two R/S descriptors, P-44.4.1.12.2), and the principal ester of a diester on the acyloxy form (the ester-route tier, back once the session cache was fixed). What is left, each measured:

* **P-45.2.3 is implemented (2026-10-06): see "Open after P-45.2.3" below.** This entry said it was not, and that P-45.6.2 example 3's second name was this gap and not a stereo one; both are settled: `1,2-bis[(1S)-1-chloroethyl]-4-{3-[(1R)-1-chloroethyl]-4-[(1S)-1-chloroethyl]phenoxy}benzene` is now the name on every spelling (`tests/test_namer_parent_citation_locants.py`).
* **P-92.5.2.2 example 5's structure is one name now, and the earlier note about it was wrong in what it concluded** (naming round 26 follow-up, `CHANGELOG.md`, 2026-10-06, "one stereoisomer, one name"). `C[C@H](Cl)[C@@H](C)[C@@]([C@H](O)[C@@]([C@H](C)[C@@H](C)Cl)([C@H](C)[C@@H](C)Cl)[C@@H](C)[C@@H](C)Cl)([C@H](C)[C@H](C)Cl)[C@@H](C)[C@@H](C)Cl`, built from the book's descriptors with RDKit's CIP labeler (OPSIN cannot read the book's name: "Failed to assign CIP stereochemistry"), has 13 stereogenic centres and NINE chains that tie on every criterion of the preference key. It was 8 names over 10 spellings on `66f112ed`, 16 over 30 with the session-cache fix, 4 over 30 with the "R precedes S" follow-up, and is 1 over 40 now, the book's. An earlier note here said "at most one set describes it" and "most are wrong": that held only before the cache fix, which was a real wrong-compound defect (a (2R,3R) arm printed (2S,3R)). Once it was fixed every one of the 16 names was RDKit's label for the atom it describes, per atom, parent and prefixes: sixteen correct names of one molecule, each on a different chain. The defect was the CHOICE of chain, which `_break_parent_stereo_tie` made only for up to four tied parents (there are nine, of which four differ) and only for names that were equal "once the descriptors are set aside" in the finished text (which they are not, because the descriptors decide how prefixes merge). Examples 1 to 3 of the same section were never affected. `tests/test_namer_stereo_parent_choice.py` pins the book's molecule and eight more stereoisomers of its skeleton, each over random spellings, each descriptor checked per atom against RDKit.
* **Like and unlike are judged only for a parent that carries exactly two R/S descriptors.** For three or more the book pairs each centre with a reference descriptor chosen from the digraph (P-92.5.2.1, Mata and Lobo), which a finished name does not hold, so such a parent is compared on E/Z, r over s and R over S, and then on the whole name (`_parent_configuration_key`, `stereo_citation_key`). The one example the book prints for the numbering consequence, P-92.5.2.2 example 5 (p. 900), has a caption ("lowest locants are assigned to the like pair") that its own printed name contradicts: the unlike pair `(2S,3R)` is at the lower locant 4 and the like pair `(2S,3S)` at 6, which is what R-first citation (P-45.6.3) gives. Numbering is criterion (j), R before S; like before unlike is the rule for choosing between PARENT STRUCTURES (P-44.4.1.12.2, p. 413) and is applied there. An earlier note here said like pairs were not implemented and that no output told them apart; the ether `CC(Cl)C(C)OC(C)C(C)Cl` (halves (2S,3R) and (2S,3S)) is the output that does, and is now named on the like half.
* **M and P are not ranked in a prefix's citation order.** `stereo_citation_key` reads the letters assembly's descriptor pattern reads (R, S, E, Z, r, s); a helical descriptor inside a prefix is neither ranked nor stripped from the sort name, and the engine writes none there today.
* **The ester tier compares the alcohol component's own descriptors only.** Descriptors inside that component's substituents are ordered by the citation rule inside its tree. Every stereoisomer of six skeletons that were not tuned on (dipropylene and tripropylene glycol diacetate, the dibenzoate, a tartrate diacetate, hexane-2,5-diyl and hydrobenzoin diacetates) is one name over its spellings and reads back through OPSIN, which is what the tier was removed for failing.
* **The units' locants are compared before their descriptors** (`(2S)-butane-2,3-diol` for a single specified centre, never `(3S)`). That is this change's reading of "lower locants related to the presence of stereogenic centers" in criterion (j), supported by the note under P-92.5.1 (pdf p. 895) that the numbering of the principal chain "is based on lowest locants for stereogenic centers"; the book prints no example in which the two orders of comparison disagree.


## Open after the stereo cache fix (2026-10-06)

The naming session's cache no longer answers for two substituents that differ only in an inherited R/S descriptor (`CHANGELOG.md`, 2026-10-06). It leaves these, each measured on the tree before and after and found identical:

* **Prefixes that tie on their letters ALONE are cited in atom order (P-14.5.4).** "When two or more prefixes consist of identical Roman letters, priority for order of citation is given to the group that contains the lowest locant(s) at the first point of difference" (BlueBookV2.pdf p. 82). `derive_sort_name` strips locants and stereodescriptors, and the sort that cites the prefixes is stable on it, so prefixes that tie on their letters keep the order the atoms were written in. The book's own `1-(pentan-2-yl)-4-(pentan-3-yl)benzene` is that name in 20 of 40 random spellings and `4-(pentan-3-yl)-1-(pentan-2-yl)benzene` in the other 20 (no stereo there, so neither the cache key nor the rule below is involved). **The stereo half of this was closed the same day** (`CHANGELOG.md`, 2026-10-06, "R precedes S beyond the numbering"): prefixes that differ only in their descriptors are cited R before S and Z before E (P-45.6.3, p. 427), so the R,S di-sec-butylbenzene is `1-[(2R)-butan-2-yl]-3-[(2S)-butan-2-yl]benzene` in every spelling (it was that or `3-[(2S)-...]-1-[(2R)-...]benzene`, 63 and 57 of 120, once the cache key made it the right molecule), and the E,Z-propenyl pair on a 1,3-phenylene is `1-[(1Z)-prop-1-en-1-yl]-3-[(1E)-prop-1-en-1-yl]benzene` (it was cited either way, 31 and 29 of 60, with E on locant 1 in every spelling, against criterion (j)).
* **A name OPSIN cannot read is checked by CIP, not by read-back.** `CC[C@H](C)[C@H]1CC[C@@H]([C@H](C)CC)CC1` (side chains R and S) was `(1R,4S)-1,4-bis[(2S)-butan-2-yl]cyclohexane`, the same defect, and is now `(1R,4S)-1-[(2R)-butan-2-yl]-4-[(2S)-butan-2-yl]cyclohexane`, each ring centre paired with the side chain RDKit's CIP gives it. OPSIN reads neither (`Could not find atom that: <stereoChemistry locant="1" ...>`), so the sweep that found the rest cannot confirm this one; a name that parses back is not the only way a name can be right, and one that does not parse is not therefore wrong.


## Open after naming round 26 (2026-10-06; D-187 to D-190 closed in round 26 above)

* **Different anions on one polyol keep the accepted (acyloxy) name, not the PIN.** P-65.6.3.3.3.2 method (1) prints `propane-1,2,3-triyl 1,2-diacetate 3-propanoate (PIN)`, `1,4-phenylene acetate dichloroacetate (PIN)` and `methylene acetate formate (PIN)`; the book's five examples and every variant tried (with and without locants, `methanediyl`) are UNPARSEABLE to OPSIN (measured 2026-10-06), so a name built here could not be checked by the one reader this project trusts. They stay on method (2), `2,3-bis(acetyloxy)propyl propanoate`, which OPSIN confirms. Reopen if OPSIN reads the form or another reader is wired in.
* **A polyol whose organyl group is not one parent keeps the acyloxy name.** `_organyl_cites_valences` declines a group the generic path cannot write as one n-valent group: a multiplicative group (`1,2-phenylenedi(propan-3,1-yl)`, `1,4-phenylenebis(methylene)`, `oxydi(ethane-2,1-diyl)`: diethylene glycol diacetate), a ring assembly (`[1,1'-biphenyl]-4,4'-diyl`, bisphenol A diacetate) and valences on a branched skeleton (pentaerythritol: four valences on four carbons). The book prints PINs for all of them; none is built. The first version of the generic path wrote the first of these as `3-(2-propylphenyl)propane-1-diyl`, one locant for two valences, a different molecule: that is what the guard is for.
* **Esters of a polyol AND a polyacid** (P-65.6.3.3.4.1, `dimethyl ethane-1,2-diyl dibutanedioate (PIN)`) are not built; the name is unchanged and OPSIN reads it.
* **A meso group's descriptor set was chosen by atom order.** CLOSED 2026-10-06 (see CHANGELOG.md): P-14.4 (j), not P-31.1.4.3.4 as this entry first cited, puts the preferred descriptor (R before S) at the first point of difference, and it is the last criterion of `_break_alphanumerical_tie`. `(2R,3S)-butane-2,3-diyl diacetate`, `(1R,2S)-cyclohexane-1,2-diyl diacetate`, `(2R,3S)-butane-2,3-diol` and tropine's `(1R,5S)` are each one name in 24 of 24 spellings. The tie-break in `_break_ester_tie` (which ester carries the suffix) is a different tie and is not changed. What stays open for the tie-break is in the section "Open after P-14.4 (j)" above.
* **The free-valence SET rule (D-190) covers chain and ring parents only.** A heteroatom-chain parent (hydrazine, disulfane) with two valences still reads the first attachment alone.

## Open after naming round 25 (2026-10-05; D-183 to D-186 closed in round 25 above)

* **Polyesters are written in the accepted (acyloxy) form, never the PIN.** CLOSED in round 26 for the esters of one polyol with one acid (D-187: `ethane-1,2-diyl diacetate`, heroin `...morphinan-3,6-diyl diacetate`); what is left of it is the first three bullets of the round 26 section above.
* **"Senior acid" is ring-before-chain, then skeletal atoms, then substituents** on the executed acid component, not the full P-41/P-44.1 order (class, then the rest). With more than four tied esters, or a retained acid other than formate/acetate/benzoate, or a leaf-named alcohol, the choice falls to a canonical atom rank: stable, but not a rule. Where two esters have the same acid and the alcohols compare equal on locants (two benzoates, two acrylates) the book prints no further criterion this engine implements; the name is stable but its choice among valid names is arbitrary.
* **Tropine and pseudotropine have one name.** The C3 centre is pseudoasymmetric (`3r`/`3s`), OPSIN cannot read it, so it is dropped with a note. Keeping it would give the correct name but one the parser cannot verify.
* **A tie between von Baeyer numberings is now broken by the principal group and the prefixes. The three ties listed here as still open were closed 2026-10-06 (see CHANGELOG.md): (1) by P-14.4 (j), (2) by numbering every tied decomposition with the superscripts before the heteroatoms (P-23.2.6.2, P-23.3), (3) by ranking the fewest compound locants first (P-31.1.4.2). What stays open is in the last paragraph of that entry: dependent secondary bridges cannot be enumerated, a benzene ring in a von Baeyer system is named from the Kekule form the input carries, and the pinned-heteroatom path ranks an ene above a suffix.** The tropane carboxylic acid that was `-2-` or `-4-` by spelling (`3-hydroxy-8-methyl-8-azabicyclo[3.2.1]octane-2-carboxylic acid`) is `-2-` in every spelling, with or without stereo, and cocaine with it: `name_bridged` pinned one numbering and the strategy layer could not choose between the two mirror numberings (see CHANGELOG.md, 2026-10-06). Were open: (1) numberings that tie on every locant criterion (a meso skeleton: tropine, `4-azatricyclo[5.2.1.0^{2,6}]dec-8-ene-3,5-dione` imides) are a coin flip between `(1R,5S)` and `(1S,5R)`, because the numbering score has no stereo-descriptor tier; CIP R before S at the first point of difference is not implemented, and it agrees with what round 25 pins for atropine and scopolamine. (2) Tricyclic and larger cages are numbered from the first of the tied decompositions only, so a 2-azaadamantane acid is `2-aza`, `9-aza` or `10-aza` by spelling. (3) The unsaturation tier ranks a bond by its lower locant, so `non-1-ene` and `non-1(8)-ene` tie.
* The four natural products of round 24 are no longer open: atropine and scopolamine keep every centre OPSIN reads; galantamine and ibogaine are exact.

## Open after naming round 24 (2026-10-05; D-180, D-181, D-182 closed in round 24 above)

* **Four of 45 complex natural products still lose stereo in the app:** atropine and scopolamine (tropane parents), galantamine (`benzofuro[3a,3,2-ef][2]benzazepine`) and ibogaine (a methano-bridged fused system). Not diagnosed this round: the name is right about connectivity and the engine's own stereo check leaves the descriptors out. Read `_validate_stereo_via_opsin` first.
* **Charged morphinans** (quaternary N-methyl) fall back to a von Baeyer name: `retained_modified` refuses a formally charged ring atom.
* **Only morphinan is eligible for `didehydro`/`epoxy` modification.** Other retained natural-product parents (ergoline, ibogamine, the Amaryllidaceae scaffolds) are not in `_MODIFIABLE`; add one only where the book prints such a name.
* **Which ester carries the suffix depends on input atom order.** For a molecule with two equivalent ester groups (heroin; also `CC(=O)OC1CCC(OC(C)=O)CC1C`), randomised SMILES of the same structure give two names, `...-3-yl acetate` with `6-(acetyloxy)` and the reverse. Both read back to the structure, so neither is wrong about the molecule, but the lower-locant suffix is the expected one and the tie-break is accidental. Found while porting round 24; present before it (the non-morphinan control shows it too), not investigated.
* **The battery was not run on the frozen sets as a population.** It is a 45-molecule drug panel chosen by hand, so it measures the cluster, not a rate.

## Open after naming round 23 (2026-09-27)

D-179 (the chalcogen analogue thiohydrazide) is fixed; see `CHANGELOG.md`, round 23. Still open (unchanged from round 22).

## Open after naming round 22 (2026-09-27; D-179 closed in round 23 above)

D-171 (hydrazones of a carbon-acid hydrazide) is fixed; see `CHANGELOG.md`, round 22. Still open:

* **Plain thiohydrazides** (`CC(=S)NN` is `(1-thioxoethyl)hydrazine`, not `acetothiohydrazide`): the `fg:hydrazide` SMARTS matches only a carbonyl oxygen; no
  chalcogen-generic path exists for it, unlike carboxamide/carbothioamide.

## Open after naming round 21 (2026-09-27; D-171 closed in round 22 above)

D-173 (retained `benzylidene`/`benzylidyne`) and D-178 (halogen-oxoacid amides) are fixed; see `CHANGELOG.md`, round 21. Still open, all investigated this round:

* **Hydrazones of carbon-acid hydrazides** (`CC(=O)NN=CCCCCC` is `1-acetyl-2-hexylidenehydrazine`; P-66.3.3 names the hydrazide,
  `N'-hexylideneacetohydrazide`): the FG SMARTS (`fg:hydrazide`) requires both nitrogens at `NX3`, which a hydrazone's terminal `=N-` fails, and the fix
  touches the general FG-suffix rendering pipeline broadly enough that a self-contained one was not found.
* **An azine, a triazane or a ring nitrogen on the second nitrogen of an `=N-N` group** keeps the imino form; no book names were found for these.
* **A cyano group on the nitramide nitrogen**: cyanamide (P-66.1.6.2, pdf p. 664) and nitramide are both preselected amide-class parents competing for one
  nitrogen; the book prints no example resolving which wins.
* **Ethylenedinitramine** (two nitramide groups) keeps round 16's amine name; a candidate PIN, `ethane-1,2-diylbis(nitramide)`, is derived and
  OPSIN-verified but not implemented (nitramide is a hand-built functional parent, not an ordinary suffix `multiplicative.py` already joins).

## Open after naming round 20 (2026-09-26; D-173 and D-178 closed in round 21 above)

D-170 (the substituent `hydrazinylidene`) is fixed; see `CHANGELOG.md`, round 20. Still open:

* **An azine, a triazane or a ring nitrogen on the second nitrogen of an `=N-N` group** keeps the imino form (`3-[(ethylidene)aminoimino]butanoic acid`, `3-(hydrazinylimino)butanoic acid`,
  `3-(pyrrolidin-1-ylimino)butanoic acid`); the book's names for them were not derived.
* **Hydrazones of carbon acid hydrazides** (`CC(=O)NN=CCCCCC` is `1-acetyl-2-hexylidenehydrazine`, where P-66.3.3 names the hydrazide, `N'-hexylideneacetohydrazide`) are not measured.
* **Two or more nitramide groups** (ethylenedinitramine) keep round 16's amine name, which is NOT the PIN; **a cyano group on the nitramide nitrogen** is left to the general path.

## Open after naming round 19 (2026-09-26; D-170 closed in round 20 above)

D-169 (nitric and nitrous hydrazides as parents) is fixed; see `CHANGELOG.md`, round 19. Still open:

* **D-170, the substituent names of a hydrazone or hydrazine** (OPEN `D-170a-c`): the book prints `=N-NH2` as `hydrazinylidene` ("3-amino-3-hydrazinylidenepropanoic acid (PIN)", pdf p. 682) and the nitro and nitroso
  derivatives as `nitrohydrazinylidene` / `nitrosohydrazinylidene` (p. 717); the engine writes `(aminoimino)` and `(R-aminoimino)` for the whole `=N-NH-R` family, of which round 18's `(nitramidoimino)` is one member.
* **Two or more nitramide groups** (ethylenedinitramine) keep round 16's amine name, which is NOT the PIN; **a cyano group on the nitramide nitrogen** is left to the general path.

## Open after naming round 18 (2026-09-26; D-169 closed in round 19 above)

D-168 (the `nitramido` and `nitrosoamino` prefixes) is fixed; see `CHANGELOG.md`, round 18. Still open:

* **D-169, the nitric and nitrous hydrazides** (`O2N-NH-NH2` is `nitrohydrazine`, `ON-NH-NH2` is `1-amino-2-oxohydrazine`, and a hydrazone of either is a hydrazine with an ylidene): the book makes them
  preselected parents (P-67.1.2.6.3, pdf p. 708). The nitramide route declines any hydrazine or hydrazone nitrogen, so these keep hydrazine names. OPEN rows `D-169a-c` carry OPSIN-verified targets.
* **Two or more nitramide groups** (ethylenedinitramine) keep round 16's amine name, which is NOT the PIN; **a cyano group on the nitramide nitrogen** is left to the general path.

## Open after naming round 17 (2026-09-25; D-168 closed in round 18 above)

D-166 (`nitramide`) and D-167 (N-nitro and N-nitroso carbamates) are fixed, and round 17 changed round 16's names for the plain nitramines and nitrosamines to the book's PINs (P-67.1.2.6.3, pdf p. 708):
`dimethylnitramide`, `dimethylnitrous amide`. `CHANGELOG.md`, round 17. Still open:

* **D-168, the substituent prefixes:** where a nitramide is not the parent, `-NH-NO2` is `(nitroamino)` and the book prints `nitramido` (pdf p. 717); `-NH-NO` is written `4-nitrosoaminobenzoic acid`,
  without the parentheses a compound prefix needs.
* **Nitric and nitrous hydrazides** (`O2N-NH-NH2`, `ON-NH-NH2`) keep their hydrazine names; **two or more nitramide groups** (ethylenedinitramine) keep round 16's amine name, which is NOT the PIN;
  **a cyano group on the nitramide nitrogen** is left to the general path.

## Open after naming round 16 (closed in round 17 above) (2026-09-25)

D-164 and D-165 (a nitro or nitroso group on an ACYCLIC nitrogen) are fixed; see `CHANGELOG.md`. Still open, each with a target OPSIN reads back to the same structure and that is NOT
checked against the Blue Book:

* **D-166, nitramide itself** (`N[N+](=O)[O-]`): no naming plan (the amine entries need a carbon on the nitrogen; there is no retained name for the bare parent). Target `nitramide`.
* **D-167, N-nitro and N-nitroso CARBAMATES:** `CCOC(=O)N[N+](=O)[O-]` is `[(nitroamino)(oxo)methoxy]ethane` and `CCOC(=O)N(C)N=O` is `1-(ethoxycarbonyl)-1-methyl-2-oxohydrazine`, both reading
  back. The functional-class ester route does not take them. Targets `ethyl nitrocarbamate` and `ethyl methyl(nitroso)carbamate`, in the engine's own carbamate style.
* **Not measured, so not claimed:** N-nitro or N-nitroso on a hydrazine, on a thioamide, on an amidine that is not a guanidine.

## Open after naming round 15 (2026-09-24)

D-163 (a nitro group on a RING nitrogen) is fixed; see `CHANGELOG.md`. **A nitramine was in no benchmark row**, so every standing measure reported no change for the fix
and none is evidence for it: the evidence is the nine D-163 rows in `tests/test_namer_known_defects.py` and a before/after diff of a 20-structure battery.

**The acyclic N-nitro and N-nitroso cases this section first listed as open are D-164 and D-165, fixed in round 16 (the section above).**

## Open after naming round 4 (2026-09-18)

Round 3's table below is closed except for one row: chloroquine, warfarin,
caffeine, 1,4-xylene, the sulfoxides, the N-oxide locant and cid14000's double
wrapping are all fixed, each with a `D-0xx` row in
`tests/test_namer_known_defects.py` (D-038..D-082 are round 4's). The float
comparator is gone too (stage 5, `NomenclaturePreferenceKey`), and so is the
strategy that the cache key ignored (A11). What remains, by layer. Every
target here was checked against the book on the page cited; none is guessed.

| layer | case | emits | preferred | note |
|---|---|---|---|---|
| candidate generation | heterofused systems not in the ring table | von Baeyer names | fusion names | cid5000, cid40000, the book's 2-benzazepine: general fusion construction (P-25.3), round 5 |
| candidate generation | multiplicative names | `N''-{14-[(diaminomethylidene)amino]tetradecyl}guanidine` | a multiplicative bis-guanidine | also methylenebis(phosphonic acid) and N'-acyl hydrazides (`N'-benzoylbenzohydrazide (PIN)`, p. 671). Admitting an acylated N' into the hydrazide pattern named a WRONG molecule, so it is held out |
| candidate generation | hydrazine as a parent hydride | `1-(hydrazinyl)methanamide` | `hydrazinecarboxamide (PIN)` (p. 645) | and the carbazates, `ethyl hydrazinecarboxylate` |
| candidate generation | N-substituted nitrogen oxoacids | `[(hydroxysulfonyl)amino]methane` | `methylsulfamic acid` | the oxoacid composers decline and the general path names a hydride |
| retained parents | oxamide, oxalohydrazide | `ethanediamide`, `ethanedihydrazide` | `oxamide (PIN)`, `oxalohydrazide (PIN)` (pp. 351, 668) | substitution allowed on both |
| retained parents | silicic acid, disiloxane | `tetrahydroxysilane`, `trimethyl(trimethylsilyloxy)silane` | `silicic acid`, `hexamethyldisiloxane` | the second is round 3's last open row |
| PCG seniority | an amide on a urea N | `N-benzoylurea` | `N-carbamoylbenzamide (PIN)` (p. 661) | the engine ranks urea's carbonic amide WITH carboxylic amides; declining the urea route produced `1-amino-N-benzoylmethanamide`, so the urea gate stops at acids (D-078k holds it) |
| PCG assignment | a chain-terminal amidine carbon | `4-carbamimidoylbutanoic acid` | amino + imino prefixes, as "methyl 4-(dimethylamino)-4-(ethylimino)butanoate (PIN)" (P-66.4.1.3.2, p. 677) | when the amidine carbon terminates a chain |
| PCG assignment | a silanol with an alcohol elsewhere | `2-[(hydroxy)di(methyl)silyl]ethan-1-ol` | a silanol parent (P-44.1.2, Si before C) | the single-centre route declines on any same-class group rather than count them |
| PCG assignment | hydroxamic acids | `cyclohexanecarbohydroxamic acid` | `N-hydroxycyclohexanecarboxamide (PIN)` (p. 587) | |
| numbering | tetrahydropyridines | `1,2,5,6-` | `1,2,3,6-tetrahydropyridine-4-carboxylic acid` | ranks ring double bonds, not hydro locants |
| numbering | `pyridin-1(6H)-yl` | the old name | its lowest orientation | the free valence is not in the preference key, so the P-58.2 route declines |
| data | 32 ring-table entries | -- | -- | they number only some positions; a substituent elsewhere had an empty locant. Guarded (the plan is refused), not repaired |
| serialization | thioacyl amino prefixes | `4-(ethanethioylamino)benzamide` | `4-(ethanethioamido)benzamide (PIN)` (p. 657) | a compound thioacyl is also left unenclosed |
| serialization | phosphoryl prefixes | `[diethyl(oxo)phosphanyl]acetic acid` | `(diethylphosphoryl)acetic acid` | "phosphoryl (preselected prefix)" for -PO< (p. 357), substituted as in "[(dimethoxyphosphoryl)oxy]carbonothioyl (preferred prefix)" (p. 359) |
| serialization | tert-butyl | `dimethyl(2-methylpropan-2-yl)silanol` | `tert-butyldi(methyl)...` (pp. 313, 375) | the book prints tert-butyl in PINs |

Also open, and not a name defect:

* **The atom-drop invariant has gaps.** Twice this round a change made the
  engine drop atoms and still return a name, and the plan-level atom-drop
  invariant caught neither: an FG with no prefix form that was not the
  principal group vanished with its atoms ("pentanoic acid" for an oxime acid),
  and an Si-OH suffix class (abandoned) named trimethylsilanol
  "hydroxymethane". Both were caught by a round trip, after the fact. A check
  that the finished tree accounts for every atom would catch the next one.
* **The registry.** `data/retained_names_expanded.json` now carries typed
  evidence and applicability fields: 18 PINs, 26 non-PIN retained names and 15
  book-absent names are typed; 251 entries still have no audited status.
  Separately, `data/opsin_extracted/retained_names_from_opsin.json` holds 1,824
  names taken from OPSIN's parse dictionary that feed whole-molecule naming
  unaudited (fluorouracil among them): a parser's vocabulary is not evidence
  of a PIN.
* **The book contradicts itself once, and the rule was followed.** Its prefix
  list prints `2,3-dihydro-1H-isoindol-2-yl` (p. 344); P-58.2.3.1.1 and the
  worked analysis on p. 499 give `2H-isoindol-2-yl`. The engine emits the
  latter; the test row says why.
* **Substituent numbering.** Composing `PrefixEntry.atom_origin` down the
  tree numbers every prefix subtree on the molecule, except compound amino
  prefixes assembled as strings, which carry no tree.

## Open after naming round 3 (2026-09-17)

Each of these has a known target, quoted from the Blue Book, and is not yet
implemented. Listed by layer, because the round's finding was that defects
which all look like "the ranking picked wrong" live in different places.

| layer | case | emits | preferred |
|---|---|---|---|
| candidate generation | chloroquine | `...quinolin-4-amine` | `...pentane-1,4-diamine`: no candidate carries two PCGs (P-44.1.1) |
| PCG assignment | warfarin | `4-(4-hydroxycoumarin-3-yl)...butan-2-one` | `4-hydroxy-3-(...)chromen-2-one`: the ring is offered with a phenol suffix only |
| PCG assignment | caffeine | `1,3,7-trimethyl-2,6-dioxo-1H-purine` | `1,3,7-trimethylpurine-2,6-dione`: exposed by D-036 |
| data | p-xylene | `1,4-dimethylbenzene` | `1,4-xylene` (P-22.1.3): the registry needs an entry ADDED |
| functional class | dimethyl sulfoxide | `dimethyl sulfoxide` | `(methanesulfinyl)methane` (P-63.6) |
| additive | trimethylamine N-oxide | `N,N-dimethylmethanamine oxide` | `N,N-dimethylmethanamine N-oxide` |
| serialization | hexamethyldisiloxane | `trimethyl(trimethylsiloxy)silane` | `...silyloxy...`: the O-bridge assembly drops a `yl` |
| serialization | a tertiary-amine prefix | `{[(ethyl)][...]amino}` | `{ethyl[...]amino}`: a simple prefix wrapped twice |

Deliberately deferred at the time, and closed in round 4: the float
preference score (now `NomenclaturePreferenceKey`), and the strategy missing
from `NamingSession`'s cache key with `IUPACCanonical()` built at 11 sites
(now `active_strategy()`). The registry backlog is 251 entries.

## Not limitations

* The five tests that shipped red are not engine defects. They asserted a
  non-minimal lambda numbering and three general-nomenclature-only acylium
  names; the engine's output is correct in every case. See `CHANGELOG.md`.

## Open after naming round 5

Round 5's own list, by layer. The full table, with every case's emitted name
and its cited target, is in the OpenChem Studio repository this fork is
maintained from; what follows is the summary a caller needs.

* **Fusion**, beyond one parent plus first-order attached components: a
  second-order attached component (16 of the book's P-25 examples), a
  multiparent system, interior heteroatoms (P-25.3.3.2), a 7- or 8-membered
  ring fused on three or more sides, rings larger than eight members, and
  helicenes. Each refuses with a code rather than guessing.
* **Ownership**, two blind spots: a prefix whose NAME denotes an atom it does
  not CLAIM (which let one wrong molecule through, found by probe instead),
  and the 66 of 267 corpus molecules named with no substitutive level at all,
  where a leaf is trusted to name its whole fragment.
* **Candidate generation**: N'-acyl hydrazides, carbazate esters, a C=O
  between two N=, a substituted hydrazide as a prefix, condensed ureas
  (`2-imidodicarbonic diamide`), two acyl groups on one nitrogen
  (`N-acetylbenzamide`), Si-NH-Si, phosphoramidocyanidate esters, and
  skeletal replacement where a principal group is present.
* **Serialization**, classified and left: `tert-butyl` in a preferred name
  (it renames the prefix and moves the alphanumerical citation order, so it
  is not the ranking-neutral change that stage admits), `tert-butoxycarbonyl`,
  `propane-2-sulfonyl`, `ethanethioamido`, `phosphoryl`, and the substituted
  carbamimidoyl prefix. P-14.3.4.5 is not applied to an unsaturated parent or
  to a heteroaromatic one: `1,5-dimethyl-1H-tetrazole` keeps its locants
  because `2,5-` is another compound.
* **Data**: OPSIN's RING vocabulary (705 ring names, 821 fusion components)
  is read as parent names and is not audited. Of the 44 ring parents that win
  on the tuning corpora, 10 come only from that vocabulary, and all 10 are
  book names. 171 registry entries remain untyped; the gate refuses every one
  of them that came from OPSIN's dictionary.
* **Ranking**: the P-44.1.2 senior-atom tier is compared ring against ring,
  which the book says it is not. It agrees with P-44.2.1 except for a ring
  whose senior atom is O/S/Se/Te against one whose is P..B, a pair no corpus
  molecule has.

## Open after naming round 6

* **Cyanamide as a PREFIX** (`3-(cyanoamino)propanoic acid`): the Blue Book
  prints no name for it (searched: no `cyanoamino`, `cyanamido` or `N-cyano`
  prefix), so none is targeted.
* **`cyanato` is not enclosed** (`3-cyanatopropanoic acid`) while `thiocyanato`
  is: the book prints only the latter's enclosure (`3-(thiocyanato)propanoic
  acid (PIN)`); a cyanate ester is derived from the rule, not printed.
* **The two new functional-parent routes return a leaf**, so they share the
  ownership blind spot recorded for round 5: the leaf is trusted to name its
  whole fragment.
* **Acyl cyanates and thiocyanates** (`CC(=O)SC#N`, named `acetyl thiocyanate`
  by the acyl route) are not attempted by the ester route.
* **Not from this round, found beside it: carboxylate ANIONS carrying a
  hydroxy or amino group are named as if that group were the principal one.**
  `Oc1ccccc1C(=O)[O-]` comes out `2-oxidooxomethylphenol`, which OPSIN reads
  as a phenolate aldehyde, a different molecule; likewise the 2- and
  4-aminobenzoates and 3-hydroxybenzoate. The aliphatic cases round-trip and
  are not preferred: lactate is `1-oxido-1-oxopropan-2-ol` (the book's name is
  `2-hydroxypropanoate`) and glycolate `2-oxido-2-oxoethan-1-ol`. Benzoate,
  acetate, chloroacetate and 2-methylbenzoate are unaffected. In no corpus.

## Open after naming round 7

Round 7 closed the acid-anion class and made ownership of a charged atom a measured property; what is left:

* **Deprotonated phosphonic and phosphoric acids are a DECLARED unsupported class** (`hydroxy(oxido)(oxo)(phenyl)
  phosphane` for `hydrogen phenylphosphonate`, p. 808): the "hydrogen" method for acid esters of inorganic acids is
  a construction of its own. Structurally right, not preferred; in `charge_ownership.DECLARED_UNSUPPORTED`.
* **The chiral amino-acid anions** (`alaninate`, `prolinate`, `tyrosinate`, `cysteinate`, `glutamate`) get the flat
  systematic name (`2-aminopropanoate`). OPSIN reads a bare `alaninate` as the L-isomer while P-103.1.3.1 designates
  configuration by D/L, so a whole-molecule retained name needs a stereo policy first. Glycine (achiral) is done.
* **Protonated imidazole** is `1,3-diazol-1-ium` (the book: `1H-imidazol-3-ium`) and **protonated benzimidazole** is a
  NAMING ERROR (a refusal, not a wrong name). The retained ring is found for a fully N-substituted cation and not
  when `[nH+]` sits beside `[nH]`; abandoned under the round's stop rule after a short look.
* **A betaine's cationic prefix** is `(trimethylazaniumyl)acetate`; the book prints `(N,N-dimethylmethanaminiumyl)
  acetate` (pp. 362, 837). Both denote the same structure and the pages read do not say whether the first is also
  permitted.
* **A zwitterion with an anion of ANOTHER class** (`[NH3+]C(C[O-])C([O-])=O`) round-trips but is not preferred:
  `acid_anion_route` returns `None` for two anion classes, so the carboxylate is not carved.
* **A compound acyl name on `azanide`** (`chloroacetylazanide`) is written solid: the enclosure test looks for locant
  characters and misses a substituent without one.
* **WRONG MOLECULE, found after the final evaluation and not fixed: the trianion of a tricarboxylic acid** (citrate
  `[O-]C(=O)CC(O)(CC([O-])=O)C([O-])=O`) is named `3-carboxy-3-hydroxypentanedioate`, with one carboxylate written as
  a neutral `carboxy` prefix: two charges for three sites. Two layers: the NEUTRAL acid is named
  `3-carboxy-3-hydroxypentanedioic acid` where the book prints `2-hydroxypropane-1,2,3-tricarboxylic acid (PIN)`
  (P-65.1.1.2.3, p. 578), and the classifier route then converts only the suffix groups. It was a wrong name before
  the round too. A sound fix is a charge ledger on that route (every acid group there IS a deprotonated site, so an
  acid prefix in the name is a wrong charge) plus the neutral chain choice.
* **Found by the same check: the biguanidium cation** (`CN(C)C(=N)NC(N)=[NH2+]`) is named as a dication
  (`...-1-iminomethanebis(aminium)`). Not an anion, so outside the class this round worked on.
* **Not attempted this round, and not investigated** (so no diagnosis is recorded): N'-acyl hydrazides and the
  substituted-hydrazide prefix, two acyl groups on one N, carbon with two double-bonded suffix groups, Si-NH-Si and
  condensed ureas. Each keeps its row in "Open after naming round 5".
* **The carboxylate-anion item that closes the round-6 section above is FIXED**: salicylate is `2-hydroxybenzoate`,
  lactate `2-hydroxypropanoate`, glycolate `hydroxyacetate`.

## Open after naming round 8

Found and recorded, by layer; none is a wrong molecule, and each reads back through OPSIN. The repository's `KNOWN_LIMITATIONS.md` carries the same list with
its measurements and the panel it was measured on.

* **A thiolate beside an acid anion** (`[S-]c1ccccc1C(=O)[O-]`) is `2-[oxido(oxo)methyl]benzene-1-thiolate`; the carved route takes an olate, and a thiolate's anionic
  prefix is not built.
* **A charged acid group inside a substituent** is named with `oxido`: `4-[(oxidosulfonyl)methyl]benzoate`, `3-carboxy-4-(2-oxido-2-oxoethyl)benzoate`, where the
  book prints `sulfonatomethyl`, `carboxylatomethyl` (p. 619).
* **N-alkoxy amides and amines**: a thioamide (`N-methoxy-N-methyl-1-thioxoethan-1-amine`), an N,N-dialkoxy amide, and O-alkylhydroxylamines
  (`(aminooxy)methane`, the book's `O-methylhydroxylamine`, a retained parent the engine does not build).
* **Several nitrate groups** (`1,2,3-tris(nitrooxy)propane`, the book's `propane-1,2,3-triyl trinitrate`); **chloroformates and dicarbonates**
  (`methoxymethanoyl chloride`, a nine-part name for di-tert-butyl dicarbonate); **carbazate esters** (`(ethoxycarbonyl)hydrazine`: the carbamate plan for a
  carbazate is tried and fails with 'atoms unclaimed', and the engine names the next plan; the old comment saying the anion cannot be named is stale).
* **Peptide-like acyl prefixes**: `acetamidoacetamidoacetic acid` is not enclosed, and a glycyl is `2-amino-1-oxoethyl`.
* **Benzil** keeps its locants (`1,2-diphenylethane-1,2-dione`; the book prints `diphenylethanedione`); **substituted carbamimidoyl** is
  `[(dimethylamino)(ethylimino)methyl]`; **peroxide, sulfur, phosphorus and boron pseudoketones** keep oxo prefixes; diacyl peroxides and xanthate esters are
  named by prefixes; a one-carbon ketone parent's second prefix is not enclosed (`(morpholin-4-yl)phenylmethanone`).
* **Condensed guanidines and ureas with n >= 5 AND substituents** are refused (a guard keeps them from taking the bare chain's name).
* **Not attempted, unchanged from earlier rounds**: the P-15.3 multiplicative constructions, the silicon rows (`D-089s`, `u`, `v`, `D-090b`), the hydrazide prefix
  spelling (`D-088d`, partly fixed), fusion (`D-086a` to `c`), chiral amino-acid anions (a stereo policy first), deprotonated phosphorus acids (declared
  unsupported), second-order and multiparent fusion, interior heteroatoms, and helicenes.
* **The one deliberate deviation from the book**: the curated ring table numbers pyrene's interior carbons `10b`, `10c` (the book's PIN: `3a1`, `5a1`, P-25.3.3.3.1,
  p. 224), perylene's `12c`, `12d`, and a phenalene-type hydro ring's `9b`, because the round-trip oracle reads the CAS letters and not the superscripts. Declared in
  the repository's `benchmarks/naming/known_deviations.toml` with its guard; OPSIN reading a name is never a reason to add another.

## Open after naming round 9

Round 9 fixed 9 of 13 findings from a source-backed instruments stage (a Blue Book PDF harvest, an ordinary-compound battery, a frequency census). The
"peptide-like acyl prefixes" row above is SUPERSEDED, not merely fixed: the retained acyl-plus-parent convention (P-103.2.5/P-103.3.2) is now built as a
closed table of the 20 proteinogenic amino acids, and `acetamidoacetamidoacetic acid` / `2-amino-1-oxoethyl` no longer appear for the shapes it covers.

Four findings are not fixed, each already diagnosed:

* **A carbamimidate/oxime prefix-bracketing ambiguity**: `COC(=N)NN` and similar, where "(hydrazinyl)" and "methoxy" concatenate without a locant. The
  fix touches widely-used prefix-assembly logic with real regression risk across every substituent name in the engine; deliberately not rushed.
* **Two dye-molecule ring-numbering defects, different root causes**: a phenothiazine core (methylene blue) numbers to locant 12, which OPSIN rejects
  outright -- phenothiazine is registered for automorphism matching but has no traditional-numbering override table entry, unlike its anthracene/
  acridine/xanthene analogues. A spiro xanthene (fluorescein) numbers to locant 13, out of xanthene's own valid range -- xanthene itself IS correctly
  registered, so this is a spiro-combination numbering bug, not a missing table entry; not yet isolated to a fix.
* **A polycarbocation** (two independent tertiary-carbocation substituents on one ring) needs the multiplicative and charge-perception machinery to
  work together to reach a name like "(1,3-phenylene)di(propan-2-ylium)"; no existing pattern in the codebase does this yet.

## Open after naming round 10

Round 10 closed all 4 items round 9 deferred, each turning out deeper than round 9's own diagnosis:

* **Phenothiazine-dye-locant, FIXED**: round 9's diagnosis (a missing traditional-numbering table entry) was incomplete -- adding the entry had
  zero effect on methylene blue's actual output. The real defect was a THIRD function, `retained_lookup.py`'s `_build_numbering_from_atom_locants`:
  its bond-generic substructure-match fallback (built to recover a curated ring's numbering when a substituent shifts the Kekule pattern) was gated
  to require every ring atom aromatic, including phenothiazine's N/S bridge -- non-aromatic on the isolated curated-key SMILES, but aromatic in
  methylene blue's actual extended-conjugation form. Fixed by relaxing the gate to "every CARBON aromatic" (heteroatom aromaticity is
  context-dependent; a ring carbon's is structural). Engine now emits `[7-(dimethylamino)phenothiazin-3-ylidene]di(methyl)azanium chloride`,
  matching PubChem's own name for methylene blue verbatim. Phenoxazine shares the identical defect and fix, proven by direct testing.
* **Spiro-xanthene-dye-locant, FIXED**: xanthene's own curated `atom_locants` covered only 9 of its 14 real ring positions (missing the four
  fusion carbons and the bridge oxygen's own locant) -- harmless for a bare or substituted xanthene, but it broke `spiro.py`'s combined-numbering
  completeness gate for fluorescein entirely. Fixed by completing the table, derived from its own bond topology against the already-correct
  traditional numbering. Reaches fluorescein's real IUPAC name exactly, including a second latent defect (the lactone's own locant) fixed as a
  side effect.
* **Charge-polycarbocation, the wrong-molecule half fixed**: `_classify_polycarbon_charge` already existed and already covered this exact shape,
  but its guard checked the WHOLE MOLECULE for any aromatic atom rather than the charged atoms' own scope. Narrowed to the charged atoms; the
  classifier now engages and claims both charges, but no renderer composes a name for two independently-attached substituent cations on a shared
  aromatic parent yet. Per this engine's own "refusal guard" (a classifier that engages and cannot finish RAISES rather than falling through to
  the wrong neutral name), the wrong-molecule defect is fixed; the PIN itself is separate, still-open render-side work.
* **Carbamimidate-oxime-swap, FIXED**: the engine's internal structure was correct the whole time -- the wrong OUTPUT STRING left a trailing
  "-oxy" prefix unbracketed after a preceding closing paren, and OPSIN's grammar read the adjacency as one nested substituent instead of two
  siblings on the same parent carbon. No existing enclosure rule covered a carbon-centered one-carbon STANDALONE parent with this shape (the two
  closest rules are each out of scope for a different reason). Fixed by bracketing a non-leading "-oxy" prefix on any one-carbon chain parent,
  any output form. A second, independent instance of the same bug (a different prefix pair, a different parent) was found during diagnosis and
  fixed as the same side effect.

A regression from the phenothiazine fix (item 1's gate widening also covered a structurally-meaningful heteroatom double bond in an unrelated
ring, arsanthrene) was caught by the standalone suite before this sync and is already fixed in what follows -- narrowed further to exclude a
non-aromatic heteroatom carrying an explicit double bond.

## Open after naming round 11

Round 11 re-verified every candidate directly against the current engine before admitting or dropping it -- two of five
candidates this round looked at were already fixed by other rounds' own general work, never reflected back into this
document until now.

**Fixed this round:**

* **Ketone-parent enclosure, FIXED (D-143)**: `assembly.py`'s `_assemble_substitutive` had two existing one-carbon-parent
  P-16.5.1.3.1 enclosure rules (a heteroatom-center mononuclear parent; a SUBSTITUENT-form compound prefix), but neither
  reached a one-carbon KETONE parent in STANDALONE form. `(morpholin-4-yl)phenylmethanone` left its second, simple
  "phenyl" prefix unbracketed. Fixed by mirroring the existing heteroatom-center block, scoped to a ketone's own suffix
  base_form ("one"). Severity C, not A -- OPSIN parses the unbracketed form too.
* **Carbamimidoyl N'/N,N split, FIXED (D-091v, moved from open)**: the existing "N'-substituted carbamimidoyl" special
  case required the amino N to be a bare, unsubstituted NH2, so a substituted amino N fell through to the generic
  recursive path, which OPSIN misreads as an azo-linked structure. Generalized to carve 0/1/2 substituents off the
  amino N too, gated to REQUIRE the imino N also substituted before firing: an amino-only-substituted, imino-bare
  fragment round-trips via OPSIN in isolation, but is genuinely APPEARS_AMBIGUOUS when the same shape attaches directly
  to a GUANIDINIUM parent instead of an ordinary one. A first version without this gate regressed the metformin-cation
  fixture; caught by the standalone suite before commit, kept as a permanent non-regression test.

**Re-verified and found already correct, no fix needed:**

* **Ring-nitrogen acyl prefix on a ring/chain parent**: the documented repro (a piperidine amide on a benzoic acid)
  now emits the correct "(piperidine-1-carbonyl)" form directly, verified for piperidine, morpholine and pyrrolidine.
  Fixed as a side effect of other rounds' own serialization work, never reflected back into this document.
* **The polyacid-anion charge ledger**: citrate's trianion now emits its printed PIN
  (2-hydroxypropane-1,2,3-tricarboxylate), bare and as the trisodium salt. The biguanidium dication now correctly
  RAISES instead of silently naming the wrong molecule -- the same refusal-guard class already established.

**Re-verified, found narrower but still genuinely open, re-diagnosed deeper:**

* **A charged acid group inside a carved substituent** (FIXED in round 12, D-144; see below): still broken at the time of round 11, confirmed on the exact repro. Traced to root
  cause -- `_carved_acid_group_fgs` (`engine.py`) already computes the correct anionic prefix form ("carboxylato",
  "sulfonato") for a demoted acid-anion site on the "carved" route, but that value is never threaded into the
  recursive substituent-naming call that renders a nested acid-anion group, whose own fresh `Perception()` call does
  not detect a charged chalcogen as an FG at all. Broader than previously known: affects a demoted CARBOXYLATE the
  same way as a demoted SULFONATE, not only sulfonate. Not rushed, given the shared code path several existing
  special cases (including this round's own carbamimidoyl fix) already sit beside.

## Open after naming round 12

Round 12 was deliberately small: one fully diagnosed item and one census signal that had never been triaged. Round 11's deferred
item is fixed; the fused-cation signal was measured and NOT admitted, because no single mechanism reaches the admission floor.

**Fixed this round:**

* **A charged acid group inside a substituent, FIXED (D-144, moved from open)**: on the carved acid-anion route the OUTER plan already
  held the right typed fact (a `DetectedFG` with `prefix_form` `carboxylato`/`sulfonato`, from `_carved_acid_group_fgs`), but a group
  inside a substituent is named by a RECURSIVE call on the carved fragment, whose fresh `Perception()` cannot see a charged chalcogen as
  an FG, so it composed `oxido` + `oxo` atom by atom. `generate_plans` now adds the same typed FGs for a SUBSTITUENT-form fragment, from the
  fragment's own atoms (`_substituent_acid_anion_fgs`), for exactly the classes in `_ANIONIC_ACID_PREFIX` (any other class would drop its
  charge; a phosphonate stays on its declared-unsupported path). `3-carboxy-4-(2-oxido-2-oxoethyl)benzoate` is now
  `3-carboxy-4-(carboxylatomethyl)benzoate`; `4-[(oxidosulfonyl)methyl]benzoate` is now `4-(sulfonatomethyl)benzoate` (P-65.6.2.3.1). The
  fix skips a group that contains the attachment atom: a first version did not, and double-owned the atom on `[S-]c1ccccc1C(=O)[O-]`
  (D-121u), a failed plan and a NAMING ERROR fall-back, caught by the known-defects suite before commit.

**The seam.** The outer path computed the correct typed fact, the recursive path discarded it by re-perceiving a fragment, and each guard was
correct in isolation. A recursive naming call should inherit explicit semantic context and create fresh perception only for genuinely new
local facts. Here everything the fact depends on (the acid group and its attachment carbon) is inside the fragment, so it is re-derived
with the same helper the outer path uses; a fact that is NOT local to its fragment would have to be inherited, with the outer atoms mapped
into the fragment's own indices.

**One tie-break this exposed and did not fix.** `[5-carboxy-2-(carboxylatomethyl)phenyl]acetate` and its `4-carboxy` twin are the same
molecule; which is emitted depends on the SMILES atom order. Both read back; the book prints no row for this structure.

**The fused-aromatic-ring-cation signal, triaged and not admitted.** Of 36 hits (36 unique structures) 28 name and read back and 8 embed a
`[NAMING ERROR ...]` marker; a scan of all 292 charged rows of the same 2000-structure sample found 6 more cationic ring-system failures
outside the proxy. They are visible failures, never a wrong molecule, spread over about ten ring systems (imidazo[1,2-a]pyridin-4-ium 4,
imidazo[2,1-f]purinium 2, imidazo[2,1-b][1,3]thiazol-4-ium 1, a purin-7-ium as a substituent 1, six saturated or bridged ring-N cations one
each). The neutral parents name; the bridgehead or ring-N cation does not (a fused CATION with no curated entry). The largest single system
is 4/2000 = 0.2%, under the 10-structure floor.

## Open after naming round 13

Round 13 started from a measurement: naming EVERY structure of a 2000-structure sample and reading each name back through OPSIN. It found the
largest wrong-structure cluster in the sample (a wrong ring locant, 1.35%) and an ownership failure (0.65%), both old and in no backlog. Exact
read-backs went 93.45% -> 94.80% -> 95.70%; candidate wrong structures 2.40% -> 0.90%; embedded engine errors and refusals 1.90% -> 1.15%.

**Fixed this round:**

* **A wrong ring locant on a 1,3,4-oxa/thiadiazole (and 1,2,5-oxa/thiadiazole) substituent, FIXED (D-145).** `_lowest_free_valence_numberings`
  ranked the lowest COMBINED heteroatom locant set ahead of the senior heteroatom at locant 1. A monocyclic hetero ring is numbered by
  Hantzsch-Widman (senior heteroatom = 1). 1,3,4-thiadiazole (S1,N3,N4) has the alternative N1,N2,S4 with the lower set {1,2,4}, so the substituent
  was numbered as another heterocycle and its attachment carbon came out `-3-yl`. Only a ring carrying its own second substituent reached this
  filter (the bare ring goes through `_heteroaryl_substituent_with_locant`, which weights seniority). For a monocyclic ring the senior heteroatom's
  locant is now ranked first; a fused ring keeps `together` first.
* **A hard-coded curated locant returned for every attachment, FIXED (D-146, D-147).** A ring with no `atom_locants` and a `substituent_form`
  ending in a digit returned that form verbatim (`2,3-dihydro-1,4-benzodioxin-2-yl` for any benzo carbon, `azepan-1-yl` for any carbon of azepane).
  The numbering computed just above the early return already knew the real locant; it is used now when it differs from the curated digit.
  Benzodioxine is fused and the generic numbering mislabels the two positions next to the ring fusion, so it also gets an `atom_locants` table
  derived from its bond topology, as 1,3-benzodioxole's is.
* **A data row keyed on the wrong ring, FIXED (D-148).** The curated `1,2,5-oxadiazole` row was keyed on `c1conn1`, which is 1,2,3-oxadiazole.
  The key is `c1cnon1` now, and the parent and substituent are the systematic `1,2,5-oxadiazole` (BlueBookV2.pdf p. 263: "1,2,5-oxadiazole
  (formerly called furazan)"), where real furazan used to come out `furazan`.
* **A demoted ketone claimed its aryl carbon, FIXED (D-149, D-150).** `_compute_prefix_assignments` Pass 1 built the `oxo` prefix of a demoted
  ketone (anchor already in the parent) from every off-parent atom of the group and dropped only heteroatom context. A ketone matches its two
  flanking carbons as context; the one off the parent chain (an aryl or cycloalkyl ipso carbon) was claimed by the `oxo` AND by the `phenyl` the
  structural pass carved, so the ownership invariant rejected the plan (`atom 8 owned by prefix[0] and prefix[1]`), correctly. The same double
  claim silently killed the plan that named an acid or amide as the parent: `4-oxo-4-phenylbutanoic acid` came out `3-carboxy-1-phenylpropan-1-one`.
  A non-anchor carbon still in `remaining` is no longer claimed when the group is suffix-eligible and its anchor is in the parent.

**Open, found by exposing it (D-151):** an ESTER of an acid that also carries a ring-nitrogen sulfonamide is named as a functional-class ester of
the piperidine, whose "acid" is a `carboxy` prefix (`ethyl 1-(4-carboxyphenylsulfonyl)piperidine`). A wrong structure; already there for plain
methyl and ethyl esters, and no longer masked for the phenacyl ester. 2 of 2000 sampled structures. Derived target, read back: `ethyl
4-(piperidine-1-sulfonyl)benzoate`.

**Open, from testing every curated ring at every attachable position** (7,372 cases; 295 table-backed rings swept at 0 wrong): all-carbon fused
rings named with a bare `-yl` (nonacene, octacene, heptacene, the phenes, the helicenes: 11 rings) and about 7 partly hydrogenated fused rings on
the generic numbering path. The neutral parents of the cations that fail to name sweep clean, so those failures are a separate, cation-layer
defect (14 of 2000 sampled structures).

**What a consumer sees.** The engine still emits an embedded `[NAMING ERROR: ...]` for a structure it cannot name (D-133's target is one, on
purpose); a consumer of this package sees that string. Only a layer that reads names back through a parser can withhold it.

## Open after naming round 14

Round 14 worked the measured residue of round 13 as clusters with ONE root mechanism each; naming a 2000-structure sample and reading every name back through
OPSIN went from 95.70% to 97.95% exact (no structure that read back exactly stopped doing so). Fixed this round: D-151 to D-162 in `tests/test_namer_known_defects.py`.

**Definitions.** A name is `exact` when the InChIKey of the input equals the InChIKey of OPSIN's read-back of the name (formula equality is never
correctness). OPSIN is a STRUCTURAL check only: it is not an authority for a preferred numbering or a PIN.

**Fixed this round:**

* **A sulfonamide on a RING nitrogen (D-151, D-152).** `S(=O)(=O)N<ring>` was detected as a sulfonamide whose demoted prefix claimed S, O, O and N and left the
  ring's carbons unclaimed, so every plan with the other side as parent died and the engine named the ring as the parent: an acid lost its suffix and an ESTER was
  named as an ester of the piperidine (a different structure). It is left to the structural carve now, and the prefix is the sulfonic acid's `<ring>-N-sulfonyl`
  (P-65.3.2.3). The sulfamoyl prefix also printed one shared `N,N-` block, so two different N-substituents read `N,N-cyclohexylmethylsulfamoyl`; each carries its own locant.
* **Ring cations that had no name (D-154 to D-157), four roots.** General fusion nomenclature refused any charged ring atom (now described on a neutral copy with the same
  atom indices, bicyclic systems only; tricyclic cations stay on the von Baeyer fallback); a ring-fusion `[n+]` beside an `[nH]` is the same cation as the `[nH+]` drawing and
  the charge is moved; a charged N with three ring bonds was made an indicated-hydrogen target, and the curated quinolizidine row gave its nitrogen `4a` (it is 5); and an
  acyl or amido prefix, derived by naming the acid recursively, lost a ring cation's `-ium` because STANDALONE is promoted to CATION at depth 0 only.
* **Stereo dropped (D-158, D-159).** A retained ring substituent (`oxolan-2-yl`) is a leaf that never reads stereo and the stereo-drop gate ran for STANDALONE only, so
  `(oxolan-2-yl)methanol` lost its descriptor; the gate now also runs for a substituent and reads the parent CIP stash. Tetrahedral stereo on a SPIRO parent is admitted at
  plain-integer locants, under the existing post-assembly OPSIN validation.
* **Fused-ring locants (D-160, D-161).** Heptacene, octacene, nonacene and pentaphene to octaphene were named with a bare `-yl`; each now has a table that is one of the
  numberings `fusion_general.name_fusion` derives under P-25.3.3 (the four helicenes stay unnumbered: the orientation module declines them). octahydro-1H-indole, the biotin
  skeleton and `[1,2,4]triazolo[3,4-b][1,3]benzothiazole` get complete tables.
* **An aromatic non-benzene carbocycle named saturated (D-153).** Tropone was `cycloheptanone`, hinokitiol `2-hydroxy-5-(propan-2-yl)cycloheptan-1-one`: RDKit marks the ring
  aromatic and the carbocycle branch read "no double bond found" as saturated. The Kekule bonds are recovered.

**Open (D-162, and the residue):** an N-hydroxy-N-alkyl amide inside an ester loses its N-substituent (`[(hydroxycarbamoyl)methyl]methyl acetate`), a different
structure. The rest is 41 of 2000 sampled structures in about ten clusters, none with more than 8 members: spiro parents whose centre has a primed locant (stereo still
dropped), tricyclic and amidinium ring cations, four neutral polycycles with no valid plan, lost `[S-]` and `[NH+]` charges, and single-row misnames.
