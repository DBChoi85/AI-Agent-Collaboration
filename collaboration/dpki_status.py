"""Fail-closed Besu certificate-status gate; experimental allowlist, not full DPKI."""
import hashlib
import json
from pathlib import Path
from cryptography import x509
from .chain import BesuRpc, RpcError
from .trust import TrustRejected

def require_onchain_active(certificate_pem: bytes, config_path="/chain/status.json"):
    try:
        cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
        cert = x509.load_pem_x509_certificate(certificate_pem)
        from cryptography.hazmat.primitives.serialization import Encoding
        digest = hashlib.sha256(cert.public_bytes(Encoding.DER)).hexdigest()
        address = cfg["address"]
        selector = cfg["isActiveSelector"]
        if not (isinstance(address, str) and len(address) == 42 and address.startswith("0x")
                and isinstance(selector, str) and len(selector) == 10 and selector.startswith("0x")):
            raise TrustRejected("invalid on-chain status configuration")
        rpc = BesuRpc(cfg["rpcUrl"], timeout=4)
        result = rpc.call("eth_call", [{"to": address, "data": selector + digest}, "latest"])
        if not isinstance(result, str) or not result.startswith("0x") or len(result) != 66:
            raise TrustRejected("invalid status contract response")
        value = int(result, 16)
        if value != 1:
            raise TrustRejected("certificate not active on Besu")
        return digest
    except (OSError, ValueError, KeyError, TypeError, RpcError) as exc:
        if isinstance(exc, TrustRejected):
            raise
        raise TrustRejected("on-chain certificate status unavailable or invalid") from exc
