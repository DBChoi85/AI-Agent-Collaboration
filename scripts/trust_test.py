"""Disposable two-domain X.509 identity verification and fail-closed cases."""
from datetime import datetime, timedelta, timezone
import json

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from collaboration.trust import TrustRejected, verify_agent_certificate


def key():
    return ec.generate_private_key(ec.SECP256R1())


def pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM)


def name(value):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, value)])


def make_ca(domain, start, end):
    private = key()
    subject = name(domain + "-CA")
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(private.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(start).not_valid_after(end)
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False,
                key_encipherment=False, data_encipherment=False, key_agreement=False,
                key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
            .sign(private, hashes.SHA256()))
    return private, cert


def make_agent(ca_key, ca, domain, agent, start, end):
    private = key()
    cert = (x509.CertificateBuilder().subject_name(name(agent)).issuer_name(ca.subject)
            .public_key(private.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(start).not_valid_after(end)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                key_encipherment=False, data_encipherment=False, key_agreement=False,
                key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectAlternativeName([
                x509.UniformResourceIdentifier(f"spiffe://{domain}/agent/{agent}")]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    return cert


def reject(label, *args, **kwargs):
    try:
        verify_agent_certificate(*args, **kwargs)
    except TrustRejected:
        return label
    raise AssertionError("FAIL OPEN: " + label)


def main():
    now = datetime.now(timezone.utc)
    start, end = now - timedelta(hours=1), now + timedelta(hours=2)
    ca_a_key, ca_a = make_ca("domainA", start, end)
    ca_b_key, ca_b = make_ca("domainB", start, end)
    agent_a = make_agent(ca_a_key, ca_a, "domainA", "producer", start, end)
    agent_b = make_agent(ca_b_key, ca_b, "domainB", "consumer", start, end)
    valid = [
        verify_agent_certificate(pem(agent_a), pem(ca_a), "domainA", "producer"),
        verify_agent_certificate(pem(agent_b), pem(ca_b), "domainB", "consumer"),
    ]
    assert valid == ["domainA/producer", "domainB/consumer"]
    expired = make_agent(ca_a_key, ca_a, "domainA", "producer",
                         now - timedelta(days=2), now - timedelta(days=1))
    negative = [
        reject("wrong-domain", pem(agent_a), pem(ca_a), "domainB", "producer"),
        reject("wrong-agent", pem(agent_a), pem(ca_a), "domainA", "consumer"),
        reject("untrusted-ca", pem(agent_a), pem(ca_b), "domainA", "producer"),
        reject("revoked", pem(agent_a), pem(ca_a), "domainA", "producer",
               revoked_serials=frozenset({agent_a.serial_number})),
        reject("expired", pem(expired), pem(ca_a), "domainA", "producer"),
        reject("malformed", b"not a certificate", pem(ca_a), "domainA", "producer"),
    ]
    print("PASS: disposable two-domain X.509 trust verification and fail-closed negative tests")
    print("TRUST_RESULT=" + json.dumps({"track": "x509-trust-adapter-v1", "accepted": valid,
        "rejected": negative, "caveat": "offline trust adapter only; not yet an A2A enforcement point or DLT-backed DPKI"}))


if __name__ == "__main__":
    main()
