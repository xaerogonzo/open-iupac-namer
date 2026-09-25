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

## Open after naming round 16 (2026-09-25)

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
