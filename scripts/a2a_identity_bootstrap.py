"""Create disposable independent domain CAs and agent keys inside a Docker volume."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
import os

ROOT = Path(os.environ.get("IDENTITY_DIR", "/identities"))
DOMAINS = [("domainA", "producer"), ("domainB", "consumer")]

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    start = datetime.now(timezone.utc) - timedelta(minutes=5)
    end = start + timedelta(hours=6)
    for domain, agent in DOMAINS:
        ca_key = ec.generate_private_key(ec.SECP256R1())
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, domain + "-CA")])
        ca_cert = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
            .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(start).not_valid_after(end)
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False,
                key_encipherment=False, data_encipherment=False, key_agreement=False,
                key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
            .sign(ca_key, hashes.SHA256()))
        agent_key = ec.generate_private_key(ec.SECP256R1())
        agent_cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, agent)]))
            .issuer_name(ca_name).public_key(agent_key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(start).not_valid_after(end)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                key_encipherment=False, data_encipherment=False, key_agreement=False,
                key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectAlternativeName([
                x509.UniformResourceIdentifier(f"spiffe://{domain}/agent/{agent}")]), critical=False)
            .sign(ca_key, hashes.SHA256()))
        (ROOT / f"{domain}-ca.pem").write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
        (ROOT / f"{domain}-{agent}.pem").write_bytes(agent_cert.public_bytes(serialization.Encoding.PEM))
        (ROOT / f"{domain}-{agent}.key").write_bytes(agent_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
    print("PASS: disposable per-domain CA and agent identities generated")

if __name__ == "__main__":
    main()
