'use strict';
// Every "add file" button opens the Windows file dialog through the local server instead of the browser one, so the
// app gets the real path: files are read where they are on this computer (hard link or disk copy), never uploaded.
// The picked files are empty File objects tagged with their path; fetch/XHR send the path (X-Local-Path) instead of
// the bytes, previews stream from /local/file and .text() reads from disk. Drag & drop still uploads (the browser
// does not reveal dropped paths); folder upload inputs (webkitdirectory) keep the browser dialog on purpose.
(()=>{
const LOCAL=new WeakMap();
const KIND=[['video',/video\/|\.(mp4|mov|m4v|mkv|webm|avi)\b/],['audio',/audio\/|\.(mp3|wav|m4a|aac|flac|ogg)\b/],['image',/image\/|\.(png|jpe?g|webp|gif)\b/],['srt',/\.srt\b/],['json',/json/]];
const kinds=accept=>{const a=(accept||'').toLowerCase();const out=KIND.filter(([,re])=>re.test(a)).map(([k])=>k);return out.length?out:['video','audio','image']};
const TITLE={video:'Chọn video',audio:'Chọn file âm thanh',image:'Chọn ảnh',srt:'Chọn file SRT',json:'Chọn file dự án'};
window.isLocalFile=f=>LOCAL.has(f);window.localPath=f=>LOCAL.get(f);
function wrap(item){const f=new File([],item.name,{type:item.type,lastModified:Date.now()});Object.defineProperty(f,'size',{value:item.size});
 f.text=async()=>(await request('/local/read-text',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:item.path})})).text;LOCAL.set(f,item.path);return f}
let native=null;
document.addEventListener('click',async e=>{const input=e.target;
 if(!(input instanceof HTMLInputElement)||input.type!=='file'||input.webkitdirectory||input===native||input.dataset.upload==='browser')return;
 e.preventDefault();e.stopPropagation();
 const k=kinds(input.accept);let picked;
 try{picked=(await request('/local/pick-files',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kinds:k,multiple:input.multiple,title:TITLE[k[0]]+(input.multiple?' (chọn được nhiều file)':'')})})).files}
 catch{native=input;input.click();native=null;return}  // no native dialog on this machine: the browser one still works
 if(!picked.length)return;
 const dt=new DataTransfer();for(const item of picked)dt.items.add(wrap(item));
 // the input must hand back the same File objects (they carry the path)
 const files=[...dt.files];for(let i=0;i<files.length;i++)if(!LOCAL.has(files[i]))LOCAL.set(files[i],picked[i].path);
 input.files=dt.files;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}))},true);
const fetch0=window.fetch.bind(window);
window.fetch=(url,opts)=>{const body=opts?.body;if(body instanceof File&&LOCAL.has(body)){const h=new Headers(opts.headers||{});h.set('X-Local-Path',encodeURIComponent(LOCAL.get(body)));opts={...opts,body:null,headers:h}}return fetch0(url,opts)};
const send0=XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.send=function(body){if(body instanceof File&&LOCAL.has(body)){this.setRequestHeader('X-Local-Path',encodeURIComponent(LOCAL.get(body)));return send0.call(this,null)}return send0.call(this,body)};
const url0=URL.createObjectURL.bind(URL),revoke0=URL.revokeObjectURL.bind(URL);
URL.createObjectURL=o=>o instanceof File&&LOCAL.has(o)?'/local/file?path='+encodeURIComponent(LOCAL.get(o)):url0(o);
URL.revokeObjectURL=u=>{if(String(u).startsWith('blob:'))revoke0(u)};
})();
