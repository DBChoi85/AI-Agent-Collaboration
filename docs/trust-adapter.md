# X.509 trust adapter: PR #20

Run the standalone disposable trust adapter check:

```sh
sh scripts/lab.sh trust-test
```

Two independent CA private keys and two agent certificates are generated **in memory inside the ephemeral test container**, not loaded from existing host certificates. The trust adapter checks the explicit CA anchor, ECDSA/RSA signatures, X.509 validity, CA basic constraints/key usage, leaf signing usage, SPIFFE-style URI SAN binding, and a supplied revoked-serial set. Negative tests reject wrong domain, wrong agent, unknown CA, revoked, expired and malformed credentials.

**Scope boundary:** This is an X.509 PKI trust-verification foundation. It is not yet a DLT-anchored DPKI verifier, does not automatically query CRLs/OCSP or DLT directory commitments, and is not yet wired into A2A server authorization or collaboration membership. The subsequent integrated PR must fail closed before task execution, authenticate request possession of the leaf private key, and verify on-chain trust evidence. The in-memory revoked set is a test input, not a full revocation distribution mechanism.
