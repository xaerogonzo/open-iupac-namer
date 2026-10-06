"""Naming round 24: the morphinan family is named on the retained parent, not as a von Baeyer pentacycle.

Blue Book P-13.8.1.1 (p. 66) prints morphine as "4,5alpha-epoxy-17-methyl-7,8-didehydromorphinan-3,6alpha-diol". Names were read back through
OPSIN to the input structure, stereo included, when the names were chosen; here the engine's output is pinned. Needs `java` on PATH, because the engine
confirms its own bridged-ring stereo with OPSIN and drops what it cannot confirm.
"""
import shutil

import pytest
from rdkit import Chem

from iupac_namer import name_smiles

pytestmark = pytest.mark.skipif(shutil.which("java") is None, reason="needs java on PATH (the engine's own OPSIN stereo check)")

FAMILY = [
    ("morphine", "CN1CC[C@]23[C@@H]4[C@H]1CC5=C2C(=C(C=C5)O)O[C@H]3[C@H](C=C4)O",
     "(5R,6S,9R,13S,14R)-4,5-epoxy-17-methyl-7,8-didehydromorphinan-3,6-diol"),
    ("codeine", "COc1ccc2C[C@H]3N(C)CC[C@@]45[C@@H](Oc1c24)[C@@H](O)C=C[C@@H]35",
     "(5R,6S,9R,13S,14R)-4,5-epoxy-3-methoxy-17-methyl-7,8-didehydromorphinan-6-ol"),
    ("heroin", "CC(=O)O[C@H]1C=C[C@H]2[C@H]3Cc4ccc(OC(C)=O)c5O[C@@H]1[C@]2(CCN3C)c45",
     "(5R,6S,9R,13S,14R)-4,5-epoxy-17-methyl-7,8-didehydromorphinan-3,6-diyl diacetate"),
    ("hydromorphone", "CN1CC[C@]23[C@@H]4C(=O)CC[C@]2([C@H]1CC5=C3C(=C(C=C5)O)O4)O",
     "(5R,9R,13S,14S)-4,5-epoxy-3,14-dihydroxy-17-methylmorphinan-6-one"),
    ("oxycodone", "COc1ccc2C[C@H]3N(C)CC[C@@]45[C@@H](Oc1c24)C(=O)CC[C@@]35O",
     "(5R,9R,13S,14S)-4,5-epoxy-14-hydroxy-3-methoxy-17-methylmorphinan-6-one"),
    ("naloxone", "C=CCN1CC[C@]23[C@@H]4C(=O)CC[C@]2([C@H]1Cc1ccc(O)c(O4)c13)O",
     "(5R,9R,13S,14S)-4,5-epoxy-3,14-dihydroxy-17-(prop-2-en-1-yl)morphinan-6-one"),
    ("thebaine", "COC1=CC=C2[C@H]3Cc4ccc(OC)c5O[C@@H]1[C@]2(CCN3C)c45",
     "(5R,9R,13S)-4,5-epoxy-3,6-dimethoxy-17-methyl-6,7,8,14-tetradehydromorphinan"),
    # the molecule that started the round (a diacetoxy-oxo morphinan, drawn in the app)
    ("3,14-diacetoxy-6-oxo", "CC(=O)Oc1ccc2c3c1O[C@H]1C(=O)CC[C@@]4(OC(C)=O)[C@@H](C2)N(C)CC[C@]314",
     "(5R,9R,13S,14S)-4,5-epoxy-17-methyl-6-oxomorphinan-3,14-diyl diacetate"),
]


# Round 26: the two diacetates are the esters of ONE polyol with ONE acid, so they take the book's `<organyl>-diyl diacetate`
# (P-65.6.3.3.3.1) instead of the acyloxy form round 24 pinned. OPSIN reads both back to the input structure, stereo included.
@pytest.mark.parametrize("label,smiles,expected", FAMILY, ids=[f[0] for f in FAMILY])
def test_morphinan_family_name(label, smiles, expected):
    assert name_smiles(Chem.MolToSmiles(Chem.MolFromSmiles(smiles))) == expected


def test_the_retained_lookup_still_names_the_plain_skeleton():
    assert name_smiles("CN1CCC23CCCCC2C1Cc1ccc(O)cc13").endswith("17-methylmorphinan-3-ol")
