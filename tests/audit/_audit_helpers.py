"""Round-trip helper that three test files import but that was never
committed.

``test_fr_orientation_numbering``, ``test_retained_rings`` and
``test_skeletal_chain_replacement`` all do
``from tests.audit._audit_helpers import assert_round_trip``, but
``tests/audit/`` is absent from the repository -- so the first of those
files fails to COLLECT and the suite reports its neighbours as errors
too.

Reconstructed from how the callers use it, and from the criterion the
rest of the suite already applies: a generated name is right when
parsing it back with OPSIN yields the structure it came from.

Like the other OPSIN-dependent tests here it degrades to a skip when
``py2opsin`` is unavailable, rather than failing on a missing optional
dependency.  ``py2opsin`` is declared in the ``test`` extra and shells
out to a JRE, so Java has to be on PATH as well.
"""

from __future__ import annotations

import pytest
from rdkit import Chem

from iupac_namer import name_smiles

try:
    from py2opsin import py2opsin
    HAVE_OPSIN = True
except ImportError:
    HAVE_OPSIN = False


def assert_round_trip(smiles: str) -> str:
    """Name ``smiles``, parse the name back, and assert it is the same
    molecule.  Returns the name so callers can assert further on it."""
    original = Chem.MolFromSmiles(smiles)
    assert original is not None, f"test input is not valid SMILES: {smiles}"

    name = name_smiles(smiles)
    assert name, f"no name was generated for {smiles}"

    if not HAVE_OPSIN:
        pytest.skip("py2opsin is not installed; cannot verify the round trip")

    # py2opsin returns "" (or [""]) for a name it cannot parse, and False
    # if it fell over internally.  None of those is a SMILES.
    result = py2opsin(str(name).strip(), output_format="SMILES")
    parsed = result[0] if isinstance(result, list) and result else result
    assert parsed, f"OPSIN could not parse {name!r} (from {smiles})"

    round_tripped = Chem.MolFromSmiles(parsed)
    assert round_tripped is not None, (
        f"OPSIN returned unparseable SMILES for {name!r}: {parsed!r}"
    )
    assert Chem.MolToSmiles(round_tripped) == Chem.MolToSmiles(original), (
        f"{name!r} parses back to a different structure:\n"
        f"  expected {Chem.MolToSmiles(original)}\n"
        f"  got      {Chem.MolToSmiles(round_tripped)}"
    )
    return str(name)
