import assert from 'node:assert/strict';
import fs from 'node:fs';
import solc from 'solc';
import { ethers } from 'ethers';

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const rpc = process.env.BESU_RPC_URL || 'http://besu:8545';
const a = process.env.AGENT_A_URL || 'http://agent-a:8080';
const b = process.env.AGENT_B_URL || 'http://agent-b:8080';
const provider = new ethers.JsonRpcProvider(rpc);
async function retry(label, action) {
  let last;
  for (let i = 0; i < 45; i++) {
    try { return await action(); }
    catch (e) { last = e; await sleep(1000); }
  }
  throw new Error(label + ' unavailable: ' + last?.message);
}
await retry('Besu', () => provider.getBlockNumber());
for (const [label, url] of [['agent-a', a], ['agent-b', b]]) {
  await retry(label, async () => {
    const response = await fetch(url + '/health');
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const status = await response.json();
    assert.equal(status.status, 'ready');
  });
}
const source = fs.readFileSync('contracts/CollaborationRegistry.sol', 'utf8');
const input = { language: 'Solidity',
  sources: { 'CollaborationRegistry.sol': { content: source } },
  settings: { optimizer: { enabled: true, runs: 200 }, evmVersion: 'cancun',
    outputSelection: { '*': { '*': ['abi', 'evm.bytecode.object'] } } } };
const compiled = JSON.parse(solc.compile(JSON.stringify(input)));
for (const issue of compiled.errors || []) {
  if (issue.severity === 'error') throw new Error(issue.formattedMessage);
  console.warn(issue.formattedMessage);
}
const artifact = compiled.contracts['CollaborationRegistry.sol'].CollaborationRegistry;
const block = await provider.getBlock('latest');
assert.equal(block.baseFeePerGas ?? 0n, 0n, 'zero-base-fee chain required');
const signer = new ethers.NonceManager(ethers.Wallet.createRandom().connect(provider));
const fee = { type: 0, gasPrice: 0n };
const factory = new ethers.ContractFactory(artifact.abi, '0x' + artifact.evm.bytecode.object, signer);
const estimate = await provider.estimateGas({ ...(await factory.getDeployTransaction(fee)), from: await signer.getAddress() });
const registry = await factory.deploy({ ...fee, gasLimit: estimate * 120n / 100n + 100_000n });
async function mined(tx) {
  const receipt = await tx.wait(1, 90000);
  assert.ok(receipt && receipt.status === 1, 'transaction failed or timed out');
  return receipt;
}
await mined(registry.deploymentTransaction());
const collaborationId = ethers.id('integrated-' + crypto.randomUUID());
const identities = [ethers.id('domainA/producer'), ethers.id('domainB/consumer')];
await mined(await registry.create(collaborationId, identities[0], fee));
await mined(await registry.join(collaborationId, identities[1], fee));

const results = [];
for (const [sourceName, url, identity] of [
  ['domainA/producer', b, identities[1]],
  ['domainB/consumer', a, identities[0]]
]) {
  const cardResponse = await fetch(url + '/.well-known/agent-card.json');
  assert.ok(cardResponse.ok);
  const card = await cardResponse.json();
  assert.ok(card.url.endsWith('/a2a'));
  const request = { jsonrpc: '2.0', id: crypto.randomUUID(), method: 'message/send',
    params: { message: { role: 'user', parts: [{ data: {
      source: sourceName, task: 'integrated-evidence', value: 42
    }}] } } };
  const started = performance.now();
  const response = await fetch(url + '/a2a', { method: 'POST',
    headers: { 'content-type': 'application/json' }, body: JSON.stringify(request) });
  assert.ok(response.ok, 'agent transport failed');
  const body = await response.json();
  assert.equal(body.id, request.id);
  const task = body.result;
  assert.equal(task.status.state, 'completed');
  const shared = task.artifacts[0];
  // Python transport hashes sorted-key compact JSON; nested input requires recursive sorting.
  const stable = value => Array.isArray(value) ? '[' + value.map(stable).join(',') + ']' :
    value && typeof value === 'object' ? '{' + Object.keys(value).sort().map(k =>
      JSON.stringify(k) + ':' + stable(value[k])).join(',') + '}' : JSON.stringify(value);
  const bytes = Buffer.from(stable(shared.parts[0].data));
  const digest = ethers.sha256(bytes);
  assert.equal(digest.slice(2), shared.sha256, 'off-chain artifact hash mismatch');
  const receipt = await mined(await registry.anchor(collaborationId, identity, digest, fee));
  const anchored = receipt.logs.map(log => {
    try { return registry.interface.parseLog(log); } catch { return null; }
  }).find(log => log?.name === 'EvidenceAnchored' && log.args.identity === identity);
  assert.ok(anchored, 'on-chain evidence event missing');
  assert.equal(anchored.args.digest, digest);
  const altered = JSON.parse(JSON.stringify(shared.parts[0].data));
  altered.accepted = false;
  assert.notEqual(ethers.sha256(Buffer.from(stable(altered))), anchored.args.digest);
  results.push({ direction: sourceName + ' -> ' + card.name, taskId: task.id,
    artifactBytes: bytes.length, digest, blockNumber: receipt.blockNumber,
    exchangeAndAnchorMs: Math.round((performance.now() - started) * 1000) / 1000,
    eventVerified: true, tamperDetected: true });
}
assert.equal((await registry.collaborations(collaborationId)).sequence, 4n);
await mined(await registry.close(collaborationId, fee));
console.log('PASS: real Docker HTTP task artifacts anchored and verified on Besu in both directions');
console.log('INTEGRATED_RESULT=' + JSON.stringify({ track: 'a2a-inspired-besu-e2e-v1',
  chainId: (await provider.getNetwork()).chainId.toString(),
  contract: await registry.getAddress(), collaborationId, results,
  caveat: 'real HTTP agent containers + Besu; A2A-inspired subset, no DPKI, single run' }));
