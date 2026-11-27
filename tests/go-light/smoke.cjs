const {spawn, execFileSync} = require("node:child_process");
const {mkdtemp, mkdir, rm, stat} = require("node:fs/promises");
const {tmpdir} = require("node:os");
const path = require("node:path");
const net = require("node:net");
const assert = require("node:assert/strict");
const {setTimeout: delay} = require("node:timers/promises");

async function loopbackPort() {
  const listener = net.createServer();
  await new Promise((resolve, reject) => {
    listener.once("error", reject);
    listener.listen(0, "127.0.0.1", resolve);
  });
  const port = listener.address().port;
  await new Promise((resolve) => listener.close(resolve));
  return port;
}

async function run() {
  const binary = path.resolve(process.argv[2]);
  const dir = await mkdtemp(path.join(tmpdir(), "light-smoke-"));
  const root = path.join(dir, "broray-light");
  const runtime = path.join(dir, "run");
  const flags = ["--root", root, "--run", runtime];
  const port = await loopbackPort();
  const address = "127.0.0.1:" + port;
  const base = "http://" + address;
  assert.match(execFileSync(binary, ["version"], {encoding:"utf8"}), /^BROray-Light 3\.5\.10\s*$/);
  const daemon = spawn(binary, ["serve", ...flags, "--listen", address], {stdio:["ignore","ignore","pipe"]});
  const exit = new Promise((resolve, reject) => { daemon.once("exit", resolve); daemon.once("error", reject); });
  let logs = "";
  daemon.stderr.on("data", (chunk) => { logs += String(chunk); });
  try {
    let status;
    for (let i=0; i<100 && !status && daemon.exitCode===null; i++) {
      status = await fetch(base).catch(() => undefined);
      if (!status) await delay(50);
    }
    assert.equal(status?.status, 200, logs);
    execFileSync(binary, ["ready", ...flags, "--version", "3.5.10"]);
    assert.throws(() => execFileSync(binary, ["ready", ...flags, "--version", "3.5.9"], {stdio:"pipe"}));
    const sock = await stat(path.join(runtime, "control.sock"));
    assert.equal(sock.mode & 0o777, 0o600);
    for (const route of ["/", "/servers", "/subscriptions"]) {
      const response = await fetch(base + route);
      assert.equal(response.status, 200);
      const html = await response.text();
      assert.match(html, /BROray.Light/);
      assert.match(html, /\/assets\/light\.js/);
      assert.match(response.headers.get("content-security-policy"), /frame-ancestors 'none'/);
    }
    for (const asset of ["light.js", "light.css"]) {
      const response = await fetch(base + "/assets/" + asset);
      assert.equal(response.status, 200);
      assert.ok((await response.text()).length > 300);
    }
    for (const route of ["/routes","/dot","/api/ready"]) assert.equal((await fetch(base+route)).status,404);
    for (const route of ["/api/state", "/api/web-access"]) {
      assert.equal((await fetch(base+route)).status,401);
    }
    const creds = await fetch(base+"/api/login", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({user:"fixture",password:"fixture"})
    });
    assert.equal(creds.status,401);
    assert.equal(creds.headers.get("set-cookie"),null);
    await mkdir(path.join(dir,"broray"));
    assert.throws(() => execFileSync(binary, ["ready", ...flags, "--version", "3.5.10"], {stdio:"pipe"}));
    assert.throws(() => execFileSync(binary, ["serve", ...flags, "--listen", address], {stdio:"pipe"}));
  } finally {
    daemon.kill("SIGTERM");
    await exit;
    await rm(dir,{recursive:true,force:true});
  }
  console.log("host smoke: version, daemon, private readiness, WebUI, auth isolation and full-product conflict passed");
}

run().catch((error) => { console.error(error); process.exitCode=1; });
