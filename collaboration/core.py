"""Fail-closed, transport-independent collaboration reference core."""
from __future__ import annotations
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Protocol
import json
import uuid


class TrustVerifier(Protocol):
    def verify(self, domain: str, agent: str) -> bool: ...


class DenyAllVerifier:
    def verify(self, domain: str, agent: str) -> bool:
        return False


@dataclass(frozen=True)
class Participant:
    domain: str
    agent: str


@dataclass(frozen=True)
class Evidence:
    collaboration_id: str
    sequence: int
    actor: Participant
    event: str
    payload_hash: str
    previous_hash: str
    commitment: str


@dataclass
class Collaboration:
    identifier: str
    owner: Participant
    participants: set[Participant] = field(default_factory=set)
    active: bool = True
    evidence: list[Evidence] = field(default_factory=list)


class CollaborationRegistry:
    """In-memory lifecycle + hash-chain evidence; not a substitute for DLT consensus."""

    def __init__(self, verifier: TrustVerifier | None = None):
        self.verifier = verifier or DenyAllVerifier()
        self.collaborations: dict[str, Collaboration] = {}

    def _trusted(self, actor: Participant) -> None:
        if not self.verifier.verify(actor.domain, actor.agent):
            raise PermissionError("DPKI trust verification failed")

    @staticmethod
    def _commit(c: Collaboration, actor: Participant, event: str, payload: bytes) -> Evidence:
        previous = c.evidence[-1].commitment if c.evidence else "0" * 64
        seq = len(c.evidence) + 1
        payload_hash = sha256(payload).hexdigest()
        record = json.dumps(
            {"collaboration": c.identifier, "sequence": seq, "domain": actor.domain,
             "agent": actor.agent, "event": event, "payload_hash": payload_hash,
             "previous_hash": previous}, sort_keys=True, separators=(",", ":")
        ).encode()
        ev = Evidence(c.identifier, seq, actor, event, payload_hash, previous, sha256(record).hexdigest())
        c.evidence.append(ev)
        return ev

    def create(self, owner: Participant) -> Collaboration:
        self._trusted(owner)
        c = Collaboration(str(uuid.uuid4()), owner, {owner})
        self.collaborations[c.identifier] = c
        self._commit(c, owner, "created", b"")
        return c

    def join(self, cid: str, owner: Participant, entrant: Participant) -> Evidence:
        c = self._get_active(cid)
        self._trusted(owner)
        self._trusted(entrant)
        if owner != c.owner:
            raise PermissionError("only owner may admit participants")
        if entrant in c.participants:
            raise ValueError("participant already joined")
        c.participants.add(entrant)
        return self._commit(c, owner, "joined", f"{entrant.domain}/{entrant.agent}".encode())

    def record(self, cid: str, actor: Participant, event: str, payload: bytes) -> Evidence:
        c = self._get_active(cid)
        self._trusted(actor)
        if actor not in c.participants:
            raise PermissionError("not a collaboration participant")
        if event not in {"data_shared", "artifact_shared", "task_completed"}:
            raise ValueError("unsupported event")
        return self._commit(c, actor, event, payload)

    def close(self, cid: str, actor: Participant) -> Evidence:
        c = self._get_active(cid)
        self._trusted(actor)
        if actor != c.owner:
            raise PermissionError("only owner may close")
        ev = self._commit(c, actor, "closed", b"")
        c.active = False
        return ev

    def _get_active(self, cid: str) -> Collaboration:
        c = self.collaborations[cid]
        if not c.active:
            raise ValueError("collaboration closed")
        return c

    @staticmethod
    def verify_evidence(c: Collaboration) -> bool:
        previous = "0" * 64
        for index, ev in enumerate(c.evidence, 1):
            if ev.collaboration_id != c.identifier or ev.sequence != index or ev.previous_hash != previous:
                return False
            record = json.dumps(
                {"collaboration": ev.collaboration_id, "sequence": ev.sequence,
                 "domain": ev.actor.domain, "agent": ev.actor.agent,
                 "event": ev.event, "payload_hash": ev.payload_hash,
                 "previous_hash": ev.previous_hash}, sort_keys=True, separators=(",", ":")
            ).encode()
            if sha256(record).hexdigest() != ev.commitment:
                return False
            previous = ev.commitment
        return True


@dataclass(frozen=True)
class SharedResource:
    collaboration_id: str
    task_id: str
    resource_id: str
    owner: Participant
    media_type: str
    content_hash: str

    @classmethod
    def from_bytes(cls, collaboration_id: str, task_id: str, resource_id: str,
                   owner: Participant, media_type: str, content: bytes) -> "SharedResource":
        return cls(collaboration_id, task_id, resource_id, owner, media_type, sha256(content).hexdigest())

    def verify(self, content: bytes) -> bool:
        return sha256(content).hexdigest() == self.content_hash
