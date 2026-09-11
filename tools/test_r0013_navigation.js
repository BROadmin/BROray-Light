'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const source = fs.readFileSync(path.join(__dirname,'../packaging/r0013-overlay/app/web-new/assets/js/app-shell.js'));
const records = [];
let failed = false;
for (const [pathname,suffix,expected] of [
  ['/home.html','?v=2.0.0','home.html'], ['/servers.html','?v=2.0.0','servers.html'],
  ['/subscriptions.html','?v=2.0.0','subscriptions.html'], ['/home.html','#section','home.html'],
  ['/servers.html','','servers.html'], ['/','?v=2.0.0','home.html'], ['/missing.html','?v=2.0.0',null]
]) {
  const name = pathname + ' href-suffix=' + suffix;
  try {
    const links = ['home.html','servers.html','subscriptions.html'].map(p=>({
      path:p, attributes:{href:p+suffix,'aria-current':'page'}, active:true,
      getAttribute(k) {return this.attributes[k] || null;},
      setAttribute(k,v) {this.attributes[k]=v;}, removeAttribute(k) {delete this.attributes[k];}
    }));
    for (const link of links) link.classList={toggle(k,v){assert.equal(k,'active');link.active=v;}};
    const context=vm.createContext({location:{pathname},document:{
      addEventListener(event,handler){assert.equal(event,'DOMContentLoaded');handler();},
      querySelectorAll(selector){assert.equal(selector,'nav a');return links;}
    }});
    vm.runInContext(source.toString('utf8'),context);
    assert.deepEqual(links.filter(l=>l.active).map(l=>l.path), expected?[expected]:[]);
    for(const link of links) assert.equal(link.attributes['aria-current'],link.active?'page':undefined);
    records.push({name,status:'PASS'});
  } catch(error) {failed=true;records.push({name,status:'FAIL',error:error.message});break;}
}
const report={stage:'R0013',revision:'p59-query-safe-current-navigation',candidateReady:false,
  status:failed?'FAIL_FIRST_ERROR':'PASS_BOUNDED_NAVIGATION',sourceSha256:crypto.createHash('sha256').update(source).digest('hex'),tests:records};
const payload=JSON.stringify(report,null,2)+'\n';
if(process.argv[2])fs.writeFileSync(process.argv[2],payload);
console.log(payload);process.exitCode=failed?1:0;
