"""Property-based tests for the VerifiedPrincipal value object (Phase C).

VerifiedPrincipal is what TokenVerifier.verify() returns on success;
it's the payload BearerAuthMiddleware stashes on request.state. The
properties pin its dataclass semantics — equality, hash, immutability
of the frozenset scopes — against accidental regression if the shape
ever shifts (e.g. someone makes scopes a list and breaks dedup).

Iter C of the testing-techniques rollout.
"""

from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.infrastructure.ports.token_verifier import PrincipalKind, VerifiedPrincipal

_KIND = st.sampled_from(["human", "service_account"])
_NON_EMPTY_TEXT = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=64,
)
_SCOPE_SET = st.frozensets(
    st.text(
        alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
        min_size=1,
        max_size=32,
    ),
    max_size=8,
)


@pytest.mark.unit
@given(
    principal_id=st.uuids(),
    subject=_NON_EMPTY_TEXT,
    issuer=_NON_EMPTY_TEXT,
    kind=_KIND,
    scopes=_SCOPE_SET,
)
def test_verified_principal_constructs_for_any_valid_5_tuple(
    principal_id: UUID,
    subject: str,
    issuer: str,
    kind: PrincipalKind,
    scopes: frozenset[str],
) -> None:
    """Any well-typed 5-tuple builds without validation friction."""
    vp = VerifiedPrincipal(
        principal_id=principal_id,
        subject=subject,
        issuer=issuer,
        kind=kind,
        scopes=scopes,
    )
    assert vp.principal_id == principal_id
    assert vp.subject == subject
    assert vp.issuer == issuer
    assert vp.kind == kind
    assert vp.scopes == scopes


@pytest.mark.unit
@given(
    principal_id=st.uuids(),
    subject=_NON_EMPTY_TEXT,
    issuer=_NON_EMPTY_TEXT,
    kind=_KIND,
    scopes=_SCOPE_SET,
)
def test_verified_principal_equality_is_reflexive(
    principal_id: UUID,
    subject: str,
    issuer: str,
    kind: PrincipalKind,
    scopes: frozenset[str],
) -> None:
    vp = VerifiedPrincipal(
        principal_id=principal_id,
        subject=subject,
        issuer=issuer,
        kind=kind,
        scopes=scopes,
    )
    assert vp == vp
    assert hash(vp) == hash(vp)


@pytest.mark.unit
@given(
    principal_id=st.uuids(),
    subject=_NON_EMPTY_TEXT,
    issuer=_NON_EMPTY_TEXT,
    kind=_KIND,
    scopes=_SCOPE_SET,
)
def test_verified_principal_eq_implies_hash_eq(
    principal_id: UUID,
    subject: str,
    issuer: str,
    kind: PrincipalKind,
    scopes: frozenset[str],
) -> None:
    """Two VPs built from identical fields are equal AND share a hash
    (Python's hash/eq contract; pinned because someone could
    accidentally override __eq__ on a refactor)."""
    a = VerifiedPrincipal(
        principal_id=principal_id,
        subject=subject,
        issuer=issuer,
        kind=kind,
        scopes=scopes,
    )
    b = VerifiedPrincipal(
        principal_id=principal_id,
        subject=subject,
        issuer=issuer,
        kind=kind,
        scopes=scopes,
    )
    assert a == b
    assert hash(a) == hash(b)


@pytest.mark.unit
@given(
    principal_id=st.uuids(),
    subject=_NON_EMPTY_TEXT,
    issuer=_NON_EMPTY_TEXT,
    kind=_KIND,
    scopes=_SCOPE_SET,
)
def test_verified_principal_is_frozen(
    principal_id: UUID,
    subject: str,
    issuer: str,
    kind: PrincipalKind,
    scopes: frozenset[str],
) -> None:
    """Frozen dataclass: assignment to fields raises FrozenInstanceError."""
    vp = VerifiedPrincipal(
        principal_id=principal_id,
        subject=subject,
        issuer=issuer,
        kind=kind,
        scopes=scopes,
    )
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        vp.subject = "tampered"  # pyright: ignore[reportAttributeAccessIssue]
