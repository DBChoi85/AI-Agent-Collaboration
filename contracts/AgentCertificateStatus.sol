// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Experimental on-chain certificate digest allowlist/status registry.
/// @dev Administrator registration is an explicit trust assumption; this is NOT
///      a Merkle directory commitment or full PKI revocation infrastructure.
contract AgentCertificateStatus {
    address public immutable administrator;
    mapping(bytes32 => bool) public active;
    event CertificateStatus(bytes32 indexed certificateDigest, bool active);
    error Unauthorized();
    error ZeroDigest();
    constructor() { administrator = msg.sender; }
    function setStatus(bytes32 digest, bool enabled) external {
        if (msg.sender != administrator) revert Unauthorized();
        if (digest == bytes32(0)) revert ZeroDigest();
        active[digest] = enabled;
        emit CertificateStatus(digest, enabled);
    }
    function isActive(bytes32 digest) external view returns (bool) {
        return active[digest];
    }
}
