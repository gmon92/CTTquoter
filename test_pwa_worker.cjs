const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function worker(offline=false){
  const listeners={},cached=[],deleted=[];
  const context=vm.createContext({URL,Response,Promise,
    self:{location:{origin:'https://quotes.example.com'},clients:{claim:async()=>{}},
      addEventListener:(name,callback)=>listeners[name]=callback},
    fetch:async()=>{if(offline) throw new Error('offline');return new Response('online');},
    caches:{open:async()=>({addAll:async paths=>cached.push(...paths)}),
      match:async path=>new Response(`cached ${path}`),keys:async()=>['ctt-public-v0','ctt-public-v1','another-app'],
      delete:async key=>deleted.push(key)}});
  vm.runInContext(fs.readFileSync(`${__dirname}/static/sw.js`,'utf8'),context);
  return {listeners,cached,deleted,request(path,method='GET',mode='cors'){
    let result;
    listeners.fetch({request:{url:new URL(path,'https://quotes.example.com').href,method,mode},respondWith:value=>result=value});
    return result;
  }};
}

test('installation caches only public assets and never app or login pages',async()=>{
  const w=worker();let done;w.listeners.install({waitUntil:value=>done=value});await done;
  assert.ok(w.cached.includes('/offline.html'));
  assert.ok(w.cached.includes('/icons/apple-touch-icon.png'));
  for(const path of w.cached) assert.ok(!path.startsWith('/api/') && !['/','/index.html','/login'].includes(path));
});
test('activation removes only old caches owned by CTT',async()=>{
  const w=worker();let done;w.listeners.activate({waitUntil:value=>done=value});await done;
  assert.deepEqual(w.deleted,['ctt-public-v0']);
});
test('offline navigation receives a generic notice without a saved quote',async()=>{
  const response=await worker(true).request('/','GET','navigate');
  assert.equal(await response.text(),'cached /offline.html');
});
test('offline quote and reprice POSTs fail clearly without cached fare responses',async()=>{
  for(const path of ['/api/quote','/api/reprice']){
    const response=await worker(true).request(path,'POST');
    assert.equal(response.status,503);
    assert.equal(response.headers.get('Cache-Control'),'no-store');
    assert.match((await response.json()).error,/offline/);
  }
});
test('online APIs and navigations go to the server',async()=>{
  for(const [path,method,mode] of [['/api/quote','POST','cors'],['/login','GET','navigate'],['/','GET','navigate']]){
    assert.equal(await (await worker().request(path,method,mode)).text(),'online');
  }
});
test('worker does not intercept third party assets, login POSTs or unknown files',()=>{
  const w=worker(true);
  assert.equal(w.request('https://other.example.com/api/quote','POST'),undefined);
  assert.equal(w.request('/login','POST'),undefined);
  assert.equal(w.request('/app.py'),undefined);
});
