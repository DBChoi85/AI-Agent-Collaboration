import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import solc from 'solc';
import { ethers } from 'ethers';

const action = process.argv[2] || 'deploy';
const root = '/identities';
const output = '/chain/status.json';
const provider = new ethers.JsonRpcProvider(process.env.BESU_RPC_URL || 'http://besu:8545');
for (let i = 0; i < 60; i++) {
  try { await provider.getBlockNumber(); break; }
  catch (e) { if (i === 59) throw e; await new Promise(r => setTimeout(r, 1000)); }
}
const fee = { type: 0, gasPrice: 0n };
async function mined(tx) {
  const receipt = await tx.wait(1, 90000);
  assert.ok(receipt && receipt.status === 1);
  return receipt;
}
const sources = { 'AgentCertificateStatus.sol': {
  content: fs.readFileSync('contracts/AgentCertificateStatus.sol', 'utf8') } };
const compiled = JSON.parse(solc.compile(JSON.stringify({language:'Solidity', sources,
  settings:{optimizer:{enabled:true,runs:200},evmVersion:'cancun',
    outputSelection:{'*':{'*':['abi','evm.bytecode.object']}}}})));
assert.equal((compiled.errors || []).filter(e => e.severity === 'error').length, 0);
const contract = compiled.contracts['AgentCertificateStatus.sol'].AgentCertificateStatus;
const walletPath = '/chain/admin-key.json';
let wallet;
if (action === 'deploy') {
  wallet = ethers.Wallet.createRandom();
  fs.writeFileSync(walletPath, JSON.stringify({privateKey:wallet.privateKey}), {mode:0o600});
} else {
  wallet = new ethers.Wallet(JSON.parse(fs.readFileSync(walletPath,'utf8')).privateKey);
}
const signer = new ethers.NonceManager(wallet.connect(provider));
const digests = [['domainA','producer'],['domainB','consumer']].map(([domain,agent]) => {
  const pem = fs.readFileSync(root + '/' + domain + '-' + agent + '.pem');
  const der = new crypto.X509Certificate(pem).raw;
  return {source:domain+'/'+agent, digest:'0x'+crypto.createHash('sha256').update(der).digest('hex')};
});
let registry;
if (action === 'deploy') {
  const factory = new ethers.ContractFactory(contract.abi,'0x'+contract.evm.bytecode.object,signer);
  const estimate = await provider.estimateGas({...(await factory.getDeployTransaction(fee)),from:await signer.getAddress()});
  registry = await factory.deploy({...fee,gasLimit:estimate*120n/100n+100000n});
  await mined(registry.deploymentTransaction());
  for (const item of digests) await mined(await registry.setStatus(item.digest,true,fee));
  const address = await registry.getAddress();
  fs.writeFileSync(output,JSON.stringify({address,rpcUrl:'http://besu:8545',
    isActiveSelector:registry.interface.getFunction('isActive').selector,digests}));
  for (const item of digests) assert.equal(await registry.isActive(item.digest),true);
  console.log('PASS: both domain certificates registered as active on Besu');
} else if (action === 'revoke') {
  const cfg = JSON.parse(fs.readFileSync(output,'utf8'));
  registry = new ethers.Contract(cfg.address,contract.abi,signer);
  await mined(await registry.setStatus(digests[0].digest,false,fee));
  assert.equal(await registry.isActive(digests[0].digest),false);
  assert.equal(await registry.isActive(digests[1].digest),true);
  console.log('PASS: domainA certificate revoked on Besu; domainB remains active');
} else throw new Error('unknown action '+action);
