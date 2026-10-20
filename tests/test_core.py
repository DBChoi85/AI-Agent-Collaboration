import unittest
from dataclasses import replace
from collaboration.core import CollaborationRegistry, Participant, SharedResource


class TestOnlyVerifier:
    """Not suitable for deployment: test fixture, no cryptographic verification."""
    def verify(self, domain, agent):
        return (domain, agent) in {("A", "alpha"), ("B", "beta")}


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.registry = CollaborationRegistry(TestOnlyVerifier())
        self.a = Participant("A", "alpha")
        self.b = Participant("B", "beta")
        self.c = self.registry.create(self.a)

    def test_default_deny(self):
        with self.assertRaises(PermissionError):
            CollaborationRegistry().create(self.a)

    def test_membership_and_evidence(self):
        with self.assertRaises(PermissionError):
            self.registry.record(self.c.identifier, self.b, "data_shared", b"secret")
        self.registry.join(self.c.identifier, self.a, self.b)
        ev = self.registry.record(self.c.identifier, self.b, "artifact_shared", b"result")
        self.assertEqual(ev.payload_hash, SharedResource.from_bytes(
            self.c.identifier, "t1", "r1", self.b, "text/plain", b"result").content_hash)
        self.assertTrue(self.registry.verify_evidence(self.c))
        self.c.evidence[-1] = replace(ev, payload_hash="0" * 64)
        self.assertFalse(self.registry.verify_evidence(self.c))

    def test_lifecycle(self):
        with self.assertRaises(PermissionError):
            self.registry.close(self.c.identifier, self.b)
        self.registry.close(self.c.identifier, self.a)
        with self.assertRaises(ValueError):
            self.registry.record(self.c.identifier, self.a, "data_shared", b"x")

    def test_resource_integrity(self):
        resource = SharedResource.from_bytes(self.c.identifier, "t1", "r1", self.a, "application/json", b'{"ok":true}')
        self.assertTrue(resource.verify(b'{"ok":true}'))
        self.assertFalse(resource.verify(b'{"ok":false}'))

    def test_unauthorized_join(self):
        with self.assertRaises(PermissionError):
            self.registry.join(self.c.identifier, self.b, self.a)


if __name__ == "__main__":
    unittest.main()
