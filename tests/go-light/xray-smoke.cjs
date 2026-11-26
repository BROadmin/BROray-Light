const {spawn, execFile} = require("node:child_process");
const {chmod, copyFile, mkdir, mkdtemp, readFile, readdir, rm, writeFile} = require("node:fs/promises");
const {tmpdir} = require("node:os");
const path = require("node:path");
const net = require("node:net");
const http = require("node:http");
const assert = require("node:assert/strict");
const {setTimeout: delay} = require("node:timers/promises");

async function freePort() {
  const listener = net.createServer();
  await new Promise((resolve, reject) => { listener.once("error",reject); listener.listen(0,"127.0.0.1",resolve); });
  const port = listener.address().port;
  await new Promise((resolve) => listener.close(resolve));
  return port;
}

async function canConnect(port) {
  return new Promise((resolve) => {
    const connection = net.createConnection({host:"127.0.0.1",port});
    connection.setTimeout(500);
    connection.once("connect",() => { connection.destroy(); resolve(true); });
    connection.once("error",() => resolve(false));
    connection.once("timeout",() => { connection.destroy(); resolve(false); });
  });
}

async function eventually(condition, message, limit=25000) {
  const deadline = Date.now()+limit;
  while (Date.now()<deadline) {
    if (await condition()) return;
    await delay(150);
  }
  throw new Error(message);
}

async function main() {
  const [light, officialCore] = process.argv.slice(2).map((entry) => path.resolve(entry));
  const folder = await mkdtemp(path.join(tmpdir(),"light-xray-smoke-"));
  const root = path.join(folder,"broray-light");
  const run = path.join(folder,"run");
  const core = path.join(root,"runtime","xray","xray");
  const state = path.join(root,"state","light.json");
  const config = path.join(folder,"upstream.json");
  const [webPort, socksPort, vlessPort] = await Promise.all([freePort(),freePort(),freePort()]);
  const id = "srv-immutable";
  const uuid = "11111111-1111-4111-8111-111111111111";
  await mkdir(path.dirname(core),{recursive:true,mode:0o700});
  await mkdir(path.dirname(state),{mode:0o700});
  await copyFile(officialCore,core);
  await chmod(core,0o700);
  await writeFile(state,JSON.stringify({
    schema:1, active:id, manageInterface:false, failover:{enabled:true,threshold:3,cooldownSeconds:15},
    servers:[{manual:true,profile:{id,uuid,name:"Controlled VLESS",protocol:"vless",network:"raw",security:"none",address:"127.0.0.1",port:vlessPort}}]
  }),{mode:0o600});
  await writeFile(config,JSON.stringify({
    log:{loglevel:"warning"},
    inbounds:[{listen:"127.0.0.1",port:vlessPort,protocol:"vless",settings:{decryption:"none",clients:[{id:uuid}]}}],
    outbounds:[{protocol:"freedom"}]
  }),{mode:0o600});
  let requests=0;
  const endpoint = http.createServer((req,res) => { requests++; res.writeHead(204); res.end(); });
  await new Promise((resolve) => endpoint.listen(0,"127.0.0.1",resolve));
  const probe = "http://127.0.0.1:"+endpoint.address().port+"/ready";
  const children=[];
  let out="";
  function child(file,args) {
    const process=spawn(file,args,{stdio:["ignore","pipe","pipe"]});
    const done=new Promise((resolve,reject) => {process.once("exit",resolve);process.once("error",reject);});
    process.stdout.on("data", (data) => {out+=data;});
    process.stderr.on("data", (data) => {out+=data;});
    children.push({process,done});
    return {process,done};
  }
  const flags=["--root",root,"--run",run];
  const daemon=child(light,["serve",...flags,"--listen","127.0.0.1:"+webPort,"--socks","127.0.0.1:"+socksPort,"--probe-url",probe]);
  const ready=()=>new Promise((resolve) => execFile(light,["ready",...flags,"--version","3.5.10"],{timeout:18000}, (err) => resolve(!err)));
  try {
    await eventually(async () => (await fetch("http://127.0.0.1:"+webPort).catch(() => null))?.status===200,"WebUI startup");
    await eventually(async () => {
      const files=await readdir(run);
      return !files.some((file) => /^xray-.*\.json$/.test(file)) && !(await canConnect(socksPort));
    },"initial failed Xray attempt must stop");
    assert.equal(await ready(),false,"update became ready before selected VLESS upstream");
    assert.equal(JSON.parse(await readFile(state,"utf8")).active,id);
    child(core,["run","-config",config]);
    await eventually(() => canConnect(vlessPort),"official upstream Xray startup");
    await eventually(ready,"active state was not restored after the VLESS upstream recovered",40000);
    assert.ok(requests>=2,"no real HTTP through Xray during boot and readiness");
    daemon.process.kill("SIGKILL");
    await daemon.done;
    await eventually(async () => !(await canConnect(socksPort)),"active Xray survived forced daemon death",8000);
    assert.ok(await canConnect(vlessPort),"unrelated Xray listener was stopped");
    console.log("real Xray smoke: failed boot, durable selection, VLESS recovery, update readiness and SIGKILL ownership passed");
  } catch (error) {
    console.error(out);
    throw error;
  } finally {
    for (const {process} of children) process.kill("SIGTERM");
    await Promise.allSettled(children.map(({done})=>done));
    await new Promise((resolve) => endpoint.close(resolve));
    await rm(folder,{recursive:true,force:true});
  }
}

main().catch((error) => { console.error(error); process.exitCode=1; });
