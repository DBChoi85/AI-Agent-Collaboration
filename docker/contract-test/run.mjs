import fs from 'node:fs';
import assert from 'node:assert/strict';
import solc from 'solc';
import { ethers } from 'ethers';

const rpc = process.env.BESU_RPC_URL || 'http://besu:8545';
const maxAttempts = 45;
const transactionTimeoutMs = 90_000;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const provider = new ethers.JsonRpcProvider(rpc, undefined, { staticNetwork: false });
let ready = false;
for (let i = 0; i < maxAttempts; i++) {
  try {
    const block = await provider.getBlockNumber();
    const network = await provider.getNetwork();
    console.log('Besu ready:', network.chainId.toString(), 'block', block);
    ready = true;
    break;
  } catch (e) {
    if (i === maxAttempts - 1) console.error(e.message);
    await delay(2000);
  }
}
if (!ready) throw new Error('Besu RPC unavailable');

const source = fs.readFileSync('contracts/CollaborationRegistry.sol', 'utf8');
const input = {
  language: 'Solidity',
  sources: { 'CollaborationRegistry.sol': { content: source } },
  settings: { optimizer: { enabled: true, runs: 200 }, evmVersion: 'cancun', outputSelection: { '*': { '*': ['abi', 'evm.bytecode.object'] } } }
};
console.log('Solidity compiler:', solc.version());
const output = JSON.parse(solc.compile(JSON.stringify(input)));
for (const issue of output.errors || []) {
  if (issue.severity === 'error') throw new Error(issue.formattedMessage);
  console.warn(issue.formattedMessage);
}
const artifact = output.contracts['CollaborationRegistry.sol'].CollaborationRegistry;
assert.ok(artifact.evm.bytecode.object.length > 0, 'compiled bytecode missing');

// Besu does not expose unlocked accounts by default. Sign locally with ephemeral
// development-only keys. The isolated dev network must permit zero-fee txs.
const latest = await provider.getBlock('latest');
assert.equal(latest.baseFeePerGas ?? 0n, 0n,
  'This zero-balance dev signer requires zero baseFeePerGas; configure an isolated zero-fee Besu chain');
const owner = new ethers.NonceManager(ethers.Wallet.createRandom().connect(provider));
const stranger = new ethers.NonceManager(ethers.Wallet.createRandom().connect(provider));
const fee = { type: 0, gasPrice: 0n };
console.log('Using ephemeral local signers (no eth_accounts or external keys)');
const factory = new ethers.ContractFactory(artifact.abi, '0x' + artifact.evm.bytecode.object, owner);
const deploymentRequest = await factory.getDeployTransaction(fee);
const estimatedGas = await provider.estimateGas({ ...deploymentRequest, from: await owner.getAddress() });
const deploymentGasLimit = estimatedGas * 120n / 100n + 100_000n;
console.log('Deployment gas estimate:', estimatedGas.toString(), 'limit:', deploymentGasLimit.toString());
const registry = await factory.deploy({ ...fee, gasLimit: deploymentGasLimit });
const deployment = registry.deploymentTransaction();
assert.ok(deployment, 'deployment transaction missing');
const deploymentReceipt = await deployment.wait(1, transactionTimeoutMs);
assert.ok(deploymentReceipt, 'deployment was not mined within 90 seconds; check Besu miner logs and transaction pool');
assert.equal(deploymentReceipt.status, 1, 'contract deployment reverted');
console.log('Deployed:', await registry.getAddress());

const id = ethers.id('collaboration-e2e-1');
const alice = ethers.id('domainA/agentA');
const bob = ethers.id('domainB/agentB');
const digest = ethers.sha256(ethers.toUtf8Bytes('off-chain-artifact'));
const zero = ethers.ZeroHash;

async function sent(tx) {
  const receipt = await tx.wait(1, transactionTimeoutMs);
  assert.ok(receipt, 'transaction was not mined within 90 seconds');
  assert.equal(receipt.status, 1);
  return receipt;
}
async function mustRevert(action, label) {
  let reverted = false;
  try {
    await action();
  } catch (error) {
    // Reject only contract execution reverts, never RPC, nonce, or balance errors.
    if (error.code !== 'CALL_EXCEPTION') throw error;
    reverted = true;
  }
  assert.ok(reverted, 'expected EVM revert: ' + label);
}
await mustRevert(() => registry.create.staticCall(zero, alice), 'zero collaboration id');
await sent(await registry.create(id, alice, fee));
assert.equal(await registry.members(id, alice), true);
await mustRevert(() => registry.create.staticCall(id, alice), 'duplicate collaboration');
await mustRevert(() => registry.connect(stranger).join.staticCall(id, bob), 'non-owner join');
await sent(await registry.join(id, bob, fee));
assert.equal(await registry.members(id, bob), true);
await mustRevert(() => registry.join.staticCall(id, bob), 'duplicate member');
await mustRevert(() => registry.anchor.staticCall(id, ethers.id('unknown'), digest), 'nonmember evidence');
await sent(await registry.anchor(id, bob, digest, fee));
await sent(await registry.leaveCollaboration(id, bob, fee));
assert.equal(await registry.members(id, bob), false);
await mustRevert(() => registry.anchor.staticCall(id, bob, digest), 'removed member evidence');
await mustRevert(() => registry.connect(stranger).close.staticCall(id), 'non-owner close');
await sent(await registry.close(id, fee));
await mustRevert(() => registry.join.staticCall(id, bob), 'closed collaboration');
const state = await registry.collaborations(id);
assert.equal(state.state, 2n);
assert.equal(state.sequence, 5n);
assert.notEqual(state.head, zero);
console.log('PASS: compiled, deployed, state transitions, membership, access rejection, evidence, close');
console.log(JSON.stringify({ contract: await registry.getAddress(), sequence: state.sequence.toString(), head: state.head }, null, 2));


// Experimental track: two independently named agent domains exchange an off-chain
// task artifact and anchor only its SHA-256 digest on the zero-fee QBFT ledger.
// This is NOT yet an A2A transport or production DPKI integration benchmark.
const experimentId = ethers.id('cross-domain-artifact-experiment');
const producer = ethers.id('domainA/producer');
const consumer = ethers.id('domainB/consumer');
const artifactPayload = Buffer.from(JSON.stringify({
  taskId: 'task-001', producer: 'domainA/producer',
  consumer: 'domainB/consumer', result: { score: 0.98, accepted: true }
}));
const artifactDigest = ethers.sha256(artifactPayload);
const timings = {};
async function measure(label, action) {
  const start = process.hrtime.bigint();
  const result = await action();
  timings[label] = Number(process.hrtime.bigint() - start) / 1e6;
  return result;
}
await measure('createMs', async () => sent(await registry.create(experimentId, producer, fee)));
await measure('joinMs', async () => sent(await registry.join(experimentId, consumer, fee)));
const anchored = await measure('anchorMs', async () =>
  sent(await registry.anchor(experimentId, producer, artifactDigest, fee)));
const event = anchored.logs.map(log => {
  try { return registry.interface.parseLog(log); } catch { return null; }
}).find(log => log?.name === 'EvidenceAnchored');
assert.ok(event, 'EvidenceAnchored event missing');
assert.equal(event.args.identity, producer);
assert.equal(event.args.digest, artifactDigest);
assert.equal(ethers.sha256(artifactPayload), event.args.digest, 'unaltered artifact must verify');
const tampered = Buffer.from(artifactPayload);
tampered[0] ^= 1;
assert.notEqual(ethers.sha256(tampered), event.args.digest, 'tampered artifact must be detected');
const experimentState = await registry.collaborations(experimentId);
assert.equal(experimentState.sequence, 3n);
await measure('closeMs', async () => sent(await registry.close(experimentId, fee)));
console.log('PASS: cross-domain artifact digest anchoring, event verification, and tamper detection');
console.log('EXPERIMENT_RESULT=' + JSON.stringify({
  track: 'qbft-cross-domain-artifact-v1',
  chainId: (await provider.getNetwork()).chainId.toString(),
  contract: await registry.getAddress(),
  collaborationId: experimentId,
  producer: 'domainA/producer', consumer: 'domainB/consumer',
  artifactBytes: artifactPayload.length, artifactDigest,
  tamperDetected: true, eventVerified: true, timingsMs: timings,
  caveat: 'single-run functional experiment; not A2A transport or DPKI validation'
}));
