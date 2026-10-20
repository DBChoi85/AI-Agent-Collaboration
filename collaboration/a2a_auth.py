"""Signed A2A task-envelope authentication (experimental, not DLT-backed DPKI)."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from .trust import TrustRejected, verify_agent_certificate

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def sign_envelope(source, payload, directory="/identities"):
    domain, agent = source.split("/", 1)
    root = Path(directory)
    key = serialization.load_pem_private_key((root / f"{domain}-{agent}.key").read_bytes(), password=None)
    body = {"source": source, "payload": payload, "issuedAt": int(time.time())}
    signature = key.sign(canonical(body), ec.ECDSA(hashes.SHA256()))
    return {"body": body, "certificate": (root / f"{domain}-{agent}.pem").read_text(),
            "signature": base64.b64encode(signature).decode()}

def verify_envelope(envelope, directory="/identities", now=None):
    try:
        if set(envelope) != {"body", "certificate", "signature"}:
            raise TrustRejected("invalid envelope structure")
        body = envelope["body"]
        if set(body) != {"source", "payload", "issuedAt"}:
            raise TrustRejected("invalid signed body")
        source = body["source"]
        domain, agent = source.split("/", 1)
        if not domain or not agent or "/" in agent:
            raise TrustRejected("invalid agent identity")
        timestamp = body["issuedAt"]
        current = int(now if now is not None else time.time())
        if type(timestamp) is not int or abs(current - timestamp) > 60:
            raise TrustRejected("stale or future-dated message")
        root = Path(directory)
        cert_pem = envelope["certificate"].encode()
        ca_pem = (root / f"{domain}-ca.pem").read_bytes()
        verify_agent_certificate(cert_pem, ca_pem, domain, agent,
                                 now=datetime.fromtimestamp(current, tz=timezone.utc))
        cert = x509.load_pem_x509_certificate(cert_pem)
        public = cert.public_key()
        if not isinstance(public, ec.EllipticCurvePublicKey):
            raise TrustRejected("unsupported agent signing key")
        public.verify(base64.b64decode(envelope["signature"], validate=True),
                      canonical(body), ec.ECDSA(hashes.SHA256()))
        return source, body["payload"]
    except (KeyError, ValueError, TypeError, AttributeError, OSError, InvalidSignature) as exc:
        if isinstance(exc, TrustRejected):
            raise
        raise TrustRejected("A2A message authentication failed") from exc
