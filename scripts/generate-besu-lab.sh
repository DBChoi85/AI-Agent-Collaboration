#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ -e local-besu-lab ]; then
  echo "Refusing to reuse existing local-besu-lab; run sh scripts/lab.sh reset" >&2
  exit 1
fi
mkdir -p local-besu-lab
# The config is ephemeral and is used only to generate a single-validator QBFT genesis.
cat > local-besu-lab/config.json <<'EOF'
{
  "genesis": {
    "config": {
      "chainId": 1337,
      "londonBlock": 0,
      "shanghaiTime": 0,
      "cancunTime": 0,
      "zeroBaseFee": true,
      "qbft": {
        "blockperiodseconds": 2,
        "epochlength": 30000,
        "requesttimeoutseconds": 4
      }
    },
    "nonce": "0x0",
    "timestamp": "0x0",
    "gasLimit": "0x1c9c380",
    "difficulty": "0x1",
    "mixHash": "0x63746963616c2062797a616e74696e65206661756c7420746f6c6572616e6365",
    "coinbase": "0x0000000000000000000000000000000000000000",
    "alloc": {}
  },
  "blockchain": {
    "nodes": {
      "generate": true,
      "count": 1
    }
  }
}
EOF
docker run --rm -v "$(pwd)/local-besu-lab:/lab" --entrypoint /opt/besu/bin/besu hyperledger/besu:25.9.0 operator generate-blockchain-config --config-file=/lab/config.json --to=/lab/generated --private-key-file-name=key
cp local-besu-lab/generated/genesis.json local-besu-lab/genesis.json
key_file=$(find local-besu-lab/generated/keys -type f -name key | head -n 1)
[ -n "$key_file" ] || { echo "QBFT validator key was not generated" >&2; exit 1; }
cp "$key_file" local-besu-lab/key
chmod 600 local-besu-lab/key
echo "Generated disposable QBFT genesis and validator key"
