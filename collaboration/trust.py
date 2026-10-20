"""Fail-closed X.509 trust adapter for disposable cross-domain agent experiments.

This is a PKI verification building block, NOT yet DLT-backed DPKI.
"""
from __future__ import annotations

from datetime import datetime, timezone
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding
from cryptography.x509.oid import ExtensionOID


class TrustRejected(ValueError):
    """Agent identity cannot be authenticated under the configured trust policy."""


def _check_signature(public_key, signature: bytes, payload: bytes, algorithm) -> None:
    try:
        if isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(signature, payload, ec.ECDSA(algorithm))
        elif isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(signature, payload, padding.PKCS1v15(), algorithm)
        else:
            raise TrustRejected("unsupported signing key")
    except InvalidSignature as exc:
        raise TrustRejected("invalid certificate signature") from exc


def verify_agent_certificate(
    certificate_pem: bytes,
    ca_pem: bytes,
    expected_domain: str,
    expected_agent: str,
    revoked_serials: frozenset[int] = frozenset(),
    now: datetime | None = None,
) -> str:
    """Verify one CA-signed leaf and return its authenticated domain/agent identity.

    CA certificates are trusted by explicit configuration; this does not discover
    CA keys or validate their on-chain directory commitments.
    """
    try:
        leaf = x509.load_pem_x509_certificate(certificate_pem)
        ca = x509.load_pem_x509_certificate(ca_pem)
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise TrustRejected("timezone-aware verification time required")
        for cert in (leaf, ca):
            if not (cert.not_valid_before_utc <= instant <= cert.not_valid_after_utc):
                raise TrustRejected("certificate outside validity interval")
        if leaf.issuer != ca.subject or ca.issuer != ca.subject:
            raise TrustRejected("issuer mismatch or non-self-issued trust anchor")
        ca_basic = ca.extensions.get_extension_for_class(x509.BasicConstraints).value
        if not ca_basic.ca:
            raise TrustRejected("trust anchor is not a CA")
        ca_usage = ca.extensions.get_extension_for_class(x509.KeyUsage).value
        if not ca_usage.key_cert_sign:
            raise TrustRejected("CA not authorized to sign certificates")
        leaf_basic = leaf.extensions.get_extension_for_class(x509.BasicConstraints).value
        if leaf_basic.ca:
            raise TrustRejected("CA certificate cannot authenticate as agent")
        leaf_usage = leaf.extensions.get_extension_for_class(x509.KeyUsage).value
        if not leaf_usage.digital_signature:
            raise TrustRejected("agent cannot sign")
        if leaf.serial_number in revoked_serials:
            raise TrustRejected("certificate revoked")
        san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        expected = f"spiffe://{expected_domain}/agent/{expected_agent}"
        if expected not in san.get_values_for_type(x509.UniformResourceIdentifier):
            raise TrustRejected("agent identity SAN mismatch")
        _check_signature(ca.public_key(), ca.signature, ca.tbs_certificate_bytes, ca.signature_hash_algorithm)
        _check_signature(ca.public_key(), leaf.signature, leaf.tbs_certificate_bytes, leaf.signature_hash_algorithm)
        return f"{expected_domain}/{expected_agent}"
    except (x509.ExtensionNotFound, ValueError, TypeError) as exc:
        if isinstance(exc, TrustRejected):
            raise
        raise TrustRejected("malformed or incomplete certificate") from exc
