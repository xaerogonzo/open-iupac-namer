"""Shapes no corpus row contains: a snapshot of their names, and a read-back of each (naming round 8; the fork's variant).

The application this package was written for reads names back through its own naming provider, which this package does not have. This
variant does the same two things on its own: the names are PINNED (a change fails until a person has looked and updated the fixture), and each is read back
through OPSIN and compared as the same compound on canonical SMILES, or on standard InChI where the only difference is a tautomer. A read-back alone cannot
see a PREFERENCE regression ('1,1-dimethylazinan-1-ium' still reads back as the right molecule), so both halves are needed.

Each structure is named in the RDKit CANONICAL spelling: the engine's output depends on atom order.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rdkit import Chem, RDLogger
from rdkit.Chem import inchi

from iupac_namer import name_smiles

FIXTURE = Path(__file__).parent / "fixtures" / "naming_cation_shapes.txt"

try:
    import py2opsin

    _HAVE_OPSIN = True
except Exception:  # pragma: no cover
    _HAVE_OPSIN = False


def _pinned() -> dict[str, str]:
    pinned: dict[str, str] = {}
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        smiles, _tab, name = line.partition("\t")
        assert name, f"a shape with no pinned name: {line!r}"
        assert smiles not in pinned, f"a shape is listed twice: {smiles}"
        pinned[smiles.strip()] = name.strip()
    return pinned


def _engine_name(smiles: str) -> str:
    return str(name_smiles(Chem.MolToSmiles(Chem.MolFromSmiles(smiles))))


def _same_compound(a: Chem.Mol, b: Chem.Mol) -> bool:
    if Chem.MolToSmiles(a) == Chem.MolToSmiles(b):
        return True
    ia, ib = inchi.MolToInchi(a), inchi.MolToInchi(b)
    return bool(ia) and ia == ib


def test_the_fixture_is_well_formed():
    pinned = _pinned()
    assert len(pinned) >= 100
    for smiles in pinned:
        assert Chem.MolFromSmiles(smiles) is not None, smiles


def test_no_pinned_name_has_moved():
    RDLogger.DisableLog("rdApp.*")
    moved = [
        f"{smiles}\n      pinned {pinned!r}\n      now    {now!r}"
        for smiles, pinned in _pinned().items()
        if (now := _engine_name(smiles)) != pinned
    ]
    assert not moved, f"{len(moved)} pinned names moved. If each is an intended improvement, update tests/fixtures/naming_cation_shapes.txt in the same commit:\n  " + "\n  ".join(moved)


@pytest.mark.skipif(not _HAVE_OPSIN, reason="py2opsin is not installed")
def test_every_pinned_name_is_read_back_as_the_same_compound():
    RDLogger.DisableLog("rdApp.*")
    pinned = _pinned()
    embedded = [f"{smiles} -> {name!r}" for smiles, name in pinned.items() if "NAMING ERROR" in name]
    assert not embedded, "an engine error is pinned as a name:\n  " + "\n  ".join(embedded)
    parsed = py2opsin.py2opsin(list(pinned.values()))
    failures = []
    for (smiles, name), got in zip(pinned.items(), parsed):
        mol = Chem.MolFromSmiles(smiles)
        candidate = Chem.MolFromSmiles(got) if got else None
        if candidate is None:
            failures.append(f"{smiles}\n      {name}\n      OPSIN could not read it")
        elif not _same_compound(candidate, mol):
            failures.append(f"{smiles}\n      {name}\n      reads back as {got}")
    assert not failures, f"{len(failures)} of {len(pinned)} pinned names no longer read back:\n  " + "\n  ".join(failures)
