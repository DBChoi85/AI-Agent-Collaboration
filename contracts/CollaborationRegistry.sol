// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Stores only hashed agent identities and evidence digests.
/// @dev DPKI identity verification MUST occur at a trusted gateway before calling.
///      Gateway authorization is a deployment trust assumption, not on-chain PKI verification.
contract CollaborationRegistry {
    enum State { None, Active, Closed }
    struct Collaboration {
        address owner;
        State state;
        uint64 sequence;
        bytes32 head;
    }
    mapping(bytes32 => Collaboration) public collaborations;
    mapping(bytes32 => mapping(bytes32 => bool)) public members;

    event Created(bytes32 indexed id, address indexed owner, bytes32 indexed ownerIdentity, bytes32 head);
    event MemberJoined(bytes32 indexed id, bytes32 indexed identity, uint64 sequence, bytes32 head);
    event MemberLeft(bytes32 indexed id, bytes32 indexed identity, uint64 sequence, bytes32 head);
    event EvidenceAnchored(bytes32 indexed id, bytes32 indexed identity, bytes32 indexed digest, uint64 sequence, bytes32 head);
    event Closed(bytes32 indexed id, uint64 sequence, bytes32 head);

    error InvalidState();
    error Unauthorized();
    error DuplicateMember();
    error NotMember();
    error ZeroValue();

    modifier onlyOwner(bytes32 id) {
        if (collaborations[id].owner != msg.sender) revert Unauthorized();
        _;
    }

    function _advance(bytes32 id, bytes32 kind, bytes32 identity, bytes32 digest) internal returns (uint64, bytes32) {
        Collaboration storage c = collaborations[id];
        c.sequence++;
        c.head = keccak256(abi.encode(id, c.sequence, c.head, kind, identity, digest));
        return (c.sequence, c.head);
    }

    function create(bytes32 id, bytes32 ownerIdentity) external {
        if (id == bytes32(0) || ownerIdentity == bytes32(0)) revert ZeroValue();
        if (collaborations[id].state != State.None) revert InvalidState();
        Collaboration storage c = collaborations[id];
        c.owner = msg.sender;
        c.state = State.Active;
        members[id][ownerIdentity] = true;
        (, bytes32 head) = _advance(id, keccak256("CREATE"), ownerIdentity, bytes32(0));
        emit Created(id, msg.sender, ownerIdentity, head);
    }

    function join(bytes32 id, bytes32 identity) external onlyOwner(id) {
        if (collaborations[id].state != State.Active) revert InvalidState();
        if (identity == bytes32(0)) revert ZeroValue();
        if (members[id][identity]) revert DuplicateMember();
        members[id][identity] = true;
        (uint64 seq, bytes32 head) = _advance(id, keccak256("JOIN"), identity, bytes32(0));
        emit MemberJoined(id, identity, seq, head);
    }

    function leaveCollaboration(bytes32 id, bytes32 identity) external onlyOwner(id) {
        if (collaborations[id].state != State.Active) revert InvalidState();
        if (!members[id][identity]) revert NotMember();
        members[id][identity] = false;
        (uint64 seq, bytes32 head) = _advance(id, keccak256("LEAVE"), identity, bytes32(0));
        emit MemberLeft(id, identity, seq, head);
    }

    function anchor(bytes32 id, bytes32 identity, bytes32 digest) external onlyOwner(id) {
        if (collaborations[id].state != State.Active) revert InvalidState();
        if (!members[id][identity]) revert NotMember();
        if (digest == bytes32(0)) revert ZeroValue();
        (uint64 seq, bytes32 head) = _advance(id, keccak256("EVIDENCE"), identity, digest);
        emit EvidenceAnchored(id, identity, digest, seq, head);
    }

    function close(bytes32 id) external onlyOwner(id) {
        if (collaborations[id].state != State.Active) revert InvalidState();
        (uint64 seq, bytes32 head) = _advance(id, keccak256("CLOSE"), bytes32(0), bytes32(0));
        collaborations[id].state = State.Closed;
        emit Closed(id, seq, head);
    }
}
