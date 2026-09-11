// Run with node tests/test_audio.cjs.
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const nodes = Object.fromEntries(['audio-toggle','audio-volume','audio-volume-value','audio-message'].map(id => [id, {
 value: '70', textContent: '', addEventListener(event, fn) {this[event]=fn;}, setAttribute() {}
}]));
const contexts=[];const timers=new Map();let timer=0;let requests=0;let pending=null;
class AudioContext {
 constructor(){this.state='running';this.currentTime=0;this.destination={};this.started=[];contexts.push(this);}
 createGain(){this.gain={gain:{value:1},connect(){}};return this.gain;}
 resume(){return Promise.resolve();}
 close(){this.closed=true;return Promise.resolve();}
 createBuffer(ch,n,rate){assert.equal(ch,1);assert.equal(rate,16000);this.samples=new Float32Array(n);return {getChannelData:()=>this.samples,duration:n/rate};}
 createBufferSource(){const context=this;return {connect(){},start(time){context.started.push(time);}};}
}
const pcm=new ArrayBuffer(4);const view=new DataView(pcm);view.setInt16(0,8192,true);view.setInt16(2,-8192,true);
const sandbox={window:{AudioContext,addEventListener(){}},document:{getElementById:id=>nodes[id]},
 AbortController,DataView,Number,setTimeout(fn){timers.set(++timer,fn);return timer;},clearTimeout(id){timers.delete(id);},
 fetch:async(url,options)=>{requests++; if(pending)return pending;
  return {ok:true,headers:{get:key=>({'X-Audio-Sequence':'1','X-Audio-Rate':'16000','X-Receiver-Running':'1'})[key]},arrayBuffer:async()=>pcm};}
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../ais_atis_bridge/static/audio.js'),'utf8'),sandbox);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 assert.equal(contexts.length,0); // explicit click required
 await nodes['audio-toggle'].click();await flush();
 assert.equal(requests,1);assert.equal(nodes['audio-toggle'].textContent,'Audio: on');
 assert.equal(contexts[0].gain.gain.value,.7);assert.deepEqual(Array.from(contexts[0].samples),[.25,-.25]);
 assert.equal(contexts[0].started.length,1);
 nodes['audio-volume'].value='0';nodes['audio-volume'].input();assert.equal(contexts[0].gain.gain.value,0);
 await nodes['audio-toggle'].click();assert(contexts[0].closed);assert.equal(timers.size,0);
 assert.equal(nodes['audio-toggle'].textContent,'Audio: off');
 let resolve;pending=new Promise(r=>resolve=r);
 await nodes['audio-toggle'].click();await flush();await nodes['audio-toggle'].click();
 resolve({ok:true,headers:{get:key=>({'X-Audio-Sequence':'2','X-Audio-Rate':'16000'})[key]},arrayBuffer:async()=>pcm});
 await flush();assert.equal(contexts[1].started.length,0);assert.equal(timers.size,0);
 console.log('PASS audio controls: explicit start, PCM playback scheduling, volume/mute, stop, cancelled late response');
})().catch(e=>{console.error(e);process.exitCode=1;});
