# Authenticated A2A Task Exchange

`sh scripts/lab.sh authenticated-a2a-test` creates a fresh Docker identity volume, bootstraps separate X.509 CAs and agent keys, starts the two official SDK agents in authentication-required mode, then tests signed tasks and negative cases.

The authenticated request is a JSON object carried in the official A2A Message text part. It includes a canonical signed body, the sender's CA-issued X.509 certificate, and an ECDSA signature. The server verifies the certificate under a configured domain CA and verifies possession of the corresponding private key before executing a task. Unknown CA, invalid signature, modified payload, wrong SAN, and stale timestamps are rejected. This is **application-layer message authentication**, not mTLS, not an official A2A authentication scheme, and not replay-proof: a fresh signed message can be replayed within the 60-second skew window. It is not DLT-backed DPKI. No production security guarantees should be inferred.

All identity files live only in a Docker volume and are deleted with `sh scripts/lab.sh stop`. The existing `official-a2a-test` remains an unauthenticated baseline.


## Authentication-required services

The baseline `sdk-agent-a`/`sdk-agent-b` explicitly set `A2A_REQUIRE_AUTH=0`. The isolated `auth-agent-a`/`auth-agent-b` explicitly set `A2A_REQUIRE_AUTH=1` in `compose.yaml`, with separate DNS endpoints and the shared ephemeral identity volume. The authenticated test runner verifies both running containers expose `A2A_REQUIRE_AUTH=1` before sending any tasks. The auth test must never target the baseline SDK endpoints.
