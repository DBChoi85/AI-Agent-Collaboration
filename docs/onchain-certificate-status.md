# On-chain certificate status gate (experimental)

Run `bash scripts/lab.sh reset` followed by `bash scripts/lab.sh onchain-dpki-test` and `bash scripts/lab.sh stop`.

The test creates two independent domain CAs and agent X.509 certificates in a disposable Docker volume, compiles and deploys `AgentCertificateStatus.sol` on the local Besu chain, and registers the SHA-256 digest of each agent's DER-encoded certificate as active. A contract address and read-only call selector are passed to authentication-required official A2A SDK servers through a separate Docker volume.

The server first validates the existing X.509 certificate, SAN identity, ECDSA signed envelope, and timestamp. When `A2A_REQUIRE_DLT_STATUS=1`, it additionally performs a live `eth_call` against the registry's `isActive(bytes32)` function. Any RPC failure, absent registration, or revoked digest rejects the Task before an Artifact is produced.

The runner tests both domains active, then revokes domainA's certificate on-chain and verifies that the domainA sender's official A2A Task is rejected while domainB's Task still succeeds.

**Limitations:** The status registry is an administrator-controlled certificate digest allowlist, not a DPKI directory commitment, CA provenance verification, Merkle inclusion proof, or full CRL/OCSP replacement. Contract address and administrator are trusted bootstrap assumptions. This does not implement replay prevention. Certificates and keys remain off-chain. This is an integration test, not a performance benchmark.
