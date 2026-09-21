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
