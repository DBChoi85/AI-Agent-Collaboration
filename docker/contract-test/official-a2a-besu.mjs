import assert from 'node:assert/strict';
import fs from 'node:fs';
import solc from 'solc';
import { ethers } from 'ethers';

const inputPath = process.env.EVIDENCE_INPUT || '/evidence/authenticated-a2a.json';
const records = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
assert.equal(records.track, 'official-a2a-x509-evidence-v1');
assert.equal(records.records.length, 2, 'two authenticated directions required');
const source = fs.readFileSync('contracts/CollaborationRegistry.sol', 'utf8');
const input = { language: 'Solidity', sources: { 'CollaborationRegistry.sol': { content: source } },
  settings: { optimizer: { enabled: true, runs: 200 }, evmVersion: 'cancun',
    outputSelection: { '*': { '*': ['abi', 'evm.bytecode.object'] } } } };
const compiled = JSON.parse(solc.compile(JSON.stringify(input)));
const errors = (compiled.errors || []).filter(x => x.severity === 'error');
assert.equal(errors.length, 0, JSON.stringify(errors));
const artifact = compiled.contracts['CollaborationRegistry.sol'].CollaborationRegistry;
const provider = new ethers.JsonRpcProvider(process.env.BESU_RPC_URL || 'http://besu:8545');
let ready = false;
for (let attempt = 0; attempt < 60; attempt++) {
  try { await provider.getBlockNumber(); ready = true; break; }
  catch { await new Promise(resolve => setTimeout(resolve, 1000)); }
}
assert.ok(ready, 'Besu unavailable');
const latest = await provider.getBlock('latest');
assert.equal(latest.baseFeePerGas ?? 0n, 0n, 'zero-base-fee chain required');
const signer = new ethers.NonceManager(ethers.Wallet.createRandom().connect(provider));
const fee = { type: 0, gasPrice: 0n };
const factory = new ethers.ContractFactory(artifact.abi, '0x' + artifact.evm.bytecode.object, signer);
const estimate = await provider.estimateGas({ ...(await factory.getDeployTransaction(fee)), from: await signer.getAddress() });
const registry = await factory.deploy({ ...fee, gasLimit: estimate * 120n / 100n + 100000n });
async function mined(tx) {
  const receipt = await tx.wait(1, 90000);
  assert.ok(receipt && receipt.status === 1, 'transaction failed');
  return receipt;
}
await mined(registry.deploymentTransaction());
const collaborationId = ethers.id('official-a2a-' + crypto.randomUUID());
const ids = records.records.map(record => ethers.id(record.source));
assert.notEqual(ids[0], ids[1], 'independent domains required');
await mined(await registry.create(collaborationId, ids[0], fee));
await mined(await registry.join(collaborationId, ids[1], fee));
const results = [];
for (let i = 0; i < records.records.length; i++) {
  const record = records.records[i];
  assert.match(record.artifactSha256, /^0x[0-9a-f]{64}$/);
  assert.ok(record.artifactBytes > 0);
  const receipt = await mined(await registry.anchor(collaborationId, ids[i], record.artifactSha256, fee));
  const event = receipt.logs.map(log => {
    try { return registry.interface.parseLog(log); } catch { return null; }
  }).find(log => log?.name === 'EvidenceAnchored' && log.args.identity === ids[i]);
  assert.ok(event, 'evidence event not found');
  assert.equal(event.args.digest, record.artifactSha256, 'digest mismatch');
  results.push({ source: record.source, digest: record.artifactSha256,
    artifactBytes: record.artifactBytes, blockNumber: receipt.blockNumber,
    eventVerified: true });
}
assert.equal((await registry.collaborations(collaborationId)).sequence, 4n);
await mined(await registry.close(collaborationId, fee));
console.log('PASS: authenticated official A2A artifact hashes anchored to Besu in both directions');
console.log('OFFICIAL_A2A_BESU_RESULT=' + JSON.stringify({ track: 'official-a2a-x509-besu-artifact-v1',
  contract: await registry.getAddress(), collaborationId, results,
  caveat: 'post-task artifact anchoring only; no on-chain CA/DPKI validation or trust gate' }));
