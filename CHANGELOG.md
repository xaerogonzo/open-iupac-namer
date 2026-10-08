# Changelog — this fork of `iupac_namer`

Changes made on top of upstream commit
`c3eac17ffd110c7c5dd37aaad2955e06cf8c9303`, in the order they were made.
`KNOWN_LIMITATIONS.md` is what is still wrong.

The engine's correctness criterion here is the author's own: the **OPSIN
round trip** — a name is right when parsing it back yields the structure
it came from. Everything below is checked on two independent gates,
canonical SMILES and full InChIKey, because each has a blind spot the
other covers.

Scores quoted as "N/181" are against an external benchmark corpus (the
one this fork was written for, in OpenChem Studio); they are included
because they are what several of these decisions were made on, not
because the corpus is part of this repository. Read them as "this did
not regress anything measurable", not as a claim you can reproduce here.

## Reconstruction of `tests/audit/`

`tests/audit/_audit_helpers.py` is imported by three test files but is
absent from the repository, so `test_fr_orientation_numbering.py` failed
to collect and seven tests failed for that reason alone. Reconstructed
from how the callers use it and from the engine's stated correctness
criterion. State as received: 2,907 passing, 12 failing, one file that
would not collect. After the helper: 2,940 passing, 5 failing.

## The remaining 5 test failures were the tests, not the engine

Investigated all five. None was an engine defect; the engine's output is more
correct in every case, so the expectations were corrected and the comments
that had misled them fixed.

* **Cyclophosphazene lambda numbering (2 tests).** Engine emits
  `1,2,2,4,5,6-hexamethyl-2lambda5-1,3,5,2,4,6-triazatriphosphinine`; the
  tests pinned `4lambda5` with methyls at 1,2,3,4,4,6. Both round-trip, so
  only the lowest-locant rule separates them. The ring name pins N to 1,3,5
  and P to 2,4,6, leaving six numberings; the engine's wins **both** the
  lambda-locant criterion (2 < 4) and P-14.4's lowest-locants-to-prefixes
  (`1,2,2,4,5,6` < `1,2,3,4,4,6`), so it is right however that hierarchy is
  read. The expectation came from an illustrative example in
  `try_hantzsch_widman`'s comment block that the code never produced — with
  the lambda tiebreaker disabled it yields `6lambda5`, not `4lambda5`.
* **Polyacylium surface names (3 tests).** Tests pinned
  `malonylium`/`succinylium`/`glutarylium`. Those retained names are kept for
  general nomenclature only and the systematic name is the PIN
  (P-65.1.1.2.2 / P-66.6.3); `engine.py`'s `_RETAINED_ACID_STEM_TABLE` records
  that decision with citations, and the acid path deliberately emits
  `propanedioic acid`, never `malonic acid`. The expectations were therefore
  unreachable by construction. Four dead keys removed from
  `_RETAINED_DIACID_TO_DIACYLIUM`; `oxalic acid` stays because its retained
  name IS the PIN.

## Instrumentation and a second correctness gate

* **`diagnostics.py`** (new). Off unless `IUPAC_NAMER_DEBUG` is set or a
  `capture()` scope is open. Records every point where a charged molecule is
  handed back to the plan-search neutralizer, attributed to the gate that let
  it go (`unclaimed` / `ambiguous` / `partial_claim` / `charge_sum_mismatch` /
  `render_failed`), plus per-renderer attempted/succeeded/failed counters.
  The counters live in their own module so `charge_perception` keeps its
  documented "no module-level mutable state" invariant.

  The attribution immediately corrected the working model: instrumenting only
  the render site would have missed most of the inventory, because the benzyl
  cation, phenyl anion and guanidinium never reach a renderer at all.
* **Full InChIKey as a second round-trip gate** in an external 181-molecule benchmark corpus.
  Compare the FULL key, never the 14-character skeleton block: guanidinium and
  neutral guanidine share skeleton `ZRALSGWEFCBTJO` and differ only in the
  final protonation character. It found on arrival that two of the four
  standing benchmark failures are tautomers, not wrong molecules.
* The benchmark harness gained a per-molecule HTML report and a run-to-run delta
  that lists regressions first, so a swap — one molecule fixed, another
  broken, headline score unmoved — cannot hide.

## Severity-A fixes (wrong molecule)

Fourteen inputs that named the wrong compound. All are pinned in
`tests/test_namer_known_defects.py`, which runs in the **default** suite.

* **Ring polyacylium** (D-001, 7 cases). `_diacid_name_to_polyacylium` knew
  only `oxalic acid` and the chain `<parent>dioic acid`; ring parents arrive
  as `<ring>-<locants>-dicarboxylic acid`, so it returned `None` and every
  ring-based polyacylium named as its neutral aldehyde — the phthaloyl
  dication as `1,2-bis(oxomethyl)benzene`, i.e. phthalaldehyde. Added the
  `carboxylic acid` -> `carbonylium` rule (P-65.3.1).
* **`-ylium` / `-ide` locant** (D-005, 9 cases). `_render_simple_carbon`
  hardcoded `locant = 1`, true only for a terminal charge — which is all four
  compounds it was written against had, so the round-trip never caught it.
  `C[CH+]C` was named `propan-1-ylium` (it is propan-2-ylium) and
  `[CH2+]C1CCCCC1` was named `methylcyclohexan-1-ylium`, which moves the
  charge onto the ring. The renderer now asks the engine to name the skeleton
  as a **substituent anchored at the charged atom**: the free valence is the
  anchor that forces the parent to contain that atom and number it lowest,
  which is exactly what `-ylium`/`-ide` requires (P-31.1.4). Reuses the
  engine's own parent selection rather than reimplementing it.
* **Charge next to unsaturation** (D-002 family, 7 cases).
  `_classify_simple_carbon_charge` required every atom non-aromatic and every
  bond single, so benzyl/allyl/vinyl/propargyl/diphenylmethyl cations and
  anions were unclaimed — and unclaimed means neutralized, not left alone.
  Gate is now "all-carbon skeleton, charged atom not aromatic". Two guards
  were added after measurement showed the relaxed gate stealing the retained
  ring cations (`phenylium` had started coming out as `benzene-1-ylium`): the
  charge may not sit in an unsaturated ring, and a Kekule-written ring cation
  is not flagged aromatic by RDKit so the ring-saturation test is the one that
  matters.

Benchmark unchanged at 120/124 across all of the above, stereochemistry 11/11.

## Ring N-oxides in substituent position

D-024, the last open severity-A defect.  `[CH2+]c1cc[n+]([O-])cc1` came out as
`(pyridin-4-yl)methan-1-ylium 1-oxide`, which OPSIN cannot parse.

Additive nomenclature produces a TWO-WORD name, and a substituent has to end
in `-yl` so its parent can attach to it -- there is nothing to attach to the
end of the word "oxide".  The additive check in `engine.py` fired regardless
of output form, so it wrapped a cation core.

The fix is one condition: **the additive path declines in SUBSTITUENT output
form.**  The substitutive path already knew how to render the ring --
`1-(oxido)pyridin-1-ium-4-yl` -- it was simply never reached, because additive
claimed the molecule first.  Standalone output is untouched, so
`pyridine 1-oxide`, `pyridine-4-carboxylate 1-oxide`,
`trimethylamine oxide` and `dimethyl sulfoxide` all keep the additive form
that is correct for them.

With that in place the simple-carbon classifier no longer needs to refuse a
ring-embedded charge-separated group, so the guard added for D-018 is gone
again.  The obstacle was never the charge; it was the two-word name.

Two cheaper routes were tried first and both were wrong, which is why they are
recorded in `KNOWN_LIMITATIONS.md`: a curated ring entry keyed on the N-oxide
ring is dead data (the additive path strips the oxide before ring lookup), and
composing the name from parts means reimplementing substituent assembly for
one molecular shape.

Benchmark unchanged at 163/165 -- D-024 is not in the corpus, so this one is
verified by the defect table rather than by the score.

**The severity-A open list is now empty.**

## Poly-N-substituted guanidinium

D-025.  Guanidinium with more than one N-substituent was declined by the
classifier and fell through to the neutralizer, so `CNC(NC)=[NH2+]` came out
as `1-imino-N,N'-dimethylmethane-1,1-diamine` with the charge gone.

Guanidine numbers the charged (imino) nitrogen **2** and the two amino
nitrogens 1 and 3.  Lowest locants go to the more heavily substituted amino
nitrogen, which is what makes `CNC(=[NH2+])N(C)C` `1,1,3-trimethylguanidinium`
rather than `1,3,3-`.  Substituents are carved out, named as prefixes by the
engine, grouped by name, and emitted with multiplicity and alphabetical order:

  CNC(NC)=[NH2+]      -> 1,3-dimethylguanidinium
  CN(C)C(N)=[NH2+]    -> 1,1-dimethylguanidinium
  CNC(=[NH2+])N(C)C   -> 1,1,3-trimethylguanidinium
  CNC(N)=[NH+]C       -> 1,2-dimethylguanidinium
  CCNC(=[NH2+])NC     -> 1-ethyl-3-methylguanidinium

A lone substituent keeps the locant-free form (`methylguanidinium`): 1 and 3
are equivalent when only one is substituted, so it is unambiguous.

D-024 -- a ring N-oxide in substituent position -- remains open and is now
characterised in `KNOWN_LIMITATIONS.md`, including the two cheaper fixes that
were tried and rejected.

## The last five open severity-A defects

Cleared the open list. Each had a different cause, and two of them turned out
to be one cause shared.

* **D-013, D-018 — the all-carbon gate.** `_classify_simple_carbon_charge`
  required EVERY atom to be carbon, far stronger than its own justification:
  the heteroatom motifs it exists to protect (acylium, iminium, amidinium) all
  have the heteroatom bonded directly to the charged atom, so checking the
  charged atom's own NEIGHBOURS suffices. The stronger form left any charge on
  a hetero-containing skeleton unclaimed, and unclaimed means neutralized --
  `[CH2+]c1ccncc1` came out as `4-methylpyridine`. Relaxing it also fixed the
  furyl, methoxy and hydroxy carbocations for free.

  Charge-separated groups elsewhere (nitro, azido) are now claimed rather than
  refused: they carry no net charge and are ordinary prefixes, but the coverage
  gate needs them accounted for. They must be OUTSIDE a ring -- a ring-embedded
  one makes the parent an additive two-word name (`pyridine 1-oxide`) that
  nothing can be spliced onto, which is D-024.

  Formylium is curated rather than classified: `_classify_acylium` demands no
  hydrogen on the `[C+]` and a single-bonded R, and the R=H member has one H
  and no R. Widening that pattern for a one-member family buys nothing.

* **D-015 — azolides.** Worse than dropping the charge: the plan search MOVED
  it, naming pyrrolide `1H-pyrrol-2-ide` with the charge on a ring carbon. The
  ring-anion classifier now covers nitrogen. The trap was the neutralization
  probe -- an aromatic ring N needs its hydrogen stated EXPLICITLY or the ring
  will not kekulize, and the failure presented as "not an aromatic ring anion",
  silently skipping the whole family. Imidazolide, tetrazolide and pyrazolide
  came along with it, moving from Hantzsch-Widman stems to retained PINs.

* **D-019 — diazoalkane ylides.** Net-neutral but carrying both a carbanion
  and a diazonium; `_classify_diazonium` claimed only the two nitrogens, so the
  coverage gate refused the molecule. Named as the carbanion's own `-ide` name
  plus `yldiazonium`, which delegates parent selection and numbering to the
  renderer that already gets them right. The attachment locant has to be
  restated -- `propan-2-idyl` lets OPSIN default the attachment to C1, giving a
  different molecule -- hence `propan-2-id-2-yldiazonium`.

* **D-020 — N-substituted guanidinium.** One substituent is named as a prefix
  on `guanidinium`. Two or more are declined rather than half-named (D-025),
  because the locants would have to be assigned across the guanidine skeleton.

Benchmark 162/165 -> **163/165**, diazomethane `no_prediction -> equivalent`.
Zero wrong structures, zero refusals, zero unparsable names: the only two
failures left are tautomers, and those are not errors.

## The pyrazole stem in the partially-saturated path

D-023, severity B: right molecule, wrong ring stem. With no curated entry for
the partially-saturated 1,2-diazole ring, naming fell through to
Hantzsch-Widman, which spells it `1,2-diazole` — so 2-pyrazoline came out as
`4,5-dihydro-1H-1,2-diazole`. `pyrazole` is a retained ring name and the PIN
(P-25.2.1).

Only pyrazole was affected, which is worth knowing before assuming the hydro
path is broken generally. Imidazole and pyrrole already have curated
partially-saturated entries (`4,5-dihydro-1H-imidazole`,
`2,3-dihydro-1H-pyrrole`), and oxazole and thiazole get away without one
because their Hantzsch-Widman names — `1,3-oxazole`, `1,3-thiazole` — ARE the
preferred forms. Pyrazole is the only 5-ring in that set whose HW name differs
from its PIN, so it was the only one the gap could bite. Aromatic pyrazole was
never affected.

Two curated ring entries added beside the imidazoline one they mirror, with
`atom_locants` derived by OPSIN chloro-probing exactly as that entry documents.
For `4,5-dihydro-1H-pyrazole` locant 2 cannot be probed — it is the `=N-`, and
chlorinating it saturates the ring, so `2-chloro-…` resolves to pyrazolidine
instead; it is the one remaining atom and the one remaining locant.

This propagates through the whole pyrazolone family fixed in D-022: the
benchmark row is now `…-5-oxo-4,5-dihydro-1H-pyrazol-4-yl…`, and the edaravone
core is `3-methyl-1-phenyl-4,5-dihydro-1H-pyrazol-5-one`.

Knock-on, kept deliberately rather than worked around: a curated entry for the
2,3-dihydro-1H-pyrazole skeleton outranks the pre-composed `4-pyrazolone`
stem, so that ring now takes the systematic `4,5-dihydro-1H-pyrazol-4-one`.
That is the same treatment `5-pyrazolone` received in D-022 for being
semi-systematic rather than a PIN, so both pyrazolone stems now behave
consistently. Round-trip verified on both gates.

Benchmark unchanged at 162/165 — as expected for a severity-B fix, since both
forms denote the same molecule.

## Pre-composed retained rings in substituent position

D-022, severity A, and the last wrong structure in the corpus.

`5-pyrazolone` encodes C4's saturation only by convention. Put the ring in
substituent position and the name becomes `…-5-pyrazolon-4-yl`, which removes
the very hydrogen that made C4 sp3 — OPSIN then re-reads the whole ring as its
aromatic tautomer, a different species. Every senior characteristic group that
pushes the ring into substituent position hit it: amide, carboxylic acid,
nitrile. Only the benchmark's one pyrazolone row made it visible.

The retained lookup cannot detect this on its own, and that is worth recording
for whoever meets the shape again: `try_retained_name(ring_system, mol)`
receives the CARVED fragment, which is byte-identical to the standalone
molecule, and neither it nor the plan scorer in `strategy.py` is told the
output form. There is no structural signal to test.

What made a contained fix possible is that `5-pyrazolone` is semi-systematic
rather than a PIN — the PIN is the systematic `2,4-dihydro-3H-pyrazol-3-one`
form — so the engine's existing `_DATAFILE_PIN_INELIGIBLE_NAMES` gate is the
right home for it, next to tetralin/indan/chroman/isochroman. Declining the
stem outright sidesteps the missing context: the systematic path states the
saturation explicitly and is correct in BOTH positions.

That gate turned out to be wired into only one of the two branches that read
`_smiles_to_record`. The oxo fallback — the branch that matches rings keeping
an exocyclic =O, which is exactly where the pyrazolone family arrives — never
consulted it. Both branches now do.

Benchmark 161/165 -> **162/165**, and the wrong_structure count reaches
**zero**: every row the engine still answers, it answers with a name that
denotes the molecule it was given. The three remaining failures are two
tautomers and one refusal.

Knock-on worth stating: the systematic path spells the ring `1,2-diazole`
(Hantzsch-Widman) where `pyrazole` is the retained PIN. That is severity B,
pre-existing, and independent of this change — the hydro path already emitted
it — but routing the pyrazolone family through that path makes it far more
visible. Recorded in `KNOWN_LIMITATIONS.md`.

## Azide

D-016, severity A. `[N-]=[N+]=[N-]` named as `diiminoazanium`, which denotes
`N=[N+]=N` — a **cation**. The same one name came out for the azide anion
(q=−1) *and* for its conjugate acid HN3 (q=0), so a single confident answer
covered three different species and matched none of them.

No classifier claimed the N3 chain, so the plan search invented something.
Azide belongs with the other retained pseudohalides in the curated inorganic
table — cyanide, thiocyanate, cyanate, isocyanate, isothiocyanate are all
there — and simply was not. Two entries added: `azide` and, for the conjugate
acid, `hydrogen azide` (the PIN; OPSIN also accepts the retained "hydrazoic
acid").

The salt path inherited the fix for free: `[Na+].[N-]=[N+]=[N-]` was
`sodium diiminoazanium` and is now `sodium azide`. Organic azides were never
affected — `azidoethane` and `azidobenzene` go through the `azido` substituent
prefix, a separate path that was always correct.

Benchmark 160/165 -> **161/165**; polycharged 11/12 -> 12/12, which makes all
four charged-species categories perfect. One wrong structure now remains in
the whole 165-molecule corpus.

## Aromatic ring carbanions and guanidinium

Two more severity-A defects, both surfaced by the extended corpus.

* **D-003, aromatic ring carbanion.** `c1ccc[c-]c1` named as `cyclohexane`,
  losing the charge AND the aromaticity. `_classify_simple_carbon_charge`
  refuses an aromatic charged atom on purpose — a ring carbanion needs the
  ring parent's numbering, not a chain's — and nothing else claimed it.
  `_classify_aromatic_ring_anion` now does, emitting the plain `"ide"` hint so
  the existing renderer composes the name from the ring parent and the
  engine's own substituent numbering: `benzen-1-ide`, and it generalises to
  `naphthalen-1-ide`, `naphthalen-2-ide`, `pyridin-2-ide`, `pyridin-3-ide`.

  The gate took three attempts, and the two rejected ones are worth recording
  because they look sufficient. A **radical** test misses `[cH-]1cccc1`, which
  is closed-shell. "No hydrogen on the charged carbon" misses
  `Clc1ccc[c-]1Cl`, where a chlorine occupies the position rather than a
  proton having left it — and that arrives here as a lone fragment of a
  ferrocene salt, so it is not hypothetical. The gate that works is the one
  that matches the chemistry: **neutralize the site and check the ring is
  still aromatic.** Benzenide is a sigma carbanion, so putting the hydrogen
  back gives benzene; cyclopentadienide is a delocalised pi anion, so putting
  it back gives cyclopenta-1,3-diene, which is not aromatic and belongs to the
  retained-name path.

* **D-004, guanidinium.** `[NH2+]=C(N)N` named as
  `iminomethane-1,1-diamine`. `_classify_amidinium` requires the third
  substituent on the central carbon to be a CARBON, so guanidinium — whose
  third substituent is another amino nitrogen — fell through to the
  neutralizer. `guanidine` is a retained functional parent (P-66.4.1.2.1.2)
  and `guanidinium` its retained cation (P-73.1), so the name is emitted
  directly. Scope is the unsubstituted parent; `methylguanidinium` is recorded
  as D-020 rather than half-claimed, because with the refusal guard in place a
  classifier that claims what it cannot render raises instead of mis-naming.

`_splice_alkane_suffix` now elides a trailing `e` from any parent, not only
`-ane`: `ylium` and `ide` are vowel-initial, so `benzene` + `ide` is
`benzen-1-ide`. OPSIN accepts the unelided form too, but the elided one is the
PIN.

Benchmark 158/165 -> **160/165**; carbanion 7/8 -> 8/8, onium_ion 8/9 -> 9/9.

## The neutralizer fall-through now refuses, selectively

Decided on measurement rather than principle. Over the benchmark corpus plus
the 69-probe sweep (193 molecules), `render_failed` occurred 0 times and
`partial_claim` once, while `unclaimed` occurred 35 times and was almost
always a molecule some other path names correctly.

So the first two raise and the third does not. A classifier that engaged with
a molecule and then could not finish can only produce a name for a different
molecule, because the coverage gate has already established which charges are
claimed. `unclaimed`, by contrast, is this module declining business that
belongs to the retained-ring path and friends — pyridinium, sulfonium,
betaine, nitrobenzene, phenylium.

Visible effect: `name_smiles("[CH2-][N+]#N")` raises instead of returning
`(azanylidyne)(methyl)azanium`, which was the methyldiazonium **cation** —
an invented hydrogen and a charge that is not in the input. On the benchmark
diazomethane moved `wrong_structure -> no_prediction`, so the score is
unchanged; the difference is that one of those two is honest.

## Indicated hydrogen survives the ring table (D-026)

The ring-table entry for `c1cn[nH]n1` was labelled `1H-1,2,3-triazole`, which
is the other tautomer — OPSIN parses `1H-` to `c1c[nH]nn1` — and the 1H form
had no entry at all. Both inputs therefore came back named as the 1H
structure, discarding the indicated hydrogen the caller supplied. A plain data
mislabel, not an algorithm defect: the 1,2,4-triazole and tetrazole entries
sitting beside it already distinguished their tautomers correctly.

Probing all 13 tautomer-sensitive azoles in the tables found no second case.
The purine family still normalises to `9H-purine` on purpose (see
`KNOWN_LIMITATIONS.md`); that is the only remaining place where an input
tautomer is not preserved.

This also corrects a claim made earlier in this branch. The two standing
benchmark failures were described as "tautomers, not errors" — true of
metformin, false of the triazole, where the engine really was substituting a
different structure. The mistake came from reading a matching InChIKey as
proof of correctness when InChI cannot distinguish mobile hydrogens at all.

## Benchmark corpus extended to 181

The last three fixes (D-024 ring N-oxide substituents, D-025 poly-N-substituted
guanidinium, D-026 tautomers) all had to be verified against the defect table
rather than the score, because the corpus contained nothing from those
families. Added 16 rows — `n_oxide` (6), `guanidinium` (5), `tautomer` (5) —
so those paths are now measured on every run.

Re-running the **unmodified upstream** engine against the extended corpus shows how
much each category actually discriminates, which is not uniform:
`guanidinium` 0/5 and `n_oxide` 4/6 then, both 100% now — those rows catch
their defects outright. `tautomer` scores 5/5 *both* times, because the
upstream engine emitted the bare name `1,2,3-triazole` for the 1H input
and OPSIN resolves a bare name to 1H, so it round-tripped by luck. D-026 is
caught by the pre-existing `heterocycle` row (the 2H form), not by the new
category; the new rows guard the 1,2,4-triazole and tetrazole pairs that were
already correct. Worth stating plainly: adding rows to a corpus does not by
itself mean the corpus can see the defect they were added for.

## 2026-09-17 - substituent naming: stereo, order, locants

Three defects, all in SUBSTITUENTS, all from one user report (a fentanyl and
three MPMI tryptamines). None was visible to an OPSIN round-trip gate: two
produce a valid name for the right molecule, and the third produces a name
OPSIN parses perfectly into the wrong enantiomer.

* **D-027 - a descriptor recomputed on the carved fragment.** Carving replaces
  the cut side with H, which reorders CIP priorities at any centre or double
  bond whose ranking depended on that side. The first carve already inherited
  the parent's ATOM descriptors (`_ParentCIPCode`); a NESTED carve started from
  the first fragment and recomputed there, and bonds never inherited at all.
  Measured on `CN1CCC[C@@H]1Cc1c[nH]c2ccccc12`, an R centre: carve 1 inherited
  R, carve 2 recomputed S from `C[C@H]1CCCN1C` (where the indolyl side is
  already an H, so the exocyclic carbon is CH3 and ranks below the ring CH2),
  and the name said `(5S)`. Every E/Z measured inside a substituent was
  inverted: `C/C=C(/C)c1ccc(cc1)C(=O)O` is Z and was named
  `4-[(2E)-but-2-en-2-yl]benzoic acid`.

  `perception/extraction._context_cip_maps` now reads each atom's and bond's
  descriptor as it holds in the molecule being named, inherited beating
  recomputed, and `_stamp_context_cip` copies both through the `GetMolFrags`
  map after checking it is injective and element-preserving.
  `StereoAnalysis._detect_double_bond` prefers an inherited E/Z the way the
  tetrahedral branch already preferred an inherited R/S.

* **D-028 - prefixes cited out of alphanumerical order.** `derive_sort_name`
  stripped only the outermost bracket and the leading locant, so a nested
  bracket reached the key - and `(` and `[` sort before every letter, which
  cites every compound prefix first:
  `N-[1-(2-phenylethyl)piperidin-4-yl]-N-phenylacetamide` for acetyl fentanyl,
  where P-14.5.2 puts `phenyl` first. It also stripped any leading `di`/`tri`,
  filing `dimethylamino` under m (`2-ethyl-4-(dimethylamino)benzoic acid`) and
  `diazenyl` under a.

  The key is now the letters of the complete name, with locants, indicated
  hydrogen, italic heteroatom locants, stereodescriptors, the lambda
  convention and `tert`/`sec` removed at every depth, and a leading multiplier
  removed only where it multiplies (`bis(` before a bracket, `di` before a
  SIMPLE prefix). Six other places sorted raw name strings - three copies of
  the urea/sulfamide/guanidine first-alpha helper, the ester and phosphite
  class words, two anhydride paths and the acetamido handcraft - and all now
  read that one key. `tests/test_assembly.py` carries a table of
  display name -> exact key -> ordering, with the P-number for each rule.

* **D-029 - a heterocyclyl free valence numbered by plan order.** P-31.1.4
  numbers a ring substituent by heteroatoms (b), indicated hydrogen (c), then
  the FREE VALENCE (d), ahead of the ene ending (e) and every detachable
  prefix (f). The free valence was scored nowhere: the carbon-attached
  heterocycle branch of `_compute_numberings` yielded every heteroatom-legal
  numbering and left the choice to `IUPACCanonical._numbering_score`, whose
  bands are heteroatoms, suffixes, unsaturation and prefixes. So the two N=1
  directions of 1-methylpyrrolidine tied at -0.4101 and plan order decided -
  and since the carved fragment's C2 and C5 are symmetry-equivalent, which one
  was the attachment depended on the input's atom order. Hence
  `(1-methylpyrrolidin-5-yl)methanol`, while the same ring in
  `4-(1-methylpyrrolidin-2-yl)benzoic acid` came out right. With the free
  valence unscored the prefix band decided instead:
  `4-(1,2-dimethylpyrrolidin-5-yl)benzoic acid`.

  `engine._lowest_free_valence_numberings` keeps the heteroatom-optimal
  numberings and, among them, those giving the free valences the lowest
  locants, so the answer no longer depends on how a tie is broken. The bridged
  (von Baeyer) branch above solves the same gap by generation order and is
  left alone.

  Three more instances turned up while writing the regression table, each
  measured against the pre-fix engine rather than assumed unchanged:
  `4-methylpiperidin-6-yl`, `2-methylfuran-5-yl`, and a PINNED row -
  sulfolene, now `sulfol-3-en-2-yl`. Both sulfolene names round-trip on
  canonical SMILES and InChIKey, and P-31.1.4 ranks the free valence above the
  `ene` ending, so the new answer is correct and the pin was wrong.

* **Structural perception, which is not naming.** A new `structural_groups`
  table in `data/functional_groups.json` holds ring amines
  (`ring_tertiary_amine`, `ring_secondary_amine`) and the aromatic N-H, for
  consumers that want the CHEMIST's sense of "functional group" rather than
  the nomenclature one. They are matched in their own pass and reachable only
  through `FGDetection.structural_features`: deliberately NOT part of
  `detected_fgs`, because everything there becomes a suffix or a prefix, and a
  ring nitrogen added to it would put `amino` into piperidine's name. No name
  changed - verified over a 187-molecule corpus.

Measured on that corpus, scored by OPSIN round trip on canonical SMILES and
InChIKey: **184/187 before (82 exact, three names carrying a contradicted
stereodescriptor) -> 187/187 after (87 exact)**. Suite: 3,255 passing, 16
skipped, 0 failing.

## Naming round 3 (2026-09-17): preference, not just correctness

Every name before this round already round-tripped. That is the engine's
correctness criterion, and it is blind to PREFERENCE: `caffeine`,
`(trimethylsilan-yl)benzene` and `2-methoxynaphthalen-6-yl` all parse back
to the right molecule. Measured against the external corpus, 60 names
round-tripped while differing from the reference string, and this round
worked through them against the IUPAC Blue Book itself -- the 2013
recommendations with the 2022 corrections (`BlueBookV2.pdf`, sha256
`6b607a40...fb563f`), quoted verbatim in each entry below. The per-name
verdicts, with the quotation for each, live in OpenChem Studio at
`benchmarks/naming/adjudication.toml`; the two comments in this package
that cite that path refer to it.

**The main finding is about where defects live.** Four flagship cases
looked like one defect -- "the preference score picked the wrong
candidate" -- and were measured to sit in four different layers: the plan
BUDGET (a silicon parent never proposed), candidate GENERATION (no
candidate with two principal characteristic groups), PCG ASSIGNMENT (a ring
offered as a phenol, never as its ketone) and NUMBERING. Replacing the
float score with a lexicographic key would have fixed none of them; it is
still planned, as hygiene.

* **D-030, severity A: a bridged free valence named a constitutional
  isomer.** `CNC(C)CC12CC3CC(CC(C3)C1C1CCCCC1)C2` came out
  `1-(2-cyclohexyladamantan-5-yl)-N-methylpropan-2-amine`, a different
  InChIKey. Bridged rings kept an older branch that SORTED numberings and
  relied on "later-generated wins a tie"; any competing ring prefix broke
  the tie the wrong way. They now take the same free-valence FILTER as every
  other ring substituent (`_lowest_free_valence_numberings`, P-31.1.4.2.4).
  Found by a 40-row corpus selected without consulting the engine -- the
  curated corpus scored 187/187 both before and after. Fixing it exposed a
  second defect: `-yl` elision of locant 1 was decided by a different
  predicate from stem contraction, giving `adamantan-yl`. They are one
  decision now, `assembly.render_free_valence_suffix(stem_contracts=...)`.
* **D-031: a fused free valence where locant 1 is unreachable.** The
  fused-ring branch filtered for "attachment at 1" and, finding none on a
  fused ring, yielded every numbering, so the prefix band decided:
  `2-methoxynaphthalen-6-yl`. It now falls back to the lowest REACHABLE
  free-valence locant. Verified on naphthalene, anthracene, phenanthrene,
  quinoline and a substituted naphthalene.
* **D-032: the plan budget is two budgets.** A single 20-plan cap was spent
  on benzene's numbering variants before a second parent hypothesis was
  proposed, so `trimethyl(phenyl)silane` never had a silicon plan to rank.
  `_PlanBudget` separates a work bound (`_TOTAL_PLAN_BUDGET = 512`, measured
  maximum 138) from a per-hypothesis bound (`_PLANS_PER_HYPOTHESIS = 128`,
  measured maximum 96). Runtime did not move. Eight tests here pinned the
  pre-fix parent and were wrong: P-44.1.2 (p. 375) puts carbon LAST in the
  senior-atom order, "applied ... to choose between rings and chains", so
  `(silyl)benzene` becomes `phenylsilane`, and likewise for Bi, Pb and Sb.
* **D-033: a mononuclear parent does not cite locant 1** (P-29.2, p. 301):
  `trimethylazanium-1-yl` -> `trimethylazaniumyl`. Method (1) applies BY NAME
  to Si, Ge, Sn and Pb, so `trimethylsilan-1-yl` -> `trimethylsilyl`;
  phosphorus keeps `phosphanyl`, and a pinned row holds that line.
* **D-034: the nesting order of enclosing marks cycles.** P-16.5.4:
  `{[({[( )]})]}` -- there is no deepest level, so `{...{...}...}` becomes
  `(...{...}...)`. The parent-structure brackets of spiro, fusion and von
  Baeyer names and the parentheses of added hydrogen are exempt
  (P-16.5.4.1.1-2), as are the braces of superscript locants.
  `tests/test_namer_enclosing_marks.py` pins the book's own Fig. 1.3.
* **D-035: the isotope hyphen depends on what follows it** (P-82.2.1):
  `(1-2H)-methanol` -> `(1-2H)methanol`, but `(2-13C)-1H-indole` keeps its
  hyphen, because an indicated-hydrogen locant is a preceding locant.
* **D-036: a retained name is not automatically a preferred name.**
  `retained_pins` in `data/retained_names_expanded.json` asserted PIN status
  for 292 names while citing a rule for 31; 161 were harvested from OPSIN's
  name-to-structure dictionary, where presence means a name can be READ.
  Entries now carry `pin_status` (`PIN` / `RETAINED_NOT_PIN`; absent means
  unaudited) with `pin_evidence` and `pin_source`. Eighteen are audited,
  chosen from the entries a benchmark name reaches, and eight demoted:
  butyraldehyde, chloroform, isobutane, triethylamine, trimethylamine,
  camphor, caffeine, ibuprofen. `toluene` is audited as a PIN, because
  P-22.1.3 says so; a sweep demoting every retained name would have broken
  it. The other 274 behave exactly as before.

  **This changes `name_smiles` output for existing callers**: caffeine is
  now named systematically. `NamingStrategy.preferred_name_policy()`
  (`"PIN"` by default, or `"RETAINED_PREFERRED"`) decides whether a
  `RETAINED_NOT_PIN` name may take the preferred slot.
  `retained_name_policy()` never had a reader and is deprecated, with the
  mapping `ALWAYS_IF_AVAILABLE`/`PREFER` -> `RETAINED_PREFERRED`,
  `NEVER` -> `PIN` in its docstring. Two tests here asserted camphor was a
  PIN on a citation (P-66.6.3) that is about chalcogen analogues of
  aldehydes; camphor appears on two pages of the book, neither a
  retained-name table.
* **D-037: two ring names were not the preferred ones.** `isoxazole` ->
  `1,2-oxazole`, `isothiazole` -> `1,2-thiazole` (Table 2.2), `benzofuran` ->
  `1-benzofuran` (p. 208, which also gives `2-benzofuran`). Each was
  inconsistent with its neighbours in the same table.
* **`_opsin_can_parse` uses a private input file per call.** py2opsin's
  `tmp_fpath` defaults to one relative filename in the working directory,
  shared by every caller in the process and deleted in a `finally`.
  Measured with 16 concurrent calls: 5 correct on the shared path, 16 with a
  private one. A lost call reads as "cannot parse" and strips
  stereodescriptors that were fine; it was also the source of one to eight
  spurious test failures per suite run.
* **The stereo-validation cache no longer makes a missing JRE permanent.**
  `_STEREO_OPSIN_VALIDATION_CACHE` was keyed on the name alone, though its
  answer depends on `strip_modes`, and it cached inconclusive results -- so
  one call without Java kept stereodescriptors stripped for the life of the
  process. Keyed on `(name, strip_modes)`, and only a confirmed verdict is
  cached. `tests/test_namer_stereo_validation_cache.py` fails under the old
  behaviour.

New tests: `test_namer_plan_budget.py` (mutation-tested: collapsing every
plan into one bucket kills 6 of its 14 assertions),
`test_namer_enclosing_marks.py`, `test_namer_stereo_validation_cache.py`,
and 61 rows in `test_namer_known_defects.py` covering D-030 to D-037.

Measured on the external corpus, by OPSIN round trip on canonical SMILES and
InChIKey: **187/187 before and after, exact 87 -> 98**; on the 40-row
held-out corpus **39/40 -> 40/40**. Nothing structurally regressed at any
step. Exact agreement is with PubChem's generated string, which is itself
sometimes the non-preferred name -- fixing chloroform LOST an exact match.

## 2026-09-18 - naming round 4: preference by the book's criteria, and parents the engine could not reach

Every target was settled against BlueBookV2.pdf BEFORE its code changed
(in OpenChem Studio, `benchmarks/naming/adjudication.toml`, schema 2: each
rule quoted once with its page, rows referencing it), and every fix carries a `D-0xx` row set in
`tests/test_namer_known_defects.py` -- the defect, generalisation rows, a
converse, and a negative control -- mutation-checked by reverting the fix and
watching the rows go red. D-038 to D-082. The commit messages carry the
detail; this is the map.

**Evaluation discipline** (in OpenChem Studio's benchmark, not part of this
repository). The round-3 held-out set was spent as fix targets, so a fresh
40-row set was drawn by the same filter before anything in the round was
looked at, hashed and locked, and scored once, in aggregate, at the end.

**The comparator (stage 5, D-038, D-041).** Plans are ranked by a typed key.
`LegacyScoreKey` wrapped the old float and was proved decision-identical on
both corpora (0 names and 0 winning hypotheses changed) before
`NomenclaturePreferenceKey` replaced it: declared tiers built from the same
components the float summed. Every reorder was enumerated. It found the
alphanumerical tie-break keyed on FG TYPE (every carbon prefix was "z", so
P-14.5.1's own printed example came out wrong), numbering compared as locant
SUMS, cid19000's fusion candidate generated and outranked, and naming methods
ranked by guesswork where P-52.2.4.1 decides fusion versus von Baeyer.

**Numbering (D-039..D-041).** An `[nH]` pins the tautomer, not the orientation:
uniquifying the ring match dropped carbazole's mirror numbering (held-out
cid4000 was numbered from the far ring) and the `1H-` of indol-2-yl. P-14.3.4's
locant-1 omissions applied to the charged renderers.

**Retained parents and the registry (D-042..D-044).** Phenol, aniline,
benzaldehyde and acetaldehyde are substitutable PINs; the xylenes were ADDED.
The registry gains typed evidence and applicability fields, and
OpenChem Studio's registry audit FAILS CLOSED on impossible claims (a PIN backed
only by a parser, a whole-molecule-only name used as a parent). Eight names
were demoted, SUCCINIMIDE among them: this file had called it "a genuine PIN
with a correct P-66.2 citation"; the cited paragraph prints
`pyrrolidine-2,5-dione (PIN)` and forbids substituting succinimide.

**Principal groups (A5, D-045..D-058).** P-58.2's procedure for indicated,
added and hydro hydrogen, one planner instead of a guess per route (maleimide,
caffeine's `3,7-dihydro-1H-purine-2,6-dione`, pyrimidine-4,6(1H,5H)-dione);
15 hand-written ring-ketone entries corrected to it. Sulfonic esters by
functional class, C-bound N+ as the aminium suffix, P-44.1.1's count of
principal groups as its own tier (chloroquine's pentane-1,4-diamine), the
alcohol/phenol and amine families merged, diazonium as a suffix on its
carbon parent ("toluene-1-diazonium" did not parse).

**Serialization (A9, D-059..D-064).** Enclosing marks by form rather than an
allowlist; alkoxy contracted only for methoxy..butoxy and phenoxy
(`(acetyloxy)`, never acetoxy); locant order italic before numeral
(P-14.3.5 -- the code said the reverse and cited another rule); amido prefixes
by method (1); the one-substitutable-position rule; benzyl, anilino and
carbamoyl as preferred prefixes; carbamic acid's substituents unlocanted.

**Round 3's carry-overs (A10, D-065) and saturated rings (A8, D-066).**
Peroxides and disulfides by substitutive method (1); sulfoxides and sulfones
as `(methanesulfinyl)methane`; diacyl dihalides; the amine oxide's `N-`
locant. A saturated heteromonocycle takes its Hantzsch-Widman or retained
saturated name over a hydro form (P-31.1.4.2.4).

**Fused saturated parents (A7, D-067..D-074).** P-58.2 extended to
single-bonded suffixes and free valences, but only on atoms with no hydrogen
in the lowest-indicated-hydrogen mancude parent; P-14.3.4.5's omission of
hydro locants; anthrone; ring `carbo-` suffixes keep locant 1. A new
`ring_naming/fusion_locants.py` fills fusion carbons the ring table leaves
out (161 of 186 complete entries reproduced; the rest are table errors or
special numberings, which it declines). ELEVEN table locant maps were stored
inverted -- the dihydrofuran and dihydropyrrole named a different molecule --
and are fixed under a shape guard.

**Nitrogen cores and heteroatom centres (A6, D-075..D-082).** Substituted
hydrazides, amidines and guanidines take N/N'/N'' by role; one shared namer
for urea, thiourea, guanidine, carbamic acid and single-centre parents, with
a seniority gate and lowest-locant prime order; condensed guanidines as
imidodicarbonimidic diamides (metformin's relative had been a different
molecule); silanols, boron and pnictogen oxoacids, phosphanones (additive
"phosphane oxide" declined: P-74.2.1.4 makes the lambda5-phosphanone the PIN)
and diazenes. A primed numbered locant is `N'1`: OPSIN reads `N1'` as another
position, and held-out cid55000 came back a different molecule.

**Architecture (A11, A12).** One active strategy per call
(`strategy.active_strategy`, `using_strategy`), in the session cache key,
with every fallback `IUPACCanonical()` construction gone and a test
(`tests/test_namer_strategy_propagation.py`) that scans the package source
against a new one. The carve stamps each fragment atom with the atom it was
carved from (`extraction.fragment_origin`), and every `PrefixEntry` carries
that map as `atom_origin`, so a consumer can land a substituent's own
numbering on the molecule it named by composing the maps down the tree.

**Tests that were wrong, not the engine.** 25 of this suite's files changed
this round (433 lines in, 87 out, most of it new rows); every expectation
that MOVED was moved to the form the book prints on a cited page, and
several had been written from a code comment's claim rather than from the
book. This repository's own suite, standalone on RDKit 2026.03.6:
3,605 passed / 2 failed before the round, 4,580 passed / 2 failed after --
the same two `test_trindene_indicated_h` cases both times, an RDKit
2026.3 kekulisation change that reproduces on unmodified upstream. The
`eval/` round trip is 20/20 before and after, with no name changed.

Against OpenChem Studio's external corpora (read these as "nothing
measurable regressed", not as something reproducible here): 187/187 and
40/40 round trip throughout; PubChem-verbatim agreement 98 -> 101/187 and
14 -> 16/40 on the sets the round was tuned on, and 9 -> 15/40 on the fresh
held-out set. On rows with a settled Blue Book target the engine gives the
preferred name 28/30 and 14/16 times; PubChem's own string, 15/30 and 5/16.
What is still open is in `KNOWN_LIMITATIONS.md`, "Open after naming round 4".

## Naming round 5

Nine stages on top of round 4, each measured against the same three corpora
before it was accepted. The two findings worth reading first are both WRONG
MOLECULES, because nothing else in this list can hurt a caller as much:
`H2N-C(=NH)-CH2CH2-COOH` was named `4-carbamimidoylbutanoic acid`, one carbon
too many, and an N-substituted ring amidine came out as
`4-(carbamimidoylmethyl)benzoic acid`. Both are fixed and pinned.

**An atom-ownership invariant on the semantic tree** (`ownership.py`). Every
heavy atom of the named component must be owned exactly once by a tree node,
or be classified as an allowed non-owned entity with a reason. It runs before
serialization and never by parsing the emitted string. Set
`IUPAC_NAMER_OWNERSHIP=strict` to raise instead of recording. It caught three
defects during the round that no round trip could see, and its own blind spot
is recorded in `KNOWN_LIMITATIONS.md`: a prefix's CLAIMED atoms are not the
atoms its NAME denotes.

**General fusion nomenclature, P-25.3** (`ring_naming/fusion_general.py`,
`ring_naming/fusion_orientation.py`). A fused system with no retained name is
drawn as the book draws it (every permitted ring shape as the compass
directions its sides face) and numbered from that drawing. 78 of the book's 79
in-class P-25 examples are exact end to end; 46 out-of-class cases refuse with
a stated reason rather than emitting a partial name. The numbering agrees with
OPSIN's on every in-class example that can be probed, and on 40 common drug
scaffolds.

**Multiplicative names** (`multiplicative.py`): bis-guanidines,
methylenebis(phosphonic acid), N',N'''-methylenediacetohydrazide, and 22 of
the book's P-15.3/P-51.3 preferred names exact.

**Parents the engine could not reach**: hydrazine as a parent hydride
(`hydrazinecarboxamide`), N-substituted nitrogen oxoacids
(`N-methylsulfamic acid`), oxamide, silicic acid, and a(ba)n chains
(`hexamethyldisiloxane`, `chlorodisiloxane`).

**A gate over the names harvested from OPSIN's dictionary.** The 1,824-name
vocabulary file and the 174 registry entries copied from it establish that a
name can be READ, which is not that IUPAC prefers it. Such a name is now
emitted only where the registry types it with a normative rule, so
`fluorouracil` and `tabun` no longer appear as whole-molecule names. A
converse test proves it is not a lexical blacklist: the same spelling is still
produced wherever the engine's own rules construct it.

**Principal-group seniority and assignment**: urea ranks below the amides
(P-66.1.6.1.1.5), a chain-terminal amidine is amino + imino, a silanol counts
same-class groups instead of stepping aside, hydroxamic acids are N-hydroxy
amides, and an enol takes `-ol`.

**Numbering**: hydro-prefix locants now reach the preference key, so
`1,2,3,6-tetrahydropyridine-4-carboxylic acid` and `pyridin-1(2H)-yl` come out
as the book prints them. The orientations had tied, and the tie went to
whichever was generated first.

**Serialization**, five rules, each classified as lexical before it was built:
a one-stem `ylidene` prefix is not enclosed; elision does not apply between a
prefix and its parent; the first cited simple prefix on a mononuclear parent
goes bare; P-14.3.4.5 omits locants when every position of an all-carbon or
a(ba)n parent carries the same substituent; a contracted alkoxy prefix is
substitutable; and an acyclic hydrazide ends in `-hydrazide`, not
`-ohydrazide`.

**The retained-name registry is audited where it is usable.** Every entry the
gate lets through now carries a typed status with a quoted rule. Three entries
were REMOVED because they bound a name to the wrong stereoisomer
("L-proline" on D-proline, "L-threonine" on L-allothreonine, "L-isoleucine"
on L-alloisoleucine); two new tests check that every registry name denotes
its own structure, OPSIN being the independent reader, and that no name is
bound to two structures.

Measured at the end of the round on a corpus of 40 molecules drawn and frozen
before any of this work, never consulted while making it: every name parses
back to the structure it came from, 13 of the 40 matching PubChem's string
exactly. Agreement with an adjudicated preferred name rose on all three
tuning corpora (28/30 to 30/31, 14/16 to 17/18, and 20/23 where none had been
adjudicated before).

## Naming round 6: amides and esters of cyanic acid

Found by cross-checking the engine's perception against an independent
functional-group vocabulary, which showed methyl thiocyanate being PERCEIVED as
a plain nitrile. The molecules were right in every case; the names were not
the preferred ones. Measured before any change: `NC#N` was
`aminomethanenitrile` where the Blue Book retains `cyanamide (PIN)`
(P-66.1.6.2, PDF p. 663); `CCN(CC)C#N` was `(diethylamino)methanenitrile` for
`diethylcyanamide (PIN)`; `CC(C)SC#N` was
`[(propan-2-yl)sulfanyl]methanenitrile` for `propan-2-yl thiocyanate (PIN)`
(P-65.6.3.3.7.2.1, p. 629); `N#CSCCC(=O)O` was `3-(cyanosulfanyl)propanoic
acid` for `3-(thiocyanato)propanoic acid (PIN)` (P-65.2.2, p. 604).

Four changes, each pinned by D-094a-q in `tests/test_namer_known_defects.py`:

* **`cyanamide` is a registry entry typed PIN**, with the page quoted, and a
  substituted cyanamide is named by `_name_cyanamide_functional_parent` on the
  shared N-core builder, with no locant (the nitrogen is the only position, as
  in the book's own examples).
* **An O- or S-bonded cyano group is `cyanato` / `thiocyanato`**, not a nitrile.
  The nitrile pattern is blind to what the cyano carbon is bonded to, so it and
  the prefix-only groups overlapped; the engine logged "Unknown FG overlap ...
  Treating as ambiguity" and the nitrile won. Two subsumption entries in
  `perception/fg_detection.py` settle it, and
  `_name_cyanic_ester_functional_parent` names the ester (`methyl cyanate`,
  `propan-2-yl thiocyanate`, `S-ethyl 3-(thiocyanato)propanethioate`).
* **The prefixes** `cyanato` / `thiocyanato` replace `cyanooxy` /
  `cyanosulfanyl`, including in the ether-prefix branch, which builds its own
  name and had to be taught the same thing.
* **`thiocyanato` is enclosed as the book prints it, by an EXACT match**,
  because `isothiocyanato` contains the word and is printed bare (D-094p).

`tests/test_namer_cyanic_perception.py` pins the subsumption itself, because it
is invisible in names for most molecules and visible in perception. It reads
the engine's own `Perception`. (The repository this package is vendored into
keeps the same test against its annotation layer; that layer cannot exist
here, so this copy is written for the package rather than copied.)

The regression, held-out and second held-out corpora contain no cyano
compound, so no name in them changed. The third held-out set was not
consulted.

## Naming round 7: anions that carry another group, and the retained anion names

Found by putting a salt through the application, not by any corpus. A carboxylate or sulfonate beside a neutral
hydroxy, amino or sulfanyl group was named as if that group were the principal one: salicylate came out
`2-oxidooxomethylphenol` (OPSIN reads a different molecule) and lactate `1-oxido-1-oxopropan-2-ol` (which parses
back, and is wrong anyway). Nothing caught it because half of the affected names round-trip.

**The cause was a missing owner between two guards.** `_classify_acidic_anion` deferred every "mixed charged and
neutral" molecule to plan search, and plan search's `_carved_acid_anion_sites` excluded carboxylate because "the
dedicated path handles it". Each comment was true of its own half. `charge_perception.acid_anion_route(mol)` is now
the one function both routes ask, following P-41 (anions outrank acids; everything below an acid is a prefix):
`"classifier"` for a pure anion or one beside groups junior to an acid, `"carved"` for another neutral acid, a
nitro group or a net-negative zwitterion, `None` for a genuine other ion. The carved route takes its acid group from
perception on an index-preserving neutral view (`neutral_view`), and its principal-group restriction covers the whole
anion-variant family.

Also changed, each pinned by D-095 to D-099 in `tests/test_namer_known_defects.py` (fixes red before, with converses
that differ by reason):

* **A charge ledger for the functional-group route.** A zwitterion with one carboxylate and one NEUTRAL COOH was
  named as the dianion (a wrong molecule from a route that owned the site): in `ANION` mode the suffix now sits only
  on the charged instances of a type that has both. A net-negative zwitterion (glutamate and aspartate as drawn at
  pH 7) had no owner at all and is now carved (`2-azaniumylpentanedioate`).
* **The retained anion names the book prints** (P-72.2.2.2.2, pdf p. 808; P-103.2.4.2, p. 1047): `methoxide`,
  `ethoxide`, `propoxide`, `butoxide`, `tert-butoxide`, `phenoxide` and `glycinate`, in the curated whole-molecule
  table. `isopropoxide` is deliberately NOT added (the book prints `propan-2-olate`); the chiral amino acids are not
  added either (below).
* **A salt with two identical organic `-ate` anions takes a multiplying prefix**: `calcium diacetate`, and
  `bis(...)` for a prefixed anion. The older collapse stays narrow on purpose (`disulfate` is a different ion).
* **An amide anion is an acyl group on the parent anion `azanide`** (`acetylazanide`, p. 810), not `acetylamide`.

**Ownership is a checked property.** `perception/charge_ownership.py` compares three independent sources for every
charged atom: its structural class, the routes that would claim it (taken from the real predicates before the
first-claimer-wins de-duplication), and the route the engine actually took (`diagnostics.record_route`). The
verdicts are OWNED, HOLE, OVERLAP, INCONSISTENT and a declared UNSUPPORTED that carries its reason in words.
`tests/test_charge_ownership.py` pins the decision function, both failure shapes as mutations, and the declared
edges; its one test that sweeps the panel reads `tests/charged_panel_smiles.json` here (the panel itself, its
baseline and its adjudication live in the OpenChem Studio repository, with the test that pins them).

The instrumentation changes no result: `classify_charges(claims_out=...)` and `diagnostics.record_route` are inert,
and 0 of the 307 names in the regression, held-out and second and third held-out corpora changed at any stage.
`tests/test_namer_salt_multiplier.py` unit-tests the multiplier, because the D-rows go through whole salts.

## Naming round 8: polyacids, guanidines, protonated azoles, and what ordinary compounds showed

A planned part (polyacids, condensed guanidines and ureas, protonated azoles and cations, the round-5 open list, one carried-over wrong structure) and a
limitations pass whose defects came from naming ordinary compounds and reading the names. `tests/test_namer_known_defects.py` holds the evidence (D-100 to
D-129, each red before its fix, with converses that differ by reason); the vendored-suite figure and the benchmark measurements live in the OpenChem Studio
repository, which has the corpora and panels this package does not.

**Planned part.**

* **Polyacids.** A chain with three or more C-anchored suffix groups (P-65.1.2.2.1, p. 579) needs an exo-skeleton parent candidate the generator never
  offered: `2-hydroxypropane-1,2,3-tricarboxylic acid`, `pentane-1,3,5-tricarboxylic acid`, `ethane-1,1,2,2-tetracarboxylic acid`. The classifier route gained a
  site-level charge ledger (`_balance_the_charge_ledger`): a neutral `carboxy` word on the all-anion route is a deprotonated site, so it is `carboxylato`, and
  the citrate trianion is `2-hydroxypropane-1,2,3-tricarboxylate` (a wrong molecule before, two charges for three sites).
* **An isothiourea** whose demoted prefix was written `(aminosulfanylmethylidene)amino`, which OPSIN reads as another molecule, is enclosed as the book prints
  (`[amino(sulfanyl)methylidene]amino`, P-16.5.1.3.1): the enclosure rule applies to a substituent's own prefixes.
* **Condensed guanidines and ureas** (P-66.1.6.1.4, P-66.4.1.2): `diimidotricarbonimidic diamide`, `2-imidodicarbonic diamide`, the n >= 5 skeletal-replacement
  names (unsubstituted chains only, guarded), and the metforminium and biguanidium cations (a wrong molecule and a dication name for a monocation).
* **Protonated azoles and cations.** The ring carve keeps a protonated nitrogen a target (`1H-imidazol-3-ium`, `1H-benzimidazol-3-ium`, `1H-pyrazol-2-ium`,
  retained names for saturated protonated rings), a ring cation outranks every uncharged suffix, tetrazolium and N-oxide cations are right, and a net-positive
  component that holds a carboxylate (lysinium, histidinium) is named for its own ionisation state.
* **Imide parent, hydrazides, pseudoketones.** `N-acetylbenzamide`; an N'-acyl hydrazide and a hydrazide never ranked above an acid
  (`3-hydrazinyl-3-oxopropanoic acid`); a carbonyl on a ring, azo or silicon heteroatom is 'one' (P-64.3.2: `1-(piperidin-1-yl)propan-1-one`). The group
  definitions gained `context_indices`, a declared heteroatom root of a substituent that the group does not claim.

**Limitations pass, each a class no corpus contained.** The `e` of `ene`/`yne` elides before `amide` and `amine` (`prop-2-enamide`, `prop-2-en-1-amine`); an
alkoxy on a nitrogen is `methoxy`, not `methyloxy`; an amide or amine whose nitrogen carries an alkoxy is one (the Weinreb amide was named as an ester of
azinous acid); a carbonyl between two ring nitrogens is a pseudoketone (`bis(1H-imidazol-1-yl)methanone`); nitrate and nitrite esters and acyclic carbonic
diesters are named as esters (`pentyl nitrate`, `dimethyl carbonate`); an acyclic onium cation outranks the groups beside it; a mixed-class acid polyanion is owned
by the carved route (`4-sulfonatobenzoate`, `2-oxidobenzoate`); two adjacent acyclic ketones are a dione (`butane-2,3-dione`); the acyl prefix of a ring-nitrogen
amide is `piperidine-1-carbonyl`. Carbonyldiimidazole no longer crashes the multiplicative route.

**A dated decision.** A name that reads back as another TAUTOMER is no longer withheld by the application; that is an application-layer decision and changes
nothing here. The engine's own change is that an embedded `NAMING ERROR` is never returned as a name by the callers that use it.

`tests/test_namer_probe_shapes.py` and its fixture pin the names of 200 shapes no corpus contains, and read each back through OPSIN; the fork's variant does not
use the application's provider (see its docstring). `tests/test_namer_charge_ledger.py` and `tests/test_namer_exo_skeleton.py` unit-test the two W1 mechanisms.
The hand-written `tests/test_charge_ownership.py` pins two more routes (an olate beside an acid anion, and two acid classes, are now `carved`).

## Naming round 9: a source-backed battery first, 9 of 13 admitted findings fixed

Ported from a source-backed instruments stage (a Blue Book PDF harvest, an ordinary-compound battery, a frequency census) run BEFORE any fix, which
admitted 13 findings into a hash-frozen ledger and fixed 9 of them. Every fix has its own D-row (D-130 to D-138) and its own stage-comparison
against a 1129-row tuning population, checked before the commit.

* **Carbodiimide, wrong molecule fixed (PIN open).** The multiplicative-linker route checks for a C=O in the linker (P-15.3.3.2.2) but had nothing
  for a C=N: DCC named as a saturated bis-amine instead of the carbodiimide. `_linker_has_imine` declines the linker the same way the existing
  carbonyl check does; falls back to a structurally correct substitutive name. Reaching the printed PIN
  ("dicyclohexylmethanediimine", P-62.3.1.4) needs imine functional-group perception, which is empty for this structure in every context tried.
* **Carbamimidoyl locant, fixed.** Two carboximidamide groups at the SAME parent position collided onto one N/N' prime pair, because primes were
  assigned by chemical role alone; instances sharing a position are now ordered by anchor atom index, each later one shifted two more prime marks.
* **Naphthalene ring drop, wrong molecule fixed (no PIN claimed).** The multiplicative linker builder's shortest-path walk between two attachment
  atoms took the direct one-bond route across a fused ring, letting the whole OTHER ring pass an existing per-atom "is this atom part of some lone
  benzo ring" check and silently drop out of the name -- 4 of naphthalene's 10 ring atoms never appearing. `_fused_ring_count` declines whenever the
  linker's skeleton spans more than one SSSR ring; falls back to substitutive naming that keeps every ring atom.
* **Sulfinyl bromide, wrong molecule fixed -> honest failure.** A `{R}sulfonyl`/`{R}sulfinyl` substituent shortcut assumed the sulfur carries
  exactly one substituent beside its oxo oxygens; a hypervalent S(=O)(=N-)(Br)(N<) let it silently keep whichever neighbour it reached first and
  drop the rest. `_sulfonyl_sulfinyl_has_single_substituent` declines when S carries more than one non-oxo substituent; no route exists yet to
  NAME a sulfinimidoyl/sulfonimidoyl halide, so the result is an honest parse failure rather than a plausible wrong structure.
* **Phosphine oxide, wrong molecule fixed (no PIN claimed).** A P(V) phosphine oxide named as a trivalent P(III) "phosphanetriyl": the multiplicative
  linker builder strips a terminal oxo atom from the linker's skeleton before naming (needed so the oxo belongs to its own component), but nothing
  checked whether a P=O being stripped should have blocked the construction the way a C=O or C=N already can. `_linker_has_phosphine_oxide` mirrors
  the carbonyl/imine checks.
* **Peptide acyl naming, fixed (P-103.3.2).** A new module (`iupac_namer/perception/fg/peptide_acyl.py`) matches a dipeptide's two residues against a
  closed, stereo-matched table of the 20 proteinogenic amino acids and, on a match, emits the retained acyl-plus-parent form -- "glycylalanine",
  the book's own worked example, verbatim -- instead of fully systematic substitutive nomenclature. Also handles proline as the C-terminal residue
  (a tertiary amide, since proline's ring nitrogen is already secondary before acylation), a second base shape beyond the open-chain one. A residue
  with under-specified stereochemistry (only the alpha carbon given) correctly declines rather than guesses the diastereomer.
* **Three charge-anion classifiers, wrong molecules fixed.** An ethynediide dianion, a bicyclic phosphide anion (`1-phosphabicyclo[2.2.2]octan-1-uide`,
  P-73), and an imine-nitrogen anion (butaniminide) all previously dropped their charge to a neutral structure. The phosphide classifier is gated to
  RING phosphorus only: a first version also claimed an acyclic phosphide (`dimethylphosphide`, already named correctly through a different route)
  and rendered it wrong -- caught before landing, fixed with the ring gate.

**Not ported** (round 10's starting material, already diagnosed): a carbamimidate/oxime prefix-bracketing ambiguity; two dye-molecule ring-numbering
defects (a phenothiazine core and a spiro xanthene, different root causes, neither isolated to a fix yet); a polycarbocation needing the
multiplicative and charge-perception machinery to work together, which has no existing pattern to build from.

## Naming round 10: closing all 4 deferred items, each traced deeper than round 9's own diagnosis

Round 9's own diagnoses turned out to be starting points, not final answers, for three of the four items -- each traced further before any fix
was written, and each landed somewhere more precise than what round 9 recorded.

* **Phenothiazine-dye-locant, fixed.** Round 9 diagnosed this as a missing traditional-numbering table entry for phenothiazine. That diagnosis
  was incomplete -- adding the entry (verified correct against OPSIN as a structure oracle: `10-methyl-10H-phenothiazine` places the methyl on
  N, `phenothiazin-5-ium` protonates S) had zero effect on methylene blue's actual output. The real bug is a THIRD function,
  `retained_lookup.py`'s `_build_numbering_from_atom_locants`: its bond-generic substructure-match fallback (built to recover a curated ring's
  numbering when a substituent shifts the Kekule pattern) was gated to require every ring atom aromatic, including the N/S bridge -- non-aromatic
  on the isolated curated-key SMILES, but aromatic in methylene blue's actual extended-conjugation form. Fixed by relaxing the gate to "every
  CARBON aromatic". Engine now emits `[7-(dimethylamino)phenothiazin-3-ylidene]di(methyl)azanium chloride` for methylene blue, matching
  PubChem's own name verbatim. Phenoxazine shares the identical defect and fix, proven by direct testing.
* **A regression from this fix, caught and fixed before landing.** The widened gate also covered arsanthrene's As atoms, which (unlike
  phenothiazine's plain-bonded N/S) carry a genuinely structural explicit double bond in their curated key -- the standalone suite's own
  `test_arsanthrene_atom_locants_assign_peri_to_locant_1` caught it. Narrowed further: a non-aromatic heteroatom only gets the relaxation when
  it carries no explicit double bond.
* **Spiro-xanthene-dye-locant, fixed.** Round 9 correctly noted xanthene's own table entry is right, unlike phenothiazine's gap. What it hadn't
  isolated: the curated `atom_locants` entry for xanthene covered only 9 of its 14 real ring positions -- harmless for a bare or substituted
  xanthene, but `spiro.py`'s numbering-combination completeness gate never passed for fluorescein with 5 positions missing, so the combined
  numbering came back empty and substituent locants fell through to a generic, unprimed, out-of-range walk. Fixed by completing the table with
  the four fusion positions and the bridge oxygen's own locant, derived from this table's own bond topology against the already-verified
  numbering. Engine now emits `3',6'-dihydroxyspiro[1,3-dihydro-2-benzofuran-1,9'-xanthene]-3-one` for fluorescein, matching its real IUPAC
  name exactly -- including a second latent defect (the lactone's own locant) fixed as a side effect.
* **Charge-polycarbocation, the wrong-molecule half fixed.** `_classify_polycarbon_charge` already existed and already covered this exact
  multi-charged-carbon shape, but its guard checked the WHOLE MOLECULE for any aromatic atom and any non-single bond rather than the charged
  atoms' own. Narrowed to the charged atoms' scope; the classifier now engages and claims both charges, but no renderer composes a name for two
  independently-attached substituent cations on a shared aromatic parent yet. Per this engine's own "refusal guard" (a classifier that engages
  and cannot finish RAISES instead of falling through to the neutralizer), the engine now raises instead of emitting the wrong neutral name --
  converting the admitted wrong-molecule defect into a visible, honest failure.
* **Carbamimidate-oxime-swap, fixed.** Round 9 diagnosed "a prefix-bracketing ambiguity" and correctly deferred it for its regression risk.
  Diagnosis confirms the description exactly, and more: the engine's internal tree was right the whole time -- the wrong OUTPUT STRING left a
  trailing "methoxy" unbracketed after a preceding closing paren, and OPSIN's grammar read the adjacency as one nested substituent instead of
  two siblings, a real wrong molecule once parsed back despite the engine's own tree never being wrong. No existing enclosure rule covered a
  carbon-centered one-carbon STANDALONE parent with a non-leading "-oxy" prefix. Fixed by bracketing a non-leading "-oxy" simple prefix on any
  one-carbon chain parent, any output form. A second, independent instance of the exact same bug (a different prefix pair, a different parent)
  was found during diagnosis and fixed as the same side effect, pinning that the rule is general rather than a methanimine patch.

## Naming round 11: two fixes, two backlog rows already resolved, one re-diagnosed deeper

Re-verified every candidate directly against the current engine before admitting or dropping it -- the same discipline round 9 applied to its
own seed hypotheses. Two of five candidates this round looked at were already fixed by other rounds' general work, never reflected back into
`KNOWN_LIMITATIONS.md` until now.

* **Ketone-parent enclosure, fixed (D-143).** `assembly.py`'s `_assemble_substitutive` had two existing one-carbon-parent P-16.5.1.3.1 enclosure
  rules, but neither reached a one-carbon KETONE parent in STANDALONE form. `(morpholin-4-yl)phenylmethanone` left its second, simple "phenyl"
  prefix unbracketed. Fixed by mirroring the existing heteroatom-center block, scoped to a ketone's own suffix base_form ("one"). Severity C,
  not A -- OPSIN parses the unbracketed form too.
* **Carbamimidoyl N'/N,N split, fixed (D-091v, moved from open).** The existing "N'-substituted carbamimidoyl" special case required the amino
  N to be a bare, unsubstituted NH2, so a substituted amino N fell through to the generic recursive path, which OPSIN misreads as an azo-linked
  structure. Generalized to carve 0/1/2 substituents off the amino N too, gated to REQUIRE the imino N also substituted before firing: an
  amino-only-substituted, imino-bare fragment round-trips via OPSIN in isolation, but is genuinely APPEARS_AMBIGUOUS when the same shape
  attaches directly to a GUANIDINIUM parent instead of an ordinary one -- exactly the shape an existing metformin-cation fixture already chose
  the decomposed form for, on purpose. A first version without this gate regressed that fixture; caught by the standalone suite before commit,
  kept as a permanent non-regression test.

**Two backlog rows re-tested and found already resolved**, fixed as side effects of other rounds' own work and never reflected back into
`KNOWN_LIMITATIONS.md`: a ring-nitrogen acyl prefix on a ring/chain parent (now correctly "(piperidine-1-carbonyl)"-style), and the
citrate-trianion / biguanidium-dication charge-ledger pair (citrate now emits its printed PIN; the dication now correctly RAISES instead of
silently naming the wrong molecule).

**One row re-diagnosed to its actual root cause and re-deferred, not rushed.** A charged acid group inside a carved substituent still names
wrong (e.g. `sulfonato` emitted as the generic `oxidosulfonyl`), traced to a computed-but-never-threaded prefix value between two naming
layers -- broader than previously documented (affects a demoted carboxylate the same way, not only sulfonate) but not rushed given the shared
recursive substituent-naming code path several existing special cases (including this round's own carbamimidoyl fix) already sit beside.

Standalone suite: 6524 passed, 2 failed (the same pre-existing, RDKit-2026-dependent trindene indicated-hydrogen mismatches every prior sync
has recorded), 16 skipped, 14 xfailed.

## Naming round 12: a charged acid inside a substituent (D-144), and a triaged census signal

* **D-144, fixed.** A deprotonated carboxylate or sulfonate on a carved SUBSTITUENT fragment was named `2-oxido-2-oxoethyl` /
  `(oxidosulfonyl)methyl`; it is now `carboxylatomethyl` / `sulfonatomethyl` (P-65.6.2.3.1). The outer plan held the right typed FG, and the
  recursive call that names a carved fragment lost it through a fresh `Perception()`. `SubstitutivePath.generate_plans` now adds the same typed
  FGs for a SUBSTITUENT-form fragment from the fragment's own atoms (`_substituent_acid_anion_fgs`), for exactly the classes in
  `_ANIONIC_ACID_PREFIX`, and skips a group containing the attachment atom (a first version double-owned that atom on `D-121u`).
* **The fused-aromatic-ring-cation signal was triaged and not admitted:** 8 of 36 hits, plus 6 cationic ring systems outside the proxy, fail
  visibly (never as a wrong molecule) across about ten ring systems; the largest is 4 of 2000, under the floor. See `KNOWN_LIMITATIONS.md`,
  "Open after naming round 12".

Standalone suite (run under the main repository's interpreter, RDKit 2025.09.6, not the fork's own environment): 6560 passed, 0 failed,
14 xfailed.

## Naming round 13: a wrong ring locant on a heterocyclic substituent, and a demoted ketone that claimed its aryl carbon

* **D-145, fixed.** A monocyclic hetero ring's substituent is numbered with the senior heteroatom at locant 1 (Hantzsch-Widman): a lower combined
  heteroatom set had outranked it, so `N-(5-methyl-1,3,4-thiadiazol-3-yl)acetamide` is now `...-2-yl...` (`_lowest_free_valence_numberings`). Fused
  rings are unchanged.
* **D-146, D-147, fixed.** A ring with no `atom_locants` and a hard-coded locant in its curated substituent form no longer returns that locant for
  every attachment; benzodioxine also gets an `atom_locants` table.
* **D-148, fixed.** The curated `1,2,5-oxadiazole` row was keyed on 1,2,3-oxadiazole's SMILES; corrected, and named `1,2,5-oxadiazole` as the Blue
  Book gives it.
* **D-149, D-150, fixed.** A demoted ketone no longer claims its aryl or cycloalkyl carbon (`_compute_prefix_assignments` Pass 1):
  `4-(2-oxo-2-phenylethoxy)benzoic acid` is named instead of failing an ownership check, and `4-oxo-4-phenylbutanoic acid` is no longer named
  `3-carboxy-1-phenylpropan-1-one`.
* **D-151, open.** An ester of an acid that also carries a ring-nitrogen sulfonamide is named as an ester of the piperidine.

Standalone suite (run under the source repository's interpreter, RDKit 2025.09.6, not the fork's own environment): 6637 passed, 0 failed,
15 xfailed.

## Naming round 14: ring-nitrogen sulfonamides, ring cations, stereo on retained substituents, derived fused-ring tables

* **D-151, D-152, fixed.** A sulfonamide on a ring nitrogen is the prefix `<ring>-N-sulfonyl` (`4-(piperidine-1-sulfonyl)benzoic acid`, and its ester is an ester of the
  benzoic acid, not of the piperidine); the sulfamoyl prefix gives each N-substituent its own locant (`N-cyclohexyl-N-methylsulfamoyl`).
* **D-154 to D-157, fixed.** Ring cations with no name: fused cations that are not retained rings, a cation drawn on the bridgehead nitrogen, a quaternary bridgehead cation with a
  substituent (the curated quinolizidine nitrogen is locant 5, not `4a`), and a ring cation inside an acyl prefix that lost its charge. Tricyclic cations are unchanged.
* **D-158, D-159, fixed.** A stereocentre on a retained ring substituent (`[(2R)-oxolan-2-yl]methanol`) and on a spiro parent at a plain locant keeps its descriptor.
* **D-160, D-161, fixed.** Locant tables for heptacene to nonacene and the phenes (derived from the fusion numbering rules), octahydro-1H-indole, the biotin skeleton and
  `[1,2,4]triazolo[3,4-b][1,3]benzothiazole`.
* **D-153, fixed.** Tropone, tropolone and hinokitiol are cyclohepta-2,4,6-trien-1-ones, not saturated cycloheptanones.
* **D-162, open.** An N-hydroxy-N-alkyl amide inside an ester loses its N-substituent.

Standalone suite: see the pull request (run under the source repository's interpreter, RDKit 2025.09.6, not the fork's own environment).

## Naming round 15 (2026-09-24)

* **D-163, fixed: a nitro group on a RING nitrogen (a nitramine).** 1,3-Dinitro-1,3-diazetidine was named
  `oxido{3-[oxido(oxo)azaniumyl]-1,3-diazetidin-1-yl}(oxo)azanium`, and RDX, HMX, TNAZ, N-nitropyrrolidine and the N-nitro azoles the same way. The name reads
  back, so an OPSIN round trip cannot see the problem, and it is not the name anyone uses. The `nitro` pattern in `data/functional_groups.json` is
  `[NX3+](=O)([O-])[#6]`: it needs a carbon neighbour, so a nitro nitrogen on a ring nitrogen belonged to no group, and perception's acyclic-N+ azanium candidate
  (`perception/__init__.py`, +50, "yielded BEFORE rings") offered it as a one-atom parent that outranked the ring. A second `nitro` entry,
  `[NX3+](=O)([O-])[#7;R]`, claims it: `1,3-dinitro-1,3-diazetidine`, `1,3,5-trinitro-1,3,5-triazinane`, `1,3,5,7-tetranitro-1,3,5,7-tetraazocane`,
  `1,3,3-trinitroazetidine`, `1-nitropyrrolidine`, `4-nitromorpholine`, `1-nitro-1H-imidazole`, `1-nitro-1H-indole`. Widening the existing pattern to `[#6,#7]` was
  tried first and is WRONG: the attachment carbon of a prefix-only group is found by a plain `[#6]` atom in the SMARTS text (`perception/fg_detection.py`), and any
  other spelling silently drops the attachment context (`4-(nitromethyl)piperidine` stopped naming). Nine `D-163` rows join the known-defects table.
* **Open, not fixed:** an ACYCLIC N-nitro (a nitramide: `CN(C)[N+](=O)[O-]` is `(dimethylamino)(oxido)(oxo)azanium`) and N-nitroso (`CN(C=O)N=O`). Widening the nitro
  pattern to an acyclic nitrogen drops the amine nitrogen and names a different molecule (`nitromethane`).

Standalone suite: see the pull request.

## Naming round 16 (2026-09-25)

* **D-164 / D-165, fixed: a nitro or nitroso group on an ACYCLIC nitrogen.** Round 15 fixed the ring nitramines and recorded these open. `CN(C)[N+](=O)[O-]` was
  `(dimethylamino)(oxido)(oxo)azanium`, nitroguanidine `imino{[oxido(oxo)azaniumyl]amino}methanamine`, nitrourea `1-{[oxido(oxo)azaniumyl]amino}methanamide`, NDMA
  `1,1-dimethyl-2-oxohydrazine`, and `CC(=O)N(C)[N+](=O)[O-]` `N-methyl-N'-oxido-N'-oxoacetohydrazide`, which OPSIN cannot read; all but the last read back, so a round trip cannot
  see the problem. They are now `N-methyl-N-nitromethanamine`, `N-nitroguanidine`, `N-nitrourea`, `N-methyl-N-nitrosomethanamine` and `N-methyl-N-nitroacetamide`.
  Six changes, none sufficient alone. (1) `data/functional_groups.json`: `secondary_amine`/`tertiary_amine` and `secondary_amide`/`tertiary_amide` entries whose nitrogen REQUIRES a nitro
  (`$(N[NX3+](=O)[O-])`) or nitroso (`$(N[NX2]=O)`) neighbour by a recursive constraint; the neighbour is NOT an atom of the match (as a `context_indices` atom the nitro FG loses the
  deconfliction, as a match atom the amine owns it twice). (2) A `nitro` prefix group whose match is the nitro group's own three atoms; without it the nitro nitrogen is still
  offered as the azanium parent. (3) `engine.py`: `_SMALL_FRAGMENT_PREFIXES_BY_ATTACHMENT` gains `("O=[NH+][O-]", "N"): "nitro"` (the carve puts a hydrogen on the attachment
  nitrogen). (4) A heteroatom-chain (N-N) parent may not take an `-amine` suffix on its own nitrogen. (5)/(6) `_name_urea_functional_parent` and `_name_guanidine_functional_parent`
  refuse an N-N bond because that is a hydrazide; `_is_nitro_or_nitroso_nitrogen` exempts a nitro or nitroso nitrogen. Eighteen `D-164`/`D-165` rows join the known-defects table.
* **Open, not fixed:** nitramide itself (`N[N+](=O)[O-]`, no naming plan, D-166) and N-nitro and N-nitroso carbamates (`CCOC(=O)N[N+](=O)[O-]`, D-167).

Standalone suite: see the pull request.


## Naming round 17 (2026-09-25)

* **D-166 / D-167, fixed: nitramide and nitrous amide as PARENTS, and N-nitro / N-nitroso carbamates.** Round 16 named the plain nitramines and nitrosamines as the amine with a nitro or nitroso
  prefix and recorded that as not checked against the Blue Book. P-67.1.2.6.3 (pdf p. 708): "Preferred IUPAC names for amides and hydrazides of nitric and nitrous acids are now systematically
  based on nitric or nitrous amide and hydrazide, in accordance with the seniority order of classes rather than as nitro and nitroso amines; the latter names can be used in general
  nomenclature", and p. 709 prints `(chloromethyl)(methyl)nitramide (PIN)` beside `1-chloro-N-methyl-N-nitromethanamine`. So `CN(C)[N+](=O)[O-]` is now `dimethylnitramide`, NDMA `dimethylnitrous amide`,
  `N[N+](=O)[O-]` `nitramide` (it had no naming plan), `CCOC(=O)N[N+](=O)[O-]` `ethyl nitrocarbamate` and `CCOC(=O)N(C)N=O` `ethyl methyl(nitroso)carbamate`.
  Two changes. (1) `_name_nitramide_functional_parent`, built on `_name_n_core_parent` like the cyanamide and sulfamic acid routes: the one substitutable amino nitrogen takes its prefixes with no
  locant; it declines for a group of the amide class or above elsewhere, for a nitrogen on a carbon doubly bonded to N, O or S (an acyl, imidoyl or carbamoyl carbon), a cyano carbon, a hydrazine, a ring
  nitrogen and a second nitramide group. (2) `_build_carbamate_decomposition` took the nitro or nitroso nitrogen for a carbazate's second nitrogen and offered no functional-class plan; the predicate
  moves to `types.py` as `is_nitro_or_nitroso_nitrogen`. Rows `D-164a-d` and `D-165a-d` are retargeted to the PINs; `D-166a-h` and `D-167a-b` join the known-defects table.
  Measured in the vendoring repository (the fork has no frozen populations): census scan 0 of 2000 rows changed; 1712 reference structures, 3 names changed, each now equal to the name the book prints; the blind
  Blue Book held-out set, scored once in aggregate, exact 506 -> 510 with nothing worse.
* **Open, not fixed (D-168):** the `-NH-NO2` prefix is `nitramido` in the book (P-67.1.4.3.2, pdf p. 717) and `(nitroamino)` here, and `-NH-NO` is written without its parentheses
  (`4-nitrosoaminobenzoic acid`). Also not attempted: the nitric and nitrous hydrazides, and ethylenedinitramine (two nitramide groups, a multiplicative parent).

Standalone suite: see the pull request.


## Naming round 18 (2026-09-26)

* **D-168, fixed: the `-NH-NO2` and `-NH-NO` prefixes.** Where a nitramide is not the parent, P-67.1.4.3.2 (pdf p. 717) prints "-NH-NO2 nitramido (preselected prefix)" and "-NH-NO nitrosoamino
  (preselected prefix)". `OC(=O)c1ccc(N[N+](=O)[O-])cc1` was `4-(nitroamino)benzoic acid` and is `4-nitramidobenzoic acid`; `OC(=O)c1ccc(NN=O)cc1` was `4-nitrosoaminobenzoic acid` and is
  `4-(nitrosoamino)benzoic acid`; two of either multiply as `3,5-dinitramidobenzoic acid` and `3,5-bis(nitrosoamino)benzoic acid`. Three small changes: `assembly._preferred_prefix_spelling` maps the bare
  word `nitroamino` to `nitramido` (next to `phenylamino` -> `anilino`), with a matching case in `_name_heteroatom_fv_substituent` for the prefix inside an imino group; `nitrosoamino` leaves
  `_SIMPLE_PREFIXES` (it is a substituted amino group and a compound prefix); `nitramido` joins `_LEADING_PREFIX_WORDS`.
* **A round-17 guard tightened.** A hydrazone of nitramide (`C=N-NH-NO2`) had been named as a nitramide with an ylideneamino prefix; `_is_hydrazone_type_nitrogen` now declines, and the hydrazine name
  stays until the hydrazide route exists. Isocyanato and isothiocyanato still take the nitramide parent.
* Measured in the vendoring repository (the fork has no frozen populations): census scan 0 of 2000 rows changed; 1712 reference structures, 0 changed; the blind Blue Book held-out set, scored once in
  aggregate, identical to round 17. Rows `D-168a-g` join the known-defects table and each change was removed in turn to confirm one fails.
* **Open, not fixed (D-169):** the nitric and nitrous hydrazides (`nitric hydrazide`, `nitrous hydrazide`, `N'-benzylidenenitric hydrazide`), OPEN rows with OPSIN-verified targets.

Standalone suite: see the pull request.


## Naming round 19 (2026-09-26)

* **D-169, fixed: nitric and nitrous HYDRAZIDES as parents.** P-67.1.2.6.3 (pdf p. 708): "nitric hydrazide (I) and nitrous hydrazide (II) are preselected names used as parent structures for generation of
  preferred IUPAC names", and p. 709 prints `N'-hexylidenenitrous hydrazide (PIN)`. `O2N-NH-NH2` was `nitrohydrazine` and is `nitric hydrazide`; `ON-NH-NH2` was `1-amino-2-oxohydrazine` and is `nitrous hydrazide`;
  `CNN[N+](=O)[O-]` was `1-methyl-2-nitrohydrazine` and is `N'-methylnitric hydrazide` (N is the nitrogen that bears the nitro or nitroso group, N' the terminal one); a hydrazone is named with an N'-ylidene
  (`N'-(propan-2-ylidene)nitric hydrazide`); and a hydrazide outranks an alcohol. One new `_name_nitric_hydrazide_functional_parent` on `_name_n_core_parent` with fixed `N` / `N'` labels, and an
  `allow_ylidene` extension so a nitrogen can carry a double-bonded substituent. It declines for a hydrazide-class or senior group elsewhere, a carbon acid derivative next to the nitrogen or on the hydrazone
  carbon (an amidine, a guanidine, a hydrazonoyl halide), a triazane and a ring nitrogen. Rows `D-169a-k`, thirteen control rows and `D-168g` (its round-18 stopgap replaced) join the known-defects table.
  Measured in the vendoring repository (the fork has no frozen populations): census scan 0 rows changed class and 1 changed name, 1712 reference structures 0 changed, the blind Blue Book held-out set scored once in
  aggregate and identical to round 18; seven changes were each removed and a row failed.
* **Open, not fixed (D-170):** the substituent names of a hydrazone or hydrazine. The book prints `3-amino-3-hydrazinylidenepropanoic acid (PIN)` (p. 682) and `nitrosohydrazinylidene` (p. 717); the engine writes
  `3-amino-3-(aminoimino)propanoic acid` and `(R-aminoimino)` for the `=N-NH-R` family. OPEN rows `D-170a-c`.

Standalone suite: see the pull request.


## Naming round 20 (2026-09-26)

* **D-170, fixed: the SUBSTITUENT `hydrazinylidene`.** P-66.4.1.2 (pdf p. 682) prints `3-amino-3-hydrazinylidenepropanoic acid (PIN)` and p. 717 `nitrosohydrazinylidene (preselected prefix)`. The engine read every
  `=N-N(R)(R')` group as an imino group on an amino group, which OPSIN reads back correctly and which is not the name: `OC(=O)CC(N)=NN` was `3-amino-3-(aminoimino)propanoic acid` and is
  `3-amino-3-hydrazinylidenepropanoic acid`; `OC(=O)CC(C)=NNC` was `3-(methylaminoimino)butanoic acid` and is `3-(2-methylhydrazinylidene)butanoic acid`; an acyl hydrazone was `3-acetamidoiminobutanoic acid` and is
  `3-(2-acetylhydrazinylidene)butanoic acid`; round 18's stopgap `(nitramidoimino)acetic acid` is `(nitrohydrazinylidene)acetic acid`. One new `_hydrazinylidene_prefix` cites N2's substituents at 2, writes a lone nitro or
  nitroso group unlocanted as the book prints it, and leaves the bare group unenclosed; an azine, a triazane and a ring N2 keep the imino form. Rows `D-170a-m`, five control rows, and `D-168f` (its round-18 stopgap replaced)
  join the known-defects table. Measured in the vendoring repository (the fork has no frozen populations): census scan 0 rows changed class and 19 changed name (all this prefix, exact both times), 1712 reference structures 19
  changed (all read back, none unexpected), the blind Blue Book held-out set scored once in aggregate and identical to round 19; eight of nine guards were removed in turn and a row failed (the ninth is an equivalent mutant).
* **Open, not fixed:** hydrazones of carbon acid hydrazides (the book names the hydrazide, `N'-...-ylideneacetohydrazide`), an azine and a triazane on N2.

Standalone suite: see the pull request.


## Naming round 21 (2026-09-27)

* **D-173, fixed: the retained prefixes `benzyl`, `benzylidene`, `benzylidyne`, unenclosed and unsubstituted-only.** P-29.6.1 (pdf p. 312): "benzyl, benzylidene,
  benzylidyne are retained preferred prefixes, but are not to be substituted"; printed "2-benzylpyridine (PIN)". `benzyl` (bond order 1) was already right; this
  round adds `benzylidene`/`benzylidyne` (bond orders 2/3), and reaches two hand-built compound prefixes that bypass the usual spelling substitution entirely (so
  even plain `benzyl` needed a second fix there). A substituted one (ring or alpha) stays systematic, per the book's own `carboxy(4-carboxyphenyl)methylidene`
  example. Rows `D-173a-f` join the known-defects table; ten guards were each removed in turn and a row failed.
* **D-178, fixed: amides of the mononuclear halogen oxoacids, `R2N-X` and its `=O` homologues.** P-62.4 (pdf p. 528): "compounds such as R-NH-Cl, R-NH-NO, and
  R-NH-NO2 are now named as derivatives of amides" -- the same reclassification round 17 built for nitro/nitroso, extended to a halogen. `CCNCl` was
  `(chloroamino)ethane` and is `ethylhypochlorous amide` (the printed example); iodine alone climbs the oxidation ladder (`iodous amide`, `iodic amide`) because
  RDKit accepts a neutral tri- or pentavalent iodine but refuses the same shape for chlorine or bromine outright, so the book's own bromous-amide example is not
  reachable through this engine at all. Rows `D-178a-m`; ten guards were each removed in turn and a row failed.
* **Investigated, not fixed:** hydrazones of carbon-acid hydrazides (the FG-suffix SMARTS is too broad to touch narrowly), the azine/triazane/ring-N2 imino
  cases, the book's own `hydrazin-1-yl` inconsistency, cyanamide vs nitramide competing for one nitrogen, and ethylenedinitramine (a verified candidate PIN,
  `ethane-1,2-diylbis(nitramide)`, is now recorded, not yet implemented).

Measured in the vendoring repository (this fork has no frozen populations): census scan 0 rows changed class and 10 changed name (benzylidene family, exact both
times); 1712 reference structures 2 changed (one tuning row, one the r8 benzonitrilium reference structure itself), both reading back; the blind Blue Book
held-out set scored once in aggregate, `bluebook_frozen` exact rising 510 -> 511 (one row moved equivalent -> exact), every other bucket unchanged.

Standalone suite: see the pull request.


## Naming round 22 (2026-09-27)

* **D-171, fixed: hydrazones of a carbon-acid hydrazide are named on the hydrazide, with an N'-ylidene.** P-66.3.3 prints the same pattern round 19 built for the
  nitric/nitrous hydrazide, "N'-hexylidenenitrous hydrazide (PIN)". `CC(=O)NN=CCCCCC` was `1-acetyl-2-hexylidenehydrazine` and is
  `N'-hexylideneacetohydrazide`. The `fg:hydrazide` SMARTS required both nitrogens at `NX3` (three connections), which a hydrazone's terminal `=N-` (`NX2`,
  double-bonded to carbon) failed. The fix is one recursive clause on the terminal nitrogen, `$([NX2;!R]=[#6])`, restricted to a carbon partner so a genuine
  azo/triazene nitrogen is not mistaken for a hydrazone. Nothing downstream needed touching: the general "PCG N-substituents" machinery already carves
  N-substituents and renders a bond-order-2 one as an ylidene. Also fixes a hydrazide-vs-amine seniority bug the same shape exposed (a hydrazone carbon
  bearing two amino groups was naming an amine as parent over a class-12 hydrazide). Rows `D-171a-f` join the known-defects table; two guards were each
  removed in turn and a control row failed.
* **Also found, not fixed:** plain thiohydrazides (`CC(=S)NN` is `(1-thioxoethyl)hydrazine`, not `acetothiohydrazide`) are a separate, pre-existing defect --
  the `fg:hydrazide` SMARTS matches only a carbonyl oxygen, with no chalcogen-generic path.

Measured in the vendoring repository (this fork has no frozen populations): census scan 0 rows changed class and 40 changed name (all this pattern, the
family is common in drug-like corpora); 1712 reference structures 1 changed, reading back; the blind Blue Book held-out set scored once in aggregate and
identical to round 21.

Standalone suite: see the pull request.


## Naming round 23 (2026-09-27)

* **D-179, fixed: the chalcogen analogue thiohydrazide, `R-C(=S)-NH-NH2`.** P-66.3.4 (pdf p. 672) prints "propanethiohydrazide (PIN)" and
  "benzenecarbothiohydrazide (PIN)". `fg:hydrazide`'s SMARTS matched only a carbonyl oxygen, so a thiohydrazide was never recognized as the hydrazide
  class at all (`CC(=S)NN` was `(1-thioxoethyl)hydrazine`). One new `thiohydrazide` FG entry mirrors `hydrazide` exactly; three engine.py sites keyed
  on the literal string `"hydrazide"` also needed the new type name (N-substituent carving, N/N' role primes, the anchor-in-parent guard -- the last
  caught a WRONG STRUCTURE, a double-counted carbon, before it shipped). One preprocessing entry, added for symmetry, is verified dead behind the
  anchor guard for every shape tried. Rows `D-179a-h` join the known-defects table; nine guards removed in turn each failed a row for eight of nine.

Measured in the vendoring repository (this fork has no frozen populations): census and both frozen sets 0 changes (the family is rare); 1712 reference
structures 2 changed, both the book's own printed examples, reading back; nine guards removed in turn each failed a row for eight of nine.

Standalone suite: see the pull request.

## 2026-10-05 -- naming round 24 (D-180, D-181, D-182): morphinans, a heptalene template, and Java for the engine's own OPSIN checks

Started from one molecule the app refused (a 3,14-diacetoxy-4,5-epoxy-6-oxo morphinan) and a 45-molecule battery of drugs and natural products named through
the app's own path (`derived_name_for_structure`). Before: 21 exact, 24 shown with "does not express stereochemistry", 1 refused. After: 41 exact.

**D-182 (the largest, and in the APPLICATION that embeds this engine, not here): the app ran the engine without `java` on PATH.** The engine confirms stereo on a bridged or spiro parent by
parsing its own candidate name with OPSIN (`_validate_stereo_via_opsin`) and DROPS the descriptors when that fails. py2opsin shells out to a bare `java`, and the
app's managed JRE is on neither PATH nor JAVA_HOME, so every check failed and every bridged stereocentre was dropped: camphor came back `1,7,7-trimethylbicyclo[2.2.1]heptan-2-one`,
not `(1R,4R)-...`. The engine's own benchmarks and suites ran with Java on PATH, so none could see it. `naming_providers._java_on_path()` now wraps both engine
calls (`derived_name_for_structure`, `structure_annotation._name_ring_skeleton`). Mutation-checked: removing the wrapper fails `tests/test_derived_name_reaches_opsin.py`.

**D-181: the `heptalene` template was a 13-atom [8,7] skeleton** (`C1CCCC2CCCCCC2CC1`), so it never matched a real heptalene and fusion naming fell back to
`cyclohepta[7]annulene` as the parent: colchicine's core was `benzocyclohepta[7]annulene`, a name OPSIN reads as a different structure (the app withheld it). Now
`C1CCCCC2CCCCCC12`; colchicine is `N-[(7S)-1,2,3,10-tetramethoxy-9-oxo-5,6,7,9-tetrahydrobenzo[a]heptalen-7-yl]acetamide`. All 67 `POLYCYCLES` templates were then
checked against OPSIN's parse of their own name (atom count and ring sizes, skeleton isomorphism): no other mismatch. `tests/test_round24_polycycle_templates.py` pins the table.

**D-180: a retained parent MODIFIED by `didehydro` and an `epoxy` bridge.** P-13.8.1.1 (pdf p. 66) names morphine `4,5α-epoxy-17-methyl-7,8-didehydromorphinan-3,6α-diol`
on the retained parent `morphinan` (P-101.2). The retained lookup matched the saturated skeleton exactly, so levorphanol named and morphine, codeine, heroin,
hydromorphone, oxycodone, naloxone and thebaine fell to a von Baeyer pentacycle. New `ring_naming/retained_modified.py` (rank 45, like the methylenedioxy bridge):
strip at most one ether bridge, flatten ring double bonds into recorded `didehydro` locants, look the remainder up in the curated table, number by its `atom_locants`.
`epoxy` rides on a new `NamedParent.bridge_prefixes` and is alphabetized with the substituents by `_assemble_substitutive`, as the book cites it; `didehydro` is part of the
parent name. Only parents in `_MODIFIABLE` (morphinan) are eligible, because the book prints such a name for it.
Names are in `tests/test_round24_morphinan.py`, each read back through OPSIN with stereo.

**Measured.** Census (2000 rows): 1999 unchanged; one moved, a no-stereo 4,5-epoxymorphinan, von Baeyer name -> `1-bromo-4,5-epoxy-2-hydroxymorphinan-6-one`, which OPSIN reads
back with stereo the input lacks (exact -> same_connectivity, connectivity identical). Ref-compare 1712 structures, 0 names changed, 0 violations. Vendored suite passes.

**Left open (4 of 45).** atropine, scopolamine, galantamine and ibogaine are still shown with "does not express stereochemistry"; the cause was not diagnosed. The quaternary N-methyl morphinanium falls back to von Baeyer (charged systems are not eligible). A morphinan
N-oxide is named as an additive `17-oxide`, which OPSIN reads. The Blue Book also prints a furo-fused form for morphine; the epoxy form is used because OPSIN reads it back (the round-trip tests) and it is the book's own form for the demethyl example. Which of the two is the PIN was not settled.

## 2026-10-05 -- naming round 25 (D-183 to D-186): stereo kept on four natural products, and which ester of a polyester is the principal anion

Round 24 left two items open in `KNOWN_LIMITATIONS.md`; both were diagnosed first, and the four stereo losses turned out to have FOUR different causes, not one.

**D-183, atropine and scopolamine: a pseudoasymmetric descriptor poisoned the rest.** The engine writes `(1R,3r,5S)` (the lowercase `r` is P-91.2, stamped by `rdCIPLabeler`). OPSIN cannot read `r`/`s`, so
`_validate_stereo_via_opsin` rejected the candidate and its `bridged_or_spiro` mode stripped EVERY R/S, including the `1R,5S` OPSIN reads fine. New strip mode `pseudoasymmetric` (lowercase only) is tried first.
Both now keep what OPSIN can read: `(1R,5S)-8-methyl-8-azabicyclo[3.2.1]octan-3-yl 3-hydroxy-2-phenylpropanoate`. They still carry the "does not express stereochemistry" note, correctly: **tropine and pseudotropine
are the two C3 epimers and now share one name**, `(1R,5S)-8-methyl-8-azabicyclo[3.2.1]octan-3-ol`; the note is the only thing telling them apart. PubChem omits the pseudoasymmetric centre the same way.

**D-184, galantamine: the curated table had 8a and 12a swapped.** The entry's own comment says those two junctions were "deduced by topology", and only the probed locants were right. OPSIN settles it: `8a-chloro-...`
is a valency error (the quaternary carbon has no hydrogen), `12a-chloro-` lands on the aromatic carbon beside the CH2-N, and `(4aS,6R,8aS)-...-6-ol` reads as galantamine where the old `12aR` could not be parsed, so both
junction descriptors were stripped. Swapped back; galantamine now round-trips exactly as `(4aS,6R,8aS)-...`, PubChem's published set for natural galantamine. `test_fda_0605_galantamine_no_letter_suffix_stereo` had pinned the stripped `(6R)`-only name and its docstring blamed OPSIN; it is inverted and renamed `..._keeps_its_letter_suffix_stereo`.

**D-185, ibogaine: a bridged system named by FUSION has letter junction locants.** The descriptor gate admitted only plain integers for a bridged parent (right for von Baeyer names, which have no letters), so `6a` was
dropped before validation ever saw it. Admitted when the parent is not a von Baeyer or spiro name; the OPSIN validation still strips it if the name is unreadable. Ibogaine is now `(6R,6aS,7S,9S)-...`, exact.

**D-186, a polyester's principal anion followed the order its atoms were written in.** Equally scored plans fall to generation order, and the ester decompositions came out in atom order, so heroin and any diacetate of a
diol had a different name for each way of writing the SMILES (30 random SMILES each: 5 of 7 diester shapes tried gave two names). Now, on the EXECUTED trees (`_break_ester_tie`, the ester counterpart of
`_break_alphanumerical_tie`): (1) the senior ACID is the principal anion (P-65.6.3.3.3.2 method 2, "corresponding to that of acids"): a ring parent before a chain (P-44.1.2.2), then more skeletal atoms, then more
substituents (`_acid_seniority_key`); (2) among esters of the same acid, the alcohol component: ring parent before chain, then the lowest locant of its free valence, then its prefixes (P-31.1.4;
`_ester_alcohol_key`). `propyl` beats `propan-2-yl`, `hexan-2-yl` beats `hexan-3-yl`. A well-formed poly-ester reading (`dimethyl butanedioate`) is tried first and wins, as in the normal loop. Heroin moves to
`(5R,6S,9R,13S,14R)-6-(acetyloxy)-4,5-epoxy-17-methyl-7,8-didehydromorphinan-3-yl acetate`. At most four tied plans are executed (each alcohol can hold more esters, so the work multiplies); beyond four, or when a
component is not comparable (a retained acid other than formate/acetate/benzoate, a leaf alcohol), the order is RDKit's canonical class rank, which does not depend on atom order but is not a nomenclature rule.
**A first version ordered by the size of the acid side of the cut and was wrong**: for esters on one shared skeleton that side is nearly everything, and it made an acetate outrank a ring carboxylate (census rows
1404625, 1709625, 2069625). The ref-compare and census scan caught it; the executed-acid comparison replaced it.

**Not done: the book's PIN for a polyester is a different construction.** P-65.6.3.3.3.1 names identical anions multiplicatively, `ethane-1,2-diyl diacetate (PIN)`, `propane-1,2,3-triyl triacetate (PIN)`;
method 2 (acyloxy) is "acceptable in general nomenclature". The engine builds no multiplicative ester, so every polyester it writes is the accepted form, now at least a stable one.

## 2026-10-06 -- naming round 26 (D-187 to D-190): the esters of one polyol are named as the book names them

Round 25 left the book's PIN for a polyester unbuilt. P-65.6.3.3.3.1 (pdf p. 624) names the esters of ONE polyhydroxylic component with ONE acid functional-class-multiplicatively: `ethane-1,2-diyl diacetate (PIN)`, `propane-1,3-diyl bis(chloroacetate) (PIN)`, `propane-1,2,3-triyl triacetate (PIN)`; the acyloxy form the engine wrote (`2-(acetyloxy)ethyl acetate`) is "acceptable in general nomenclature" only. Building it meant naming a POLYVALENT organyl group, which nothing had asked of the generic substituent path, and that path was wrong in four ways. Measured first: OPSIN reads every identical-anion form (stereo and unsaturation included), and reads NONE of the different-anion forms.

**D-187, the multiplicative polyester (`polyol_ester`).** A new functional-class decomposition, the mirror image of the poly-acid reading (`polyester`: one acid, several alcohols): after cutting every ester O--C(alkyl) bond the alkyl carbons lie in ONE component, the acids are separate components, and they are the SAME acid. The alcohol component is carved as a bridging substituent with one free valence per ester and named `<organyl> <multiplied anion>`: `di`/`tri` for an unsubstituted anion, `bis`/`tris` for a substituted one (`bis(chloroacetate)`; the test is the anion's own tree, since `dichloroacetate` is a different anion), and an enclosed `di(prop-2-enoate)` where the name carries a locant. `_break_ester_tie` tries it before the single-ester readings, as it does the poly-acid one. Declined, so the molecule keeps its name: different acids, a senior group elsewhere, a second alcohol, a lactone, and any organyl group the generic path cannot name as one n-valent group (`_organyl_cites_valences`: the divalent group of `1,2-phenylenedi(propan-3,1-yl) diacetate` came out `3-(2-propylphenyl)propane-1-diyl`, one locant for two valences, which is a different molecule). Heroin is now `(5R,6S,9R,13S,14R)-4,5-epoxy-17-methyl-7,8-didehydromorphinan-3,6-diyl diacetate`.

**D-188, a polyvalent free valence was written with its multiplier twice.** `FREE_VALENCE_SUFFIXES` already carries `diyl` and `triyl`, and `render_free_valence_suffix` prepended `di`/`tri` as well: `ethan-1,2-didiyl`, `propan-1,2,3-tritriyl`, and `4yl` for four valences. Nothing reached it, because the multiplicative builder writes its own linkers. It now builds the word from the count of attachment points, and the parent keeps its terminal `e` before the consonant (`ethane-1,2-diyl`, `cyclohexane-1,4-diyl`).

**D-189, a divalent ring took the monovalent retained leaf.** `_generate_retained_plans` offered `phenyl`/`cyclohexyl` for a ring with TWO free valences, so hydroquinone's group was `phenyl`: a different molecule. A retained substituent form is one valence; with more the substitutive path names the group.

**D-190, the free valences were numbered by the first one alone.** For a ring substituent the numbering kept both directions once the first attachment was locant 1, and plan order chose: catechol was `1,6-phenylene`, 1,3-cyclopentanediol `cyclopentane-1,4-diyl`, pyrogallol `benzene-1,5,6-triyl`. P-31.1.4.2.4 ranks the free valences as a SET ahead of any prefix; polyvalent groups now go through the same lowest-set rule a hetero ring already had (`_lowest_free_valence_numberings`), and a chain compares the sets of both directions. Then P-29.6.1 (pdf p. 313): "`methanediyl` and `benzene-1,2-diyl` are not recommended in place of `methylene` and `1,2-phenylene`", and they stay substitutable, so a divalent benzene is `1,4-phenylene`, `2,6-dimethyl-1,4-phenylene`, and CH2 is `methylene`, `phenylmethylene`.

**Not built, with the evidence.** P-65.6.3.3.3.2 method (1), DIFFERENT anions on one polyol (`propane-1,2,3-triyl 1,2-diacetate 3-propanoate`, `1,4-phenylene acetate dichloroacetate`, `methylene acetate formate`), is the PIN, and OPSIN reads none of it: every form tried (with and without locants, `methanediyl`) is unparseable, the book's own five examples included. Those molecules stay on method (2) (`2,3-bis(acetyloxy)propyl propanoate`), which OPSIN confirms. Also not built: an organyl group that is itself multiplicative or a ring assembly (`1,2-phenylenedi(propan-3,1-yl)`, `[1,1'-biphenyl]-4,4'-diyl`, `oxydi(ethane-2,1-diyl)`), polyvalent groups on a branched skeleton (pentaerythritol), and the poly-acid/poly-alcohol mix of P-65.6.3.3.4 (`dimethyl ethane-1,2-diyl dibutanedioate`); all keep the acyloxy name they had.

**Measured.** Census, 2000 rows, master against this tree: the class distribution is identical (1958 exact, 97.90%; 14 same-connectivity, 12 candidate wrong structures, 9 visible failures, in both), and exactly THREE names change, all exact before and after: `ethane-1,2-diyl bis({[amino(phenyl)methylidene]amino}methanoate)` (was `2-({[amino(phenyl)methylidene]amino}(oxo)methoxy)ethyl ...`), `(pyren-1-yl)methylene diacetate` and `[(1S,2S,6R,7R)-4-(3-nitrophenyl)-3,5-dioxo-10-oxa-4-azatricyclo[5.2.1.0^{2,6}]dec-8-en-7-yl]methylene diacetate`. Ref-compare against master (1712 structures over r7, r8, mc, pop): TWO names change, `1-(butanoyloxy)ethyl butanoate` -> `ethane-1,1-diyl dibutanoate` and the held-out `3,4,5-tris(acetyloxy)-1,6-diisothiocyanatohexan-2-yl acetate` -> `1,6-diisothiocyanatohexane-2,3,4,5-tetrayl tetraacetate`, both read back by OPSIN on both sides: 0 violations against `r26-release-candidate.toml` (2 without it). A 73-molecule battery of polyol esters (diols to hexols, rings, phenylenes, stereo, unsaturation, and shapes that must NOT take the path) was read back by OPSIN: 73 of 73 the identical structure, stereo included. **The first battery run found the wrong numbering** (`1,6-phenylene`, `cyclohexane-1,6-diyl`, `benzene-1,5,6-triyl`), every one of which OPSIN also read as the right molecule: a round trip that passes is not a name that is right, and D-190 is what the battery's locants asked for. Fork suite 7189 passed, 9 failed: seven were the round 24/25 tests that pinned the acyloxy form (updated, then 246 ester-related tests pass), and two (`test_trindene_indicated_h_name`) fail identically on round 25's own commit `aa1059d`, so they are not this round's. App-side, the 45 registered naming-consumer test files: 2797 passed, 0 failed. The scripted app run on the diacetoxy-oxo morphinan: `VERDICT PASS`, the name `...-6-oxomorphinan-3,14-diyl diacetate`.

**Mutation matrix, and what it taught.** 28 mutants of the new rules and guards: 20 caught, 8 survived, and every survivor was read. (1) The acid-decline check duplicated `_has_error_children`, and four builder guards (distinct acyl/oxygen, ring bond, alkyl carbons in one component, ester O in its own component) were each implied, on every connected molecule, by "the components do not overlap and no atom is left over"; they were REMOVED rather than claimed, the builder is tested directly (macrocycle, two identical lactones, carbonate, stray fragment, two molecules, shared diacid), and 48 multi-ester census structures named before and after the removal differ in 0 names. (2) The last survivor, `polyol_ester` in `_break_ester_tie`'s gate, LOOKED equivalent and was not: when the polyol plan is built and then declines at execution (diethylene glycol, bisphenol A, pentaerythritol, any ether-linked diol), the gate is what lets round 25's comparison of the single-ester readings run, and without it 7 of 20 unsymmetric shapes moved to the canonical-rank fallback's choice (`...butan-2-yl acetate` for `...ethyl acetate`). Nothing tested it; four pinned names now do, and the final matrix is 23 of 23 caught. The first test written for that gate checked only that the name was STABLE, which the fallback also is, and the mutant survived it.

## 2026-10-06 -- a tie between von Baeyer numberings goes to the strategy layer, not to atom order

Found in naming round 25 and recorded there as not fixed: `OC(=O)C1C2CCC(CC1O)N2C` was `3-hydroxy-8-methyl-8-azabicyclo[3.2.1]octane-2-carboxylic acid` for about half of its SMILES spellings and `...-4-carboxylic acid` for the rest, and cocaine likewise (`methyl (1S,2S,3S,5R)-...-2-carboxylate` or `methyl (1R,3S,4S,5S)-...-4-carboxylate`). Both names read back to the input, so only the tie-break was wrong, and no corpus could see it: a right name needs a symmetric skeleton AND a substituent on it.

**Cause.** `name_bridged` pins ONE numbering for every von Baeyer ring that has a heteroatom or a secondary bridge, because the heteroatom prefix and the unsaturation locant are written into the name text. `_choose_best_vb_locant_map` picked it by `score < best_score`, so on a tie the first numbering generated won, and generation order is sorted atom index. 8-azabicyclo[3.2.1]octane has two mirror numberings that tie on the heteroatom, unsaturation and locant-set scores, so the strategy layer was handed a single option and P-31.1.4 (lowest locants to the suffix, then the prefixes) never ran. Measured, not assumed: with the pin stripped, 40 of 40 random spellings give `-2-carboxylic acid`. The defect was wider than the two reported molecules: quinuclidin-3-ol came out `-3-ol`, `-5-ol` or `-8-ol`, and 7-azabicyclo[2.2.1]heptane-2,5-dicarboxylic acid `2,5` or `3,6`, depending on the spelling.

**Fix, in `ring_naming/bridged.py`.** (1) The two selectors (now `_best_vb_locant_maps` and `_best_vb_locant_maps_with_secondaries`) return EVERY map tied at the best score, and `name_bridged` pins all of them that write the SAME text (`_baked_name_parts`: secondary-bridge descriptor, double and triple bond locant pairs, heteroatom prefix). The text comparison is load-bearing and not decoration: the score ranks a bond by its lower locant but the name also cites the higher one, so `non-1-ene` and `non-1(8)-ene` tie. Pinning both let the strategy pick the second for `N1C2CCC=C1C(Cl)CC2` while the text said `2-chloro-9-azabicyclo[3.3.1]non-1-ene`, which OPSIN reads as a different molecule (12 of 24 spellings, measured with the comparison neutralised). (2) A second tier in both scores, `_hetero_locants_by_element` (P-31.1.4.2.4): after the heteroatoms' locants taken together, the senior element takes the lower one. `2-oxa-5-azabicyclo[2.2.1]heptane` had come out as `5-oxa-2-aza...` in 12 of 24 spellings; those two numberings write different text, so (1) alone could not reach it. (3) The numbering that used to be the only option is pinned LAST. When the strategy layer cannot tell two numberings apart, the later-generated plan wins (the declared policy of `engine._search_plans` and `_break_alphanumerical_tie`), so offering the tie in generation order made the second numbering win the ties nothing can break. On round 25's atropine and scopolamine, whose tropane skeleton is meso, that gave `(1S,5R)-...` and `(1S,2S,4R,5R)-...` against the `(1R,5S)-...` and `(1R,2R,4S,5S)-...` their tests pin; with the line removed they fail again.

**Measured, in the application that vendors this package (against its master with round 25).** A 14-structure panel, 24 spellings each (random roots and random atom orders): 4 structures stable before, 12 after; cocaine, split `-2-` and `-4-carboxylate` before, is one name in 24 of 24. A census of 2000 structures (canonical SMILES, OPSIN read-back): 4 names moved, every one `exact` before and after, the class counts identical, all four to a lower locant (`nonan-7-yl` to `nonan-3-yl`, `3,5-dichloro...2,4-diene` to `2,4-dichloro`, a dioxabicyclo[2.2.2]octene attached at 4 to attached at 1, a `dec-8-en-7-yl` to `-1-yl`). A comparison over 1712 panel structures: 2 names moved, both Blue Book `dispiroter` rows this engine cannot yet name in the book's form (neither the old nor the new name reads back), the spiro atom's locant on a 7-oxabicyclo[4.1.0]heptane component `5''` to `2''`. Mutation-checked in `tests/test_namer_numbering.py` and `tests/test_round25_stereo_and_esters.py`: pinning only the first of the tie fails the substituent-tie cases, dropping the element tier fails `2-oxa-5-aza`, dropping the text comparison fails the read-back guard, dropping the pin order fails atropine and scopolamine.

**Left open, each measured identical before this change on the same spellings, so none is caused by it.** (a) Numberings that tie on EVERY locant criterion (a meso skeleton: tropine, `2,4-diphenyl-3-azabicyclo[3.3.1]nonan-9-ol`, the `4-azatricyclo[5.2.1.0^{2,6}]dec-8-ene-3,5-dione` imides) still go by atom order: `strategy._numbering_components` scores heteroatom, suffix and prefix locants and has no stereo-descriptor tier, so `(1R,5S)` against `(1S,5R)` is a coin flip (tropine 12 of 24 each, the others 9/7, 12/4 and 12/4 of 16, the same counts and labels before and after). The rule that would settle it, CIP R before S at the first point of difference, is not implemented; it is consistent with the `(1R,5S)` and `(1R,2R,4S,5S)` that round 25 pins for atropine and scopolamine. (b) Tricyclic and larger cages use only `decompose_ring_system(...)[0]`, and the tied-score decompositions come back in an atom-index-dependent order, so 2-azaadamantane-type acids are named `2-aza`, `9-aza` or `10-aza` by spelling (six names, the same counts before and after). (c) The unsaturation tier ranks a bond by its lower locant, so `non-1-ene` against `non-1(8)-ene` is a tie decided by atom order (see the read-back guard); ranking compound locants needs a Blue Book rule not yet cited.

## 2026-10-06 -- the three von Baeyer ties the previous entry left open: meso skeletons, compound locants, and cages

The previous entry listed three numberings that still went by atom order, (a) a meso skeleton, (b) a tricyclic or larger cage, (c) `non-1-ene` against `non-1(8)-ene`. Each now has a Blue Book rule behind it, and each is the same name for every spelling that was measured. Ported from OpenChem Studio pull request #226.

**(a) A meso tie goes to the preferred stereodescriptor (P-14.4 (j)).** When two numberings tie on every locant criterion, the one whose CIP descriptors, read in locant order, prefer Z, R, M, r to E, S, P, s wins. `engine._break_alphanumerical_tie` sorts its candidates by `(locant_key, _stereo_locant_key(tree), -seq)`; a prefix-free tree gets `locant_key = ()` instead of aborting the comparison. This is general, not von Baeyer specific: the tie-break runs for every parent. It also closes round 26's open meso entry: `(2R,3S)-butane-2,3-diyl diacetate`, `(1R,2S)-cyclohexane-1,2-diyl diacetate`, `(2R,3S)-butane-2,3-diol` and `(1R,5S)-8-methyl-8-azabicyclo[3.2.1]octan-3-ol` are each one name in 24 of 24 spellings in this fork. (P-31.1.4.3.4, which that entry cited, is not the rule; it is criterion (j) of P-14.4.)

**(b) A cage is numbered from every decomposition that ties, superscripts before heteroatoms (P-23.2.6.2, P-23.3).** `vb_decompose.best_decompositions` returns all decompositions with the best score, where `_score_decomposition` now ranks the main ring's symmetric division (P-23.2.6.2.1) as well as coverage, main ring and main bridge. `bridged._best_vb_locant_maps_with_secondaries` numbers each one and scores the pairs by `(secondary-bridge superscripts as a set, in order, heteroatom locants, element order, unsaturation, substituent locants, all locants)`: P-23.3.1 fixes the hydrocarbon's numbering first and only then does the heteroatom set decide, so `2-aza`, `9-aza` and `10-aza` for the same 2-azaadamantane-type acid are one name. Element order is O, S, Se, Te, N, ... per P-23.3.2.2 (the previous entry cites P-31.1.4.2.4 for that order; the rule is P-23.3.2.2, and P-14.4 holds the general criteria). `P-23.2.6.2.3` (fewest dependent secondary bridges) is not scored: the enumerator cannot produce a dependent bridge, so a criterion there could never fire.

**(c) A compound locant ranks below a single one (P-31.1.4.2).** The unsaturation tier is `(-compound_count, -count, locants..., highs...)` (`preference.unsaturation_tier`): the numbering with the fewest compound locants such as `1(8)` wins, then the lowest locants ignoring the parentheses, then all of them. `bicyclo[4.2.0]octa-1(8),2,4-triene` is now `bicyclo[4.2.0]octa-2,4,6-triene` (24 of 24 spellings). The rewrite in `_recompute_ring_unsaturation_name` matched only a plain `-N-ene` locant, so a numbering chosen for its compound locant had its baked text and its numbering disagree; it now reads `N(M)` and rewrites from the final numbering, the all-compound case included.

**Three pinned names changed**, each reading back through OPSIN: `bicyclo[4.2.0]octa-1(8),2,4-triene` to `octa-2,4,6-triene`, and `tricyclo[8.4.0.0^{4,9}]tetradeca-1(14),2,10,12-tetraene` to `tricyclo[8.4.0.0^{2,7}]tetradeca-1(14),8,10,12-tetraene` (two tests).

**Measured in OpenChem Studio** (this fork has no panel to compare against): ref-compare over 1712 panel structures moved 25 names, 23 reading back on both sides and 2 on neither, 0 round-trip regressions; a census over 2000 structures moved 53 names with no change of class. Mutation-checked in `tests/test_namer_numbering.py` (63 tests), each by undoing one fix: best decomposition only 7 failed; symmetric division unscored 5; heteroatoms ranked above the superscripts 3; no stereo tier in the tie-break 10; compound count ignored 4; the rewrite reading only a plain locant again 2. The port was `tools/fork_port.py`, 8 files merged clean (5 engine, 3 test), numstat +226/-94 on both sides.

**Left open.** (a) The enumerator cannot produce a dependent secondary bridge, and a 28-atom tetracyclic such as the book's P-23.2.6.2.2 octacosane is beyond its cap, so that example is not matched. (b) A benzene ring inside a von Baeyer system is named from whichever Kekule form the input carries, so the ene locants of `C1=CC2=CC=CC=C2C3CCCCC13` are four names over 24 spellings (`1(14),8,10,12` 11, `2(7),3,5,8` 5, `2,4,6,8` 4, `1(10),8,11,13` 4, all read back); the commit before this change (measured in OpenChem Studio) split the same 11/5/4/4. That is a Kekule-form tie and no rule in this change reaches it. (c) The path that pins a heteroatom numbering still ranks an ene above a suffix, which sits uneasily with P-14.4 (c) before (e); it predates this change. (d) A spiro assembly can now prefer a fusion name over a von Baeyer component after the renumbering; that reads as the better name and is not guarded either way.

## 2026-10-06 -- when numberings tie, R takes the lower locant (P-14.4 (j))

A meso compound had two equally valid descriptor sets and the SMILES atom order chose: `C[C@H](O)[C@@H](C)O` was `(2R,3S)-butane-2,3-diol` or `(2S,3R)-butane-2,3-diol`, `C[C@H](Cl)[C@@H](C)Cl` and `C[C@H](Br)[C@@H](C)Br` the same two ways, `O[C@H]1CCCC[C@H]1O` `(1R,2S)-` or `(1S,2R)-`. OPSIN reads both forms to one structure, so nothing failed and no corpus row could see it.

**Cause.** The two numberings tie on every tier of the preference key (`strategy.preference_key`) and on P-14.4 (g), then fall to plan generation order, which follows atom order. Nothing implemented the criterion that settles it.

**The rule, as the book prints it** (BlueBookV2.pdf p. 79; the P-93 examples repeat it as "[see P-14.4 (j)]"): "when there is a choice for lower locants related to the presence of stereogenic centers", the lower locant goes to the CIP descriptors Z, R, M and r over E, S, P and s. The book's examples are decided by it: `(2R,4S)-2,4-difluoropentane`, `(2Z,5E)-hepta-2,5-dienedioic acid`, `(2R,3s,4S)-` and `(2R,3r,4S)-2,3,4-trichloropentanedioic acid`, and `(2Z,4S,8R,9E)-undeca-2,9-diene-4,8-diol`. (Round 26's limitations note cited this as P-31.1.4.3.4; in that PDF P-31.1.4 is the von Baeyer section, and the engine's own comments use that number for indicated hydrogen and heteroatom locants.)

**Fix, in `engine.py`, as the LAST criterion, after (g).** `_stereo_locant_key` reads a plan's `stereo_descriptors` (collected when the plan is generated, so no extra plan is executed to read them): the stereogenic units' locants first, then the descriptors' ranks in locant order, the first point of difference deciding. `_comparable_stereo` declines to compare candidates that do not describe the SAME stereogenic atoms, because a numbering that drops a descriptor (a junction locant a bridged or spiro parent cannot cite) has a shorter tuple and would win by length alone. It is applied in `_break_alphanumerical_tie`, where a name with no prefixes, which (g) cannot compare, is now compared on stereo when stereo can decide. Since round 26 (D-187) writes a polyol's diester as `<organyl>-diyl di<anion>`, the numbering of that `-diyl` group goes through the same function, which is how `(2R,3S)-butane-2,3-diyl diacetate` becomes one name in every atom order with no stereo code in round 26. On round 26's tree without this change it was `(2S,3R)-butane-2,3-diyl diacetate` (stable, S-first), `(2S,4R)-pentane-2,4-diyl diacetate` likewise, and `cyclohexane-1,2-diyl diacetate` had two names, `(1R,2S)-` and `(1S,2R)-`.

**A tier on the ester route was built and removed.** Before round 26, `_break_ester_tie` named a meso diacetate by canonical rank: one name in 30 of 30 spellings, and S-first for 5 of 10 meso skeletons probed. An R-first tier there fixed all five and passed its tests, and on one skeleton nobody had tuned on, meso dipropylene glycol diacetate, it named `CC(=O)O[C@H](C)COC[C@H](C)OC(C)=O` `(2R)-1-[(2R)-2-(acetyloxy)propoxy]propan-2-yl acetate`, the R,R compound: OPSIN read back 6 of 7 stereoisomers with the tier and 7 of 7 without. A tie-break only chooses between trees that already exist, and one of the two candidates carried descriptors that do not describe the molecule (the alcohol component is named as a fragment of its own, and plans whose fragments print alike share a cache entry). The tier was removed and `_break_ester_tie` has a comment saying why. `test_every_stereoisomer_of_these_diesters_reads_back` is the guard; putting the tier back makes it fail on exactly that name.

**Measured, in the application that vendors this package (against its master with the von Baeyer tie-break and round 26).** The 25 structures in `tests/test_namer_stereo_locant_tie.py` (18 pinned by name, 7 meso diesters pinned by their first descriptor), 13 spellings each (the written one and 12 random roots and atom orders, each checked to have the same InChIKey): with the key off, all 18 named ones gave TWO names, and of the 7 diesters 2 gave two names, 3 gave one S-first name and 2 gave an R-first one by accident of rank; with the key on, the 18 give their one pinned name and the 7 give one R-first name. The 22 of those names OPSIN can read (3 carry a pseudoasymmetric `r`/`s`, which it cannot) read back to their structure, and so does every stereoisomer of five diester skeletons. Census of 2000 rows (OPSIN read-back): 4 rows moved, class counts identical, all four to R at the lower locant; two of them are von Baeyer meso skeletons the von Baeyer tie-break left open. A comparison over 1712 panel structures: 0 names changed. Mutation-checked in the new test file: flipping the rank table, ignoring the key, comparing candidates that describe different atoms, letting stereo outrank (g), giving up on a name with no prefixes, putting descriptors before locants and not ordering them by locant each fail a named test, and putting the removed ester tier back fails the read-back guard. One mutation is an EQUIVALENT mutant and no test can see it: running the no-prefix branch when the key cannot decide changes how many plans are executed, not which one wins.

**Relation to the von Baeyer entry above, which carries the same criterion.** Ported from OpenChem Studio #226, that entry added a (j) key of its own in the same place (`_stereo_locant_key(tree)`: one 0/1 rank per descriptor the executed tree holds, in the order it holds them). The two are one rule written twice, and this entry's is the one kept: it compares the stereogenic units' locants first, orders the descriptors by locant, and refuses to compare numberings that describe different atoms. Measured in the application, on its master with that key and without this one, 2 of the 25 structures of `tests/test_namer_stereo_locant_tie.py` had two names (`C[C@H](O)C(C)O`, one specified centre, and `C/C=C\CC=C/C`, a diene with one specified bond), and that entry's own tests pass with this key. The tropine and pseudotropine results it reports are this rule's: 2 names each in 24 random SMILES become one, `(1R,5S)-`, and round 25's atropine and scopolamine pins hold.

**Not done, measured, in `KNOWN_LIMITATIONS.md`:** a meso compound whose two halves are each a candidate PARENT (an ether or amide of a meso diol) is still named by atom order, since the tie-break compares only the plans of one parent hypothesis; the acyloxy-form diesters round 26 leaves (multiplicative organyl groups) have no (j) tier and are chosen by canonical rank; the like-pair-before-unlike precedence of P-92.5.2.1 is not implemented. **Found on the way, not caused by this:** the R,S di-sec-butylbenzene is named as the R,R or the S,S, which OPSIN reads as a different stereoisomer.

## 2026-10-06 -- two substituents that print as one SMILES are not one substituent: the naming session's cache key

`name_smiles('CC[C@@H](C)c1cccc([C@@H](C)CC)c1')`, the R,S di-sec-butylbenzene, returned `1,3-bis[(2R)-butan-2-yl]benzene` or `1,3-bis[(2S)-butan-2-yl]benzene` by the order its atoms were written in. OPSIN reads the first as the R,R compound and the second as the S,S, so both were names for a different stereoisomer. The Blue Book's own example under P-14.4 (j) (BlueBookV2.pdf p. 79) is the right name, `1-[(2R)-butan-2-yl]-3-[(2S)-butan-2-yl]benzene (PIN)`.

**The cause is not the prefix merger,** which is where it was first looked for. Both prefixes reach `merge_identical_prefixes` already named `(2R)-butan-2-yl`, and the merger correctly merges two equal strings. Carved at either ring bond, the two substituents are the same molecule, `CCCC` with the attachment on atom 3, because once the ring side is an H the centre is no longer a stereocentre; the inherited descriptor lives only in a `_ParentCIPCode` atom PROPERTY (stamped `R` on one and `S` on the other, which was right), and `MolToSmiles` cannot write a property. `engine._name_bound` keyed the session cache on `Chem.MolToSmiles(mol)`, so the second lookup returned the first fragment's finished tree. With the lookup disabled the engine writes the book's name in every spelling.

**It is also why the R-first tier on the ester route had to come out of the P-14.4 (j) change.** The alcohol component of an ester is named as fragments of its own, and the inner substituent of either ester plan of `CC(=O)O[C@H](C)COC[C@H](C)OC(C)=O`, `CC(=O)OC(C)C`, is the same text with its centre capped away, so the second plan reused the first plan's tree and its `(2R)`: meso dipropylene glycol diacetate came out as the R,R compound. The tier is back (next entry).

**Fix.** `extraction.context_stereo_key(mol)` writes the stamps a fragment carries, atoms and bonds, as a suffix (`|a3=R`; nothing for a fragment with none, so every unstamped fragment keeps exactly the key it had). `_name_bound` builds `fragment_key = smiles + context_stereo_key(mol)` and all 45 session-cache calls use it; `smiles` itself stays the plain structure for the two curated oxoacid lookups and the error messages. Provenance is deliberately not in the key, or no two fragments would ever share an entry: two R,R substituents still share one, so the cache still hits.

**Measured, in the application that vendors this package.** A sweep of nine substituent families on five parents, every stereoisomer, five spellings each, every spelling checked to keep the isomer's InChIKey, every name read back through OPSIN: 2725 names. Before: 56 read back as another stereoisomer, in seven of the nine families and in nothing but a pair of the SAME substituent on a ring. After: 0 of 2725. The census over 2000 rows: 0 rows differ. A comparison over 1712 panel structures: 0 names changed. `tests/test_namer_stereo_cache_identity.py` (21 tests here: the failing case in every spelling, its converse, the premise that the two fragments print identically, the wiring, an AST guard over every cache call in `engine.py`, and a miniature of the sweep) was mutation-checked: six breaks each turn a test red (the key ignoring the stamps, including provenance, leaving out bond stamps, the lookup going back to the plain SMILES, a store these molecules reach doing the same, and a store they never reach doing the same, which the first draft of the file let survive).

**Left open (`KNOWN_LIMITATIONS.md`, "Open after the stereo cache fix").** Prefixes that tie on their letters alone are cited in atom order, which P-14.5.4 answers by the lowest locants at the first point of difference (`1-(pentan-2-yl)-4-(pentan-3-yl)benzene`, 20 of 40 spellings). The stereo half is closed in the next entry.

## 2026-10-06 -- "R precedes S" beyond the numbering: the citation order of prefixes, the parent of a meso compound, and the ester route (P-45.6.2, P-45.6.3, P-44.4.1.12)

The P-14.4 (j) entry settled the NUMBERING of one parent. Reading the Blue Book's own stereo examples through the engine, and naming every stereoisomer of a few skeletons over random spellings of each, found three more choices that went by the order the SMILES atoms were written in. All read back through OPSIN, so no corpus could see them.

**1. The order two prefixes are cited in (P-45.6.3, BlueBookV2.pdf p. 427).** "When names based on alphanumerical order ... are the same, further choice depends on the alphabetic order of the stereochemical descriptors 'R' and 'S'": `1-[(1R)-1-bromoethyl]-1-[(1S)-1-bromoethyl]cyclopentane`, not S first. `derive_sort_name` sets the descriptors aside (P-14.5), and the sort that cites the prefixes was stable on it, so the order was the order the tree held them in. The R,S di-sec-butylbenzene, which the cache fix made the right molecule, was `1-[(2R)-butan-2-yl]-3-[(2S)-butan-2-yl]benzene` (the book's own example under (j)) or `3-[(2S)-butan-2-yl]-1-[(2R)-butan-2-yl]benzene` by spelling, 7 and 9 of 16; 1,3- and 1,4-bis(1-chloroethyl)benzene and the cyclopentane above did the same. The E/Z case was worse than unstable: criterion (g) broke the tie between equal sort names on name TEXT, and "E" sorts before "Z", so `1-[(1E)-prop-1-en-1-yl]-3-[(1Z)-prop-1-en-1-yl]benzene` put E at the lower locant, against (j). `assembly.stereo_citation_key` ranks a prefix name's descriptors in the order the name cites them with (j)'s own table (Z, R, M, r before E, S, P, s), and it is the second sort key at the three places assembly cites prefixes and in `engine._alphanumerical_locant_key`, so the order a name is written in and the locants (g) reads "for the substituent cited first" cannot disagree.

**2. Which half is the parent (P-45.6.2, p. 426; P-44.4.1.12, pp. 412-413).** A meso diether or diamide has two equal halves, either of which can be the parent, and the two names differ only in their descriptors: `{[(2R,3S)-3-phenoxybutan-2-yl]oxy}benzene` or `{[(2S,3R)-3-phenoxybutan-2-yl]oxy}benzene`, likewise `N-[(2R,3S)-3-benzamidobutan-2-yl]benzamide`, the 2,4-diphenoxypentane and the dibenzyloxybutane (each split 10 and 6, or 9 and 7, over 16 spellings). `_break_alphanumerical_tie` compares only the plans of one parent hypothesis, deliberately, and P-14.4 is a numbering rule; P-45.6.2 is the rule for choosing between two names that differ in nothing else: "the configurational symbols are compared and 'R' precedes 'S'". `engine._break_parent_stereo_tie` names each tied parent hypothesis as it would be named alone and, when the names are EQUAL once the descriptors are set aside (`_choose_by_configuration`, so a choice between two different names is never made on this ground), takes the one whose configuration is senior: the parent's own E/Z, then like before unlike (P-44.4.1.12.2: "like stereodescriptors such as 'RR', 'SS' have priority over unlike 'RS' and 'SR'"), then r over s, then R over S (`_parent_configuration_key`), then `stereo_citation_key` over the whole name. It engages only for a molecule that carries stereo (`_carries_stereo`), so an achiral molecule never pays for it, and a molecule with more than four tied hypotheses is left as before. **"Like" is judged only where the pair is unambiguous**, a parent with exactly two R/S descriptors; for more, the book pairs each centre with a reference descriptor from the digraph (P-92.5.2.1), which a name does not hold. The ether `CC(Cl)C(C)OC(C)C(C)Cl` is where like-before-unlike and R-first disagree: its halves can be (2S,3R) and (2S,3S), and the parent is now the like half, `(2S,3S)-2-chloro-3-{[(2R,3S)-3-chlorobutan-2-yl]oxy}butane`.

**3. The ester route.** The R-first tier in `_break_ester_tie` that was taken out of the P-14.4 (j) change is back (`_ester_alcohol_stereo_key`); it was not the defect, the cache key above was. With the key in place, meso dipropylene glycol diacetate is `(2R)-1-[(2S)-2-(acetyloxy)propoxy]propan-2-yl acetate` in every spelling, and every stereoisomer of six skeletons that were not tuned on (dipropylene and tripropylene glycol diacetate, the dibenzoate, a tartrate diacetate, the hexane-2,5-diyl and hydrobenzoin diacetates: 22 stereoisomers) is one name that reads back through OPSIN to the structure it came from.

**Measured, in the application that vendors this package.** `tests/test_namer_stereo_parents_and_citation.py` (51 tests here), among them every stereoisomer of nine skeletons named over its spellings and read back; the census over 2000 rows: **0 rows moved**, class counts identical, so the standing census holds none of these shapes; a comparison over 1712 structures: 0 names changed, 0 violations. The Blue Book's own examples that apply (P-45.6.3, P-45.6.2 examples 2 and 3a, the (j) di-sec-butylbenzene) come out as printed in every spelling, and so do P-92.5.2.2 examples 1 to 3 (OPSIN cannot read those, so the structures were built with RDKit's CIP labeler). Mutation-checked, 16 mutants of the new rules: 13 failed a test at once, three survived and were read (the citation key reading only the first descriptor group, the cross-parent comparison admitting names that differ in more than their descriptors, the ester key's count slot), each now has a test that fails it, so 16 of 16.

**Not done, measured, in `KNOWN_LIMITATIONS.md`:** P-45.2.3, the parent chosen by the lowest locant set in order of citation, is not implemented, and none of the book's five FLAT examples for it is stable; P-92.5.2.2 example 5's 13-centre structure is named with four different chain descriptor sets over ten spellings, before this change as after it; like and unlike for a parent with three or more R/S descriptors; M and P in a prefix.

## 2026-10-06 -- a group's bonding number and a prefix's nuclide are named (D-191, D-192)

The Blue Book's own P-45.2.3 examples 11 and 12 (BlueBookV2.pdf p. 422) were named by the engine as a DIFFERENT molecule each. Example 11, `3-[2-bromo-1-(λ5-phosphanyl)propyl]-5-chloro-4-(λ5-phosphanyl)hexanoic acid`, came out with `phosphanyl` for `λ5-phosphanyl` (C9H18BrClO2P2 read back for C9H22BrClO2P2); example 12, `4-(81Br)bromo-3-[1-(81Br)bromo-2-bromopropyl]-5-chlorohexanoic acid`, came out with no label on any bromine. Neither was recorded. Both are one defect met at several places, so each is fixed at the rule and not at the example.

**D-191. A group's bonding number was part of no name.** `_SINGLE_ATOM_SUBSTITUENT` is keyed on (element, charge, bond order), with no term for the atom's hydrogens, so a one-atom group named from a carved fragment was the ordinary prefix whatever its valence: `[PH4]`-, `[SH3]`-, `[SH5]`-, `[AsH4]`-, `[SeH3]`- and `[IH2]`- were `phosphanyl`, `sulfanyl`, `arsanyl`, `selanyl` and `iodo`, each read back with two to four hydrogens fewer. The book prints the number on the prefix, `(λ5-phosphanyl)`, `(λ6-sulfanyl)`, `(λ4-sulfanylmethyl)` (P-45.3, p. 423). Five places lost it, found by following one atom through every route that could name it, and each is fixed:

1. the carved one-atom route (`_name_single_atom_substituent`), from the atom's bonding number (`_hypervalent_group_name`: `valence - 1 + bond order` in a fragment whose cut bond became a hydrogen, which is 5 for `-PH4` and for `=PH3` alike), reusing the ring code's `_STANDARD_VALENCE`; it also names `=PH3` (`lambda5-phosphanylidene`), which the table had no entry for;
2. the oxo/thioxo fallback, which made `=SH2` and `=SH4` `thioxo` (read back as `=S`);
3. the ring-carbonyl synthesis, which promoted any terminal double-bonded chalcogen on a ring or ketone carbon to a thione whatever its hydrogens;
4. the thione, selone and tellone SMARTS, whose bare `(=S)`, `(=[Se])`, `(=[Te])` asked nothing of the chalcogen's connectivity (`=[SeH2]` was a selone); they are `(=[SX1])` and so on now;
5. the heteroatom-centre PARENT: `C[PH4]` was `methylphosphane`, `c1ccccc1[PH4]` `phenylphosphane`, `C[PH2](C)C` `trimethylphosphane`. They are `methyl-lambda5-phosphane`, `phenyl-lambda5-phosphane` and `trimethyl-lambda5-phosphane`, with the hyphen the book prints before a lambda descriptor (`triphenyl-λ5-phosphanone`, `pentamethoxy-λ5-phosphane`, pp. 769-770; `_needs_hyphen_before_stem`). Only a centre that still carries a hydrogen of its own takes the number: `CP(C)(C)(C)C` stays `pentamethylphosphane`, which OPSIN reads and which loses nothing (the book's `pentamethyl-λ5-phosphane` is D-195, open). **The hydrogen standing for a carved substituent's cut bond is not one of the molecule's**, and counting it was this change's first mistake: it moved 13 of 2000 census rows, every phosphoryl group among them (`(oxo)phosphanyl` to `(oxo)-lambda5-phosphanyl`), with the class table identical. The free valence's own hydrogen is discounted now.

**D-192. A nuclide on a one-atom prefix was named by nothing.** `collect_isotope_labels` labels the atoms of the PARENT and its suffix groups and drops the label of any other atom, so a labelled halogen, hydroxy, amino, sulfanyl, selanyl, oxo or imino prefix read back unlabelled. P-82.2.1 (p. 853) puts the nuclide in front of the group, `(81Br)bromo`, `(18O)hydroxy`, with no locant for one atom (P-82.6.1.2, p. 860). `isotope.isotopic_prefix` does, at the three places a one-atom prefix is built: the FG prefix, only when the prefix IS the name of the one atom it owns (`cyano` and `carboxy` own atoms of a group and are not labelled on a guess, D-193), the `halogen_prefix` role, and the carved one-atom route (`CO[81Br]` is `{[(81Br)bromo]oxy}methane`). Three consequences are in the book and are in assembly: a labelled one-atom prefix is not a compound one (no marks of its own, `4-(81Br)bromo-3-...`; enclosed when multiplied, `1,2-di[(81Br)bromo]ethane`, the book's `1,2-di[(13C)methyl]benzene`), it is cited before an otherwise identical plain one and never merged with it (P-82.2.2.1, p. 854: `1-(81Br)bromo-2-bromoethane`, not `1,2-dibromo...`), and a nuclide is not alphabetised (`derive_sort_name`, P-14.5, p. 80). That last was an existing defect: `(1-13C)methyl` was filed under "13cmethyl" and cited before `ethyl`, `1-[(1-13C)methyl]-2-ethylbenzene` for `1-ethyl-2-[(1-13C)methyl]benzene` (D-192r, D-192s; right molecule, wrong order). `is_nuclide_token` reads the element symbols from the periodic table once, because asking RDKit for a symbol it lacks (`R` of `(2R)`) logs a C++ violation each time, and tests that a mass number is not below the atomic number (`2S` is a stereodescriptor, not a sulfur of mass 2).

**Measured here.** `tests/test_namer_known_defects.py` holds 45 FIXED rows and 10 OPEN rows for D-191 to D-196 (every target, the open ones included, read back by OPSIN on canonical SMILES and InChIKey; of the 20 D-191 rows 17 read back as a different molecule before and none does now, of the 25 D-192 rows 23), and 33 control rows that name identically before and after. The fork's full suite, run under the application's interpreter (RDKit 2025.09.6) with the JRE on PATH: 7,822 passed, 25 xfailed (the 15 open rows that were there and these 10), 0 failed, in 50 minutes. `tools/fork_port.py` merged `engine.py`, `assembly.py`, `isotope.py` and `data/functional_groups.json` clean, numstat +194/-13 on both sides; the rows of `test_namer_known_defects.py` are a three-way merge of only this change onto the fork's older copy of the table (379 lines added, none removed).

**Measured in the application that vendors this package.** The census over 2000 rows: class totals identical (1958 exact, 14, 11, 1, 7, 8, 1) and 3 names moved, each a five-bonded phosphorus with one real hydrogen, `exact` before and after with an identical read-back; the first version of the heteroatom-centre rule moved 13, ten of them the placeholder hydrogen of a carved substituent counted as real. A comparison of 1712 structures: 2 names changed, both read back before and after, 0 violations. The application's vendored suite 5,632 passed, its naming-consumer session 3,181 passed. 20 of 21 undone fixes turn a test red (the survivor, the isotope key inside `_alphanumerical_locant_key`, is shadowed by the final `m.name` element and kept to mirror assembly's order).

**Open, each measured and in `KNOWN_LIMITATIONS.md` ("Open after D-191 and D-192"):** a nuclide on an atom a retained parent name or a multi-atom prefix owns (D-193: `[15NH2]c1ccccc1` is `aniline`, a wrong molecule), P-45.2.3 examples 11 and 12 and P-45.4.1 (D-194), a hypervalent centre with no hydrogen (D-195), and the parent's isotope descriptor placed where OPSIN cannot read it (D-196).

## 2026-10-06 -- one stereoisomer, one name: the parent chosen among chains that differ only in configuration

P-92.5.2.2 example 5's structure (BlueBookV2.pdf p. 900; 13 stereogenic centres, six equal arms on two quaternary carbons) was named by the order its atoms were written in. Over random spellings of that ONE stereoisomer, each checked by InChIKey: 13 names over 30 spellings on master `eb771e6d` (8 over 10 on `66f112ed`, as first reported); 16 over 30 once the session-cache fix (#229) was in; 4 over 30 with the "R precedes S" follow-up (#232); **1 over 40 now, the book's `(2R,3R,5R,7R,8R)-2,8-dichloro-4,4-bis[(2S,3R)-3-chlorobutan-2-yl]-6,6-bis[(2S,3S)-3-chlorobutan-2-yl]-3,7-dimethylnonan-5-ol`.** The note this replaces said "at most one set describes it", and that was true only of the first row: after the cache fix every descriptor in every one of the 16 names was RDKit's `rdCIPLabeler` label for the atom it describes (parent and prefixes, checked per atom), so they were sixteen CORRECT names of one molecule, each on a different one of its nine equal chains. Only the choice of chain was left to atom order, which no per-descriptor check or read-back can see and a count of names over spellings can.

**Cause: the choice was written (#232, `_break_parent_stereo_tie`) and did not engage here, for two reasons it could not have met on the diether and diamide it was built on.** (1) It named every tied parent hypothesis side by side up to a bound of four, and this molecule has nine; only four of them are different, since the two arms of a quaternary carbon that carry one configuration are one choice. (2) It compared two parents only when their names were equal "once the descriptors are set aside", by deleting the descriptor groups from the FINISHED text, and the descriptors decide how prefixes merge: the chain through one arm reads `4,4-bis[(2S,3R)-...]` and through another `4-[(2R,3R)-...]-4-[(2S,3R)-...]`. Measured separately: raising the bound alone changed nothing (the same four names in the same 12, 7, 6 and 5 of 30), so the first obvious blocker was not the blocker.

**Fix.** `engine._plan_identity(mol, plan)` writes the molecule as a canonical SMILES with every parent atom labelled by the ordinal of its locant (a carved fragment's inherited descriptors, which a SMILES cannot write, as isotopes), so hypotheses a configuration-preserving symmetry of the molecule relates are one, and the bound (now 12, which is three arms at each end all different, 3 x 3, with room; measured 15 ms per hypothesis compared on this molecule) counts distinct choices. `assembly.assemble_without_stereo(tree)` assembles with the two descriptor-writing sites suppressed (a `ContextVar`, reset in a `finally`), so the arms are alike and merge alike; `_choose_by_configuration` compares those. The choice itself (P-44.4.1.12.2, BlueBookV2.pdf p. 413: E/Z, like before unlike for exactly two descriptors, r before s, R before S) is #232's, unchanged. 9 hypotheses are 4 distinct ones here, and the chain it picks is the book's.

**Measured here.** `tests/test_namer_stereo_parent_choice.py` (19 tests, among them the one added when #235 was merged with the P-45.2.3 change below): the book's molecule over 24 spellings and its descriptors per atom against RDKit's whole-molecule labels (through each prefix's `atom_origin`, with every labelled centre described exactly once); eight more stereoisomers of the skeleton, among them `4s`, `4r`, `6s`, `6r` pseudoasymmetric ones, 4 spellings each; the defect kept alive; nine chains are four choices; the bound counts distinct choices; and `_plan_identity` on made-up plans. Mutation-checked in the application, 9 of 9 caught.

**Measured in the application that vendors this package.** Against the tree it sat on: the census over 2000 rows 0 differences in name, read-back or class; a comparison over 1712 structures 0 names changed, 0 violations; a wider sweep of 60 random stereoisomers of the skeleton, 4 spellings each, 60 of 60 one name and right per atom (the same sweep on the #232 tip gave 12 of 12 sampled isomers two to four names).

**Left open (`KNOWN_LIMITATIONS.md`).** (a) Like before unlike is judged only for a parent with exactly two R/S descriptors, so for example 5's five-descriptor chain the choice is made by R before S, which agrees with the book here; a case where the two disagree (an all-S chain against a mixed one) is not exercised by anything. (b) The Blue Book applies P-44.4.1.12 BEFORE P-45.2.1 (the number of substituents), and the engine applies the choice only between plans that tie on the whole preference key, whose `substituent_count` and `prefix_locants` tiers come first; two chains that differ in configuration AND in substituent count would be chosen on the count. Read off the book's order and the key's tiers, not measured to occur. (c) More than 12 distinct tied hypotheses are still left to atom order. (d) The stamp branch of `_plan_identity` has no molecule that reaches it, only a unit test.

## 2026-10-06 -- P-45.2.3: of two parent structures that tie, the one whose prefixes have the lower locants in their order of citation

"The preferred IUPAC name is based on the senior parent structure that has the lower locant or set of locants for substituents cited as prefixes to the parent structure (other than 'hydro/dehydro' prefixes) in their order of citation in the name" (BlueBookV2.pdf p. 419). It comes after P-45.2.1 (the maximum number of prefixes) and P-45.2.2 (the lower locant SET), and both are tiers of the preference key, so two plans that tie on the key have the same set and only the order of citation is left: `3-chloro-7-[(4-chloro-3-nitroquinolin-7-yl)sulfanyl]-4-nitroquinoline` reads `3,7,4`, its rival `4,7,3`. The engine took whichever parent its plan order gave first, and plan order follows the order the SMILES atoms were written in, so one molecule had two names and both read back to it: nothing failed and no corpus row could see it.

**The rule.** `engine._break_parent_stereo_tie` is now `_break_parent_tie`. It still names each tied parent hypothesis as it would be named alone (its own numbering tie-break first, then up to `_PARENT_TIE_HYPOTHESES` DISTINCT ones: 4 when this was written, 12 since #235 counts choices and not chains), and no longer returns at once for a molecule that carries no stereo. `_senior_by_citation_locants` reads `_citation_locants` of each tree (`_alphanumerical_locant_key` flattened, so the locants are read as the name writes them: `1,5,1,6` before `1,6,1,5`, `N,3` before `3,N` by `Locant.__lt__`) and keeps the trees with the lowest value. The groups are flattened, not compared one prefix at a time, because between two PARENTS the prefixes are split differently (the book's example 8). It engages only when every tree is the same parent once prefixes and descriptors are set aside (`_parent_name_alone`: `quinoline`, `heptanoic acid`), which is the guard `_choose_by_configuration` already had for P-45.6: the key does not hold every criterion that tells two different parents apart, and a lower locant must not stand in for one. Hydro prefixes are not in `tree.prefixes`, so "other than hydro/dehydro" holds by construction (checked on a tetrahydronaphthalene). When it rules some parents out, the survivor (or, among survivors, the one P-45.6 prefers, else the first) is returned, because falling through would name the TOP plan's parent, which may be one just ruled out. What it leaves tied goes to P-45.6 for a molecule that carries stereo, and to plan order otherwise, as before. P-45.3, P-45.4 and P-45.5, which the book places between P-45.2.3 and P-45.6, are not applied across parents.

**The book prints fifteen examples, not five (pp. 420-422).** Over 13 random spellings each, before and after: examples 1, 2, 3, 4, 5, 7, 8, 10, 14 and 15 had the book's name 7, 4, 5, 8, 10, 8, 7, 8, 8 and 6 times and have it 13 of 13; the other name, the one the book says is not preferred, was the rest. Example 13 was already 13 of 13 (the book frames it as a choice between two numberings of one chain). Examples 6 and 9 are blocked by a criterion that comes first and is not implemented, **P-44.4.1.1** (p. 401, "the senior ... principal chain has the greater number of multiple bonds"): `strategy._parent_selection_score` counts unsaturation INFIXES, so a `1,3-diene` and a `1,3,13-triene` tie in `parent_selection`, and the `unsaturation_locants` tier that sees them next is only meaningful between numberings of one parent and ranks the shorter set higher. The engine names both molecules as a diene with an ethenyl substituent on 13 of 13 spellings (`12-ethenyl-8-(3-ethyl-4-methylhex-5-en-1-yl)-11-methyltetradeca-1,3-diene`); a throwaway patch that counts the bonds an infix names makes this rule give the book's name for both on 13 of 13, so it covers them once the count is right. Not shipped: the count would change the parent wherever two chains of equal length differ in the number of multiple bonds, which has not been measured and needs its own census. Examples 11 and 12 could not be named at all until D-191 and D-192 (xaerogonzo/OpenChem-Studio#238, merged while this was open) made the engine write a `[PH4]` group's lambda number and a labelled bromine's label; with both, this rule gives the book's name for them too, on 13 of 13 spellings each (example 11 in the engine's `lambda5` spelling, where the book prints the glyph). That closes #238's open defects D-194a and D-194b, and the six tests that pinned the rejected order (D-191p, D-192p, D-194a, D-194b and two rows of `tests/test_naming_providers.py`) moved to the book's names with it. The three examples of P-45.5 (the name earlier in alphanumerical order, `bromo` before `dibromo`) tie on this rule by the book's own words and are still two names over the spellings (the book's name 7 of 13, 5 of 13 and 6 of 13).

**A wrong molecule the rule exposed, and the fix.** `N,N'-dibenzoylhydrazine` came out as `N-benzoylbenzohydrazide`, which OPSIN reads as the N,N-diacyl isomer; `CC(=O)NNC(C)=O` as `N-acetylacetohydrazide`. The vendored suite's `test_fixed_defect_round_trips_end_to_end[D-075f]`, `[D-088a]` and `[D-117e]` caught it. The cause was not the rule. A diacylhydrazine has two hydrazide groups that share one N-N, and `_role_primes` (the N and N' roles of a hydrazide, thiohydrazide or amidine group) processed the group of the OTHER parent as well, whose roles then overwrote the first's: for the parent that came out second the terminal nitrogen was cited as `N`. Plan order took the other parent first for the two symmetric molecules (24 of 24 spellings of each, on the tree before), so nothing there was wrong until `N`, which is lower than `N'`, met the wrong tree; for an unsymmetrical one it did not, and `O=C(C=Cc1ccc(F)cc1)NNC(=O)Cc1ccccc1` was the 2000-row census's one `mismatch_same_formula` row (`3-(4-fluorophenyl)-N-(phenylacetyl)prop-2-enehydrazide`, now `...-N'-(phenylacetyl)...`). `_role_primes` now skips a group whose acyl carbon is neither in the parent nor bonded to it. A tie-break is only as good as the worst tree it is offered (the ester route's R-first tier and the P-14.4 (j) cache key said the same): the choice cannot be tested without also reading the candidates back.

**Merged with the parent choice among chains that differ only in configuration (the entry above).** Both changes rewrote `_break_parent_stereo_tie`: this one renamed it `_break_parent_tie` and put P-45.2.3 ahead of the configuration comparison, #235 counted DISTINCT hypotheses (`_plan_identity`, bound 12, so the nine equal chains of P-92.5.2.2 example 5 are four choices) and compared names assembled without descriptors. The merge keeps this change's names and steps and #235's identity and bound, and drops #235's "only a molecule that carries stereo" gate from the function's own scope, since P-45.2.3 has to reach achiral molecules and the configuration step keeps that gate for itself. **The two did not compose without a fix, and the tests said so:** `_citation_locants` read the prefixes with their descriptors, which decide how prefixes merge (`4,4-bis[...]` against `4-[...]-4-[...]`), so the four choices of example 5, which differ in nothing but configuration, had flattened locants `4,4,6,6` and `4,6,4,6`, and P-45.2.3 ruled two of them out before the configuration comparison saw them (#235's `test_nine_chains_are_four_choices` read 2 where it expects 4). The name was still the book's, 40 of 40 spellings, by that artefact. The book reads the locants "ignoring the configuration symbols" (P-45.6.2, p. 426), so `_citation_locants` now reads them with the descriptors set aside (`assembly.descriptors_set_aside`, which `assemble_without_stereo` uses too), `test_p_45_2_3_cannot_tell_the_four_choices_apart` pins it, and undoing it fails that test and #235's. The bound test of this change, written for 4, now reads the constant. Measured on the merged tree: both new test files 100 passed and 5 xfailed. (Found and fixed while merging #235 into this change, in a session that did only that; its resolution of the merge is what this paragraph describes.)

**Measured here.** `tests/test_namer_parent_citation_locants.py` (a fork variant of the application's: it skips on `java` on PATH, not on the application's OPSIN probe) pins the book's names over 16 spellings each, the same spellings splitting without the rule, the comparison and the wiring of `_break_parent_tie` on stand-in plans, the hydrazide cases, and the open defects as strict xfails; `tests/test_namer_known_defects.py` moves D-191p, D-192p, D-194a and D-194b to the book's names and to FIXED. `tools/fork_port.py` merged `engine.py` and `assembly.py` clean, numstat +188/-28 on both sides. The fork's full suite, run under the application's interpreter (RDKit 2025.09.6) with the JRE on PATH: 7,927 passed, 28 xfailed (the 15 that were open, D-193, D-194c, D-195 and D-196 of the open rows, and the five strict xfails of the P-45.2.3 test file; D-194a and D-194b passed and moved to FIXED), 0 failed, in 41 minutes.

**Measured in the application that vendors this package.** On the tree merged with master at `13ea375b`: the census over 2000 rows moves 3 rows (two this rule, `N` against a numeral, `exact` before and after, and one the hydrazide fix, `mismatch_same_formula` to `exact`), and over 7 spellings of every row 55 had more than one name on master and 50 do now; a comparison over 1712 structures changes 5 panel names (two of them the book's examples 3 and 15), 0 violations; the vendored suite 5634 passed, the naming-consumer session 3284 passed, 2 skipped, 28 xfailed. Thirteen mutations of the rule are each killed by its test file. CPU time to name the census, master and the new tree run side by side: 426.9 s and 431.9 s, then with the launch order swapped 412.5 s and 413.5 s, so the rule costs about 1% at most.

**Not done, measured, in `KNOWN_LIMITATIONS.md` ("Open after P-45.2.3"):** P-44.4.1.1; P-45.5 (and P-45.3, P-45.4 across parents; P-45.4.1's own example is D-194c).

## 2026-10-07 -- naming round 27: the principal chain has the greater number of multiple bonds (P-44.4.1.1)

BlueBookV2.pdf p. 401: "the senior ring, ring system or principal chain has the greater number of multiple bonds". `strategy._parent_selection_score` counted unsaturation INFIXES, and one infix names every bond of its kind, so `1,3-diene` and `1,3,13-triene` tied; the `unsaturation_locants` tier is only meaningful between numberings of one parent and ranks the SHORTER set higher across parents, so the diene with an ethenyl substituent won on every spelling. It counts the bonds the infixes name now (capped at 99 so the band stays under one chain atom).

* P-45.2.3 examples 6 and 9 (`...tetradeca-1,3,13-triene`, `...deca-1,3,9-triene`) are the book's name on 13 of 13 spellings; that makes fourteen of the fifteen decided by P-45.2.3 (13 was already stable). Their stand-in test, the "not reached today" pin and the strict xfail are gone from `tests/test_namer_parent_citation_locants.py`.
* Measured. Census (2000 rows): 0 moved, 1959 exact before and after, class counts identical. `tools/naming_ref_compare.py` against the tree before: 1712 panel rows, 0 changed, 0 violations, so there is no stage manifest. A 700-molecule sweep of random branched C7-C13 skeletons with 2+ multiple bonds (fixed seed) moved 238 names; every one reads back to its structure through OPSIN, and in every one the parent has the same number of carbons and strictly more multiple bonds (none shorter, none with fewer). Mostly `-ylidene`/`methylidene`/`prop-1-en-2-yl` substituents that became a longer-unsaturated parent: `2-methyl-3,4-dimethylidenepent-1-ene` is `2,4-dimethyl-3-methylidenepenta-1,4-diene`, `4-ethylidene-2,3-dimethylhex-1-ene` is `4-ethyl-2,3-dimethylhexa-1,4-diene`. The census sample has no such shape, which is why it did not move.
* Not changed, and measured: a longer chain with fewer bonds is still the parent (`3-ethenylnon-1-ene`); rings (`(cyclohex-2-en-1-yl)benzene`) and the ene/yne-against-diene tie are as before. P-44.4.1.2 (the greater number of DOUBLE bonds: `hepta-1,6-diene` before `hept-1-en-6-yne`, p. 402) is still not implemented: `C=CCCC(CCC=C)CCC#C` is three names over 12 spellings, all reading back exact (`5-(but-3-yn-1-yl)nona-1,8-diene` is the book's rule); pinned as a strict xfail in `tests/test_namer_multiple_bonds_parent.py`.
* New `tests/test_namer_multiple_bonds_parent.py` (a fork variant: it skips on `java` on PATH, not on the application's OPSIN probe); two of its tests fail on the tree before.

**Measured in the application that vendors this package** (xaerogonzo/OpenChem-Studio#245), against its master `3d895b5d`; the numbers above are from there.

## 2026-10-07 -- naming round 27, second rule: of parents that tie on P-45.2.3, the name earlier in alphanumerical order (P-45.5)

BlueBookV2.pdf p. 424: "The preferred IUPAC name is the name that is earlier in alphanumerical order. Alphabetic letters are considered first in the order that they appear in the name ... Then, if still there is a choice, numerical locants are considered in the order of their appearance." It follows P-45.2.3 (P-45.3 and P-45.4 between them are not applied across parents), so its examples are the ones that tie there ("the locants appear in the name in the same order ... but 'bromo' ... is earlier alphabetically than 'dibromo'"). They were two names over the spellings, chosen by the order the SMILES atoms were written in.

* `engine._senior_by_alphanumerical_order` runs in `_break_parent_tie` on the parents P-45.2.3 left, before the configuration comparison, and compares `_alphanumerical_letters`: the finished name (descriptors set aside) reduced to its letters, in order. Removed: locants (including a fusion locant's letter, `4a`), the italic locants and element symbols (`N`, `Se`, the `H` of `1H`), fusion descriptors (`[3,2-a]`), and hydro/dehydro prefixes, which are "not included in the category of alphabetized detachable prefixes" (P-31.1.4.2.4, pdf p. 75; `hydroxy` and `hydrogen` stay). The multiplying prefix stays, which is what puts `bromo` before `dibromo`. Same-parent guard as for P-45.2.3.
* **It declines** a name that carries a nuclide, a bonding number (`lambda`/`λ`) or an embedded `NAMING ERROR`: P-45.3 and P-45.4 come before this rule and are not applied across parents, so deciding such a tie by letters would decide it by the wrong rule (P-45.2.3's examples 11 and 12, and P-45.5's example 5, are all of that kind and are unchanged); two different broken names are not ordered.
* The book's examples 1, 2 and 4 are its name on 13 of 13 spellings (7, 7 and 10 of 13 before). Example 3 is a cyclophane the engine does not name. Example 5 (nuclides) stays two names, 9 and 4 of 13, both reading back exact: open, pinned.
* Measured. Census (2000 rows): 0 moved, class counts identical. `tools/naming_ref_compare.py`: 1712 panel rows, 9 names changed, all in `bluebook_tuning`, all 9 listed in `benchmarks/naming/stages/manifests/P45-5-alphanumerical-order.toml` with the reason (one is the book's own example 2), 0 violations once listed, every one reading back before and after. A 500-molecule sweep of two substituted benzene rings joined by N, O, S or a carbon linker (fixed seed), each named over 6 spellings on both trees: 21 molecules had more than one name before and none has now; every one is now the letters-earliest of the names it had, none was made unstable, no name appeared that the tree before did not give for that molecule, every new name reads back exact. (A first sweep of random substituted alkanes never reached a tie, 0 unstable on both trees, and measured nothing.)
* Found by measuring, not by the book's examples: the first version left a fusion locant's `a` (`4a`), a fusion descriptor's letters and the hydro prefixes in the letters. The census had one row move (exact before and after) because of the last; the book says hydro prefixes are not alphabetized, and with them out the census row does not move.
* One pinned shape moved, found by the application's own naming tests and by neither the census nor the panel: `tests/fixtures/naming_cation_shapes.txt` had `C[N+](C)([O-])CC[N+](C)(C)C` as `dimethyl(oxido)[2-(trimethylazaniumyl)ethyl]ammonium`, which was only the name of the canonical spelling: over 16 spellings the tree before gave it and `{2-[dimethyl(oxido)azaniumyl]ethyl}tri(methyl)ammonium` 8 and 8, and now the second on all 16 (earlier letters), both reading back exact. The fixture is updated; the `tri(methyl)` form is the engine's, in both. `test_without_the_rule_the_same_spellings_give_two_names` in `test_namer_parent_citation_locants.py` switches P-45.5 off as well as P-45.2.3, because P-45.5 also decides five of those examples (7, 8, 9, 10, 15) once P-45.2.3 is gone.
* New `tests/test_namer_alphanumerical_order.py` (39 tests: the book's examples, the split without the rule, what the letters exclude, what declines, the comparison on made-up trees, and `_break_parent_tie`'s wiring between P-45.2.3 and P-45.6). Mutants: 14 of the rule and its letter reading, all killed; two survived the first version of the tests (a two-letter italic locant, and the rule being applied to all parents instead of P-45.2.3's survivors) and have tests now.

**Measured in the application that vendors this package** (xaerogonzo/OpenChem-Studio#249); the numbers above are from there.

## 2026-10-07 -- naming round 28: a name keeps every nuclide (D-193), the lambda number of a single-bonded hypervalent centre (D-195), and the parent's bracket before the part it modifies (D-196)

D-193 was listed as four wrong molecules (`[15NH2]c1ccccc1` named `aniline`, `[15N]#CCC(=O)O` named `cyanoacetic acid`, ...). Measuring a labelled population showed it was not four cases: `isotope.collect_isotope_labels` dropped the label of any atom it could not locate, and every route that builds a name from parts of the molecule could lose a nuclide the same way, so the name read back as the unlabelled compound.

* **The guard.** `engine._check_nuclides_named` (called by `_name_smiles_bound` around the whole naming path) refuses a name that cites fewer atoms of a nuclide than the molecule has. `_nuclides_named` reads the isotope brackets and multiplies by the multiplier that encloses them (`1,2-di[(81Br)bromo]ethane` is two atoms; found when D-192m failed on a first version that counted brackets). A route nobody has found yet now raises, and the application shows a `NamingError`, instead of a name for another compound.
* **The routes that label their atoms.** `engine._isotope_atom_sites` (an atom a RETAINED parent name owns but does not number, alone of its element in the name: `(15N)aniline`, `4-chloro(15N)aniline`, `(18O)phenol`, `(15N)benzonitrile`; a suffix group's heteroatom of a systematic parent), `_isotopic_group_prefix` (a multi-atom prefix: `(15N)cyanoacetic acid`, `3-[(81Br)bromocarbonyl]propanoic acid`), `_isotopic_attachment_prefix` (the atom a heteroatom-rooted prefix hangs on: `(18O)methoxyacetic acid`), the hypohalous-amide parent (`dimethyl(81Br)hypobromous amide`), and `isotopic_prefix` itself, which now cites isotopic hydrogens on its atom with the atom's symbol as locant (`3-[(O-2H)hydroxy]propanoic acid`, `3-[(N,N-2H2)amino]propanoic acid`; OPSIN reads these and does not read `(2H)hydroxy`) and merges a second nuclide into an existing bracket (`[(1-13C,18O)methoxy]acetic acid`). A bare symbol is cited only when the element is alone in what it modifies (P-82.6.1.2): the first version labelled the nitrile CARBON of benzonitrile and OPSIN warned the position was ambiguous among seven carbons, and the ether route labelled one of two oxygens; both now stay unlabelled and are refused.
* **D-196 (placement).** `assembly._assemble_substitutive` cites the parent's bracket before the parent name, after the prefixes (`1-bromo(4-13C)butane`, `4-chloro(15N)aniline`) where it used to be the first thing in the name (`(4-13C)-1-bromobutane`, unreadable). `IsotopeLabel.at_suffix` marks a nuclide on a suffix group's heteroatom, cited before the suffix word after its locant: `1-phenylethan-1-(18O)one` (P-82.2.1, p. 853). A suffix with no locant keeps the front-of-name form.
* **D-195.** A hypervalent centre with no hydrogen and only single bonds takes its lambda number: `pentamethyl-lambda5-phosphane`, `pentamethoxy-lambda5-phosphane (PIN)` (p. 770), `pentaphenyl-lambda5-phosphane`, `pentamethyl-lambda5-arsane`, and `(tetramethyl-lambda5-phosphanyl)acetic acid`. A centre with a double bond already says its number and is unchanged.
* **Measured.** 400 census molecules with one atom labelled (13C, 15N or 18O on a random atom, or a deuterium on a heteroatom; fixed seed), named on master and on this tree and read back through OPSIN: master 89 exact, 86 wrong molecule, 205 unreadable, 20 naming errors; now 290 exact, 2 wrong, 40 unreadable, 20 naming errors, 48 refused. No name that was exact before changed. The two wrong are a label's locant on a bridged or polycyclic retained parent (a morphinan, a tetracyclo ring), where the engine's numbering is not OPSIN's; before, that locant was in front of the name and OPSIN could not read it, so it was invisible. Census (2000 rows): 0 moved. `tools/naming_ref_compare.py` against master: 1712 panel rows, 0 changed, so there is no stage manifest (the panels carry no isotope and no single-bonded hypervalent centre).
* New `tests/test_namer_nuclide_guard.py` (a fork variant: java on PATH, no application layer); the closed rows moved from OPEN to FIXED in `tests/test_namer_known_defects.py` (D-193a to D-193d, D-195, D-196a, D-196b, with the routes found beside them as D-193e to D-193l, D-195b, D-195c, D-196c, D-196d); `tests/test_naming_providers.py`'s example of a withheld name moved from `aniline` (now named) to two deuteriums on an aromatic amine (refused). D-194c is the one row still open of the group.

**Measured in the application that vendors this package** (xaerogonzo/OpenChem-Studio#250); the numbers above are from there.
