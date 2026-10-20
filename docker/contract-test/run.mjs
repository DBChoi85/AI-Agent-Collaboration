import fs from 'node:fs';
import assert from 'node:assert/strict';
import solc from 'solc';
import { ethers } from 'ethers';

const rpc = process.env.BESU_RPC_URL || 'http://besu:8545';
const maxAttempts = 45;
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
  settings: { optimizer: { enabled: true, runs: 200 }, outputSelection: { '*': { '*': ['abi', 'evm.bytecode.object'] } } }
};
const output = JSON.parse(solc.compile(JSON.stringify(input)));
for (const issue of output.errors || []) {
  if (issue.severity === 'error') throw new Error(issue.formattedMessage);
  console.warn(issue.formattedMessage);
}
const artifact = output.contracts['CollaborationRegistry.sol'].CollaborationRegistry;
assert.ok(artifact.evm.bytecode.object.length > 0, 'compiled bytecode missing');

// Besu --network=dev includes prefunded development accounts. No real keys are committed.
const accounts = await provider.send('eth_accounts', []);
assert.ok(accounts.length >= 1, 'Besu dev node must expose an unlocked account');
const owner = await provider.getSigner(accounts[0]);
const stranger = ethers.Wallet.createRandom().connect(provider);
await (await owner.sendTransaction({ to: stranger.address, value: ethers.parseEther('1') })).wait();
const factory = new ethers.ContractFactory(artifact.abi, '0x' + artifact.evm.bytecode.object, owner);
const registry = await factory.deploy();
await registry.waitForDeployment();
console.log('Deployed:', await registry.getAddress());

const id = ethers.id('collaboration-e2e-1');
const alice = ethers.id('domainA/agentA');
const bob = ethers.id('domainB/agentB');
const digest = ethers.sha256(ethers.toUtf8Bytes('off-chain-artifact'));
const zero = ethers.ZeroHash;

async function sent(tx) {
  const receipt = await tx.wait();
  assert.equal(receipt.status, 1);
  return receipt;
}
async function mustRevert(action, label) {
  let rejected = false;
  try {
    const tx = await action();
    await tx.wait();
  } catch (error) {
    rejected = true;
  }
  assert.ok(rejected, 'expected revert: ' + label);
}
await mustRevert(() => registry.create(zero, alice), 'zero collaboration id');
await sent(await registry.create(id, alice));
assert.equal(await registry.members(id, alice), true);
await mustRevert(() => registry.create(id, alice), 'duplicate collaboration');
await mustRevert(() => registry.connect(stranger).join(id, bob), 'non-owner join');
await sent(await registry.join(id, bob));
assert.equal(await registry.members(id, bob), true);
await mustRevert(() => registry.join(id, bob), 'duplicate member');
await mustRevert(() => registry.anchor(id, ethers.id('unknown'), digest), 'nonmember evidence');
await sent(await registry.anchor(id, bob, digest));
await sent(await registry.leave(id, bob));
assert.equal(await registry.members(id, bob), false);
await mustRevert(() => registry.anchor(id, bob, digest), 'removed member evidence');
await mustRevert(() => registry.connect(stranger).close(id), 'non-owner close');
await sent(await registry.close(id));
await mustRevert(() => registry.join(id, bob), 'closed collaboration');
const state = await registry.collaborations(id);
assert.equal(state.state, 2n);
assert.equal(state.sequence, 5n);
assert.notEqual(state.head, zero);
console.log('PASS: compiled, deployed, state transitions, membership, access rejection, evidence, close');
console.log(JSON.stringify({ contract: await registry.getAddress(), sequence: state.sequence.toString(), head: state.head }, null, 2));
