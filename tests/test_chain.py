import io
import json
import unittest
from unittest.mock import patch
from collaboration.chain import BesuRpc, RpcError


class Response(io.BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()


class ChainTests(unittest.TestCase):
    def test_status(self):
        seen = []
        def fake_open(request, timeout):
            body = json.loads(request.data)
            seen.append(body["method"])
            result = "0x539" if body["method"] == "eth_chainId" else "0xa"
            return Response(json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode())
        with patch("collaboration.chain.urlopen", side_effect=fake_open):
            self.assertEqual(BesuRpc("http://localhost:8545").status(), {"chain_id": 1337, "block_number": 10})
        self.assertEqual(seen, ["eth_chainId", "eth_blockNumber"])

    def test_rpc_error(self):
        with patch("collaboration.chain.urlopen", return_value=Response(
            b'{"jsonrpc":"2.0","id":1,"error":{"code":-1}}')):
            with self.assertRaises(RpcError):
                BesuRpc("http://localhost:8545").status()

    def test_invalid_url(self):
        with self.assertRaises(ValueError):
            BesuRpc("file:///etc/passwd")


if __name__ == "__main__":
    unittest.main()
