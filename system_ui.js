'use strict';
// 🩺 Kiểm tra hệ thống in the header (next to API key): a quick check at start colors the dot; the dialog runs the
// full check (also tests the keys with one free request each) and lists what is wrong with how to fix it.
(()=>{
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const RANK={bad:0,warn:1,ok:2,info:2},ICON={ok:'✓',warn:'!',bad:'✕',info:'i'},TITLE={ok:'Hệ thống ổn',warn:'Có mục cần chú ý',bad:'Có lỗi cần sửa'};
const open=el('button',{type:'button',id:'system-open',className:'header-key',title:'Kiểm tra hệ thống: FFmpeg, key, ổ đĩa, phông chữ…'},el('span',{className:'dot'}),document.createTextNode(' 🩺 Kiểm tra'));
const keys=$('keys-open');keys?keys.after(open):(document.querySelector('.header-tools')||document.querySelector('.app-header')).prepend(open);
const dialog=el('dialog',{id:'system-dialog',className:'dub-dialog system-dialog'});document.body.append(dialog);
let last=null,busy=false;
function badge(d){open.classList.remove('ok','warn','bad');if(!d)return;open.classList.add(d.state);
 const n=d.rows.filter(r=>r.state==='bad'||r.state==='warn').length;open.title=TITLE[d.state]+(n?` (${n} mục) · bấm để xem cách sửa`:' · bấm để kiểm tra lại')}
function report(d){return[`Review Studio ${d.version} · ${d.platform} · ${new Date().toLocaleString('vi-VN')}`,...d.rows.map(r=>`[${ICON[r.state]}] ${r.label}: ${r.detail}${r.fix?' → '+r.fix:''}`)].join('\n')}
function keyButton(){const b=el('button',{type:'button',className:'outline-action small-action',textContent:'🔑 Mở API key'});b.onclick=()=>{dialog.close();window.openKeys()};return b}
function draw(d,note=''){const again=el('button',{type:'button',className:'primary-action small-action',textContent:'↻ Kiểm tra lại',disabled:busy});again.onclick=()=>check();
 const copy=el('button',{type:'button',className:'outline-action small-action',textContent:'📋 Copy báo cáo',disabled:!d});
 copy.onclick=async()=>{try{await navigator.clipboard.writeText(report(d));copy.textContent='✓ Đã copy'}catch{copy.textContent='Không copy được'}};
 const close=el('button',{type:'button',className:'outline-action small-action',textContent:'Đóng'});close.onclick=()=>dialog.close();
 const head=d?el('p',{className:'system-summary '+d.state,textContent:TITLE[d.state]+(d.version?` · Review Studio ${d.version}`:'')}):el('p',{className:'helper',textContent:note||'Đang kiểm tra…'});
 const list=d?el('div',{className:'system-list'},...[...d.rows].sort((a,b)=>RANK[a.state]-RANK[b.state]).map(r=>el('div',{className:'system-row '+r.state},el('span',{className:'system-icon',textContent:ICON[r.state]}),
  el('div',{},el('strong',{textContent:r.label}),el('small',{textContent:r.detail}),...(r.fix?[el('em',{textContent:'Cách sửa: '+r.fix})]:[]),...(r.state!=='ok'&&(r.key==='openai'||r.key==='ai33')&&window.openKeys?[keyButton()]:[]))))):'';
 dialog.replaceChildren(el('h2',{textContent:'🩺 Kiểm tra hệ thống'}),head,list,...(d&&note?[el('p',{className:'helper',textContent:note})]:[]),el('div',{className:'dub-actions'},copy,again,close))}
// the quick check (start, key changes) only colors the dot; the full one (dialog) never waits behind it
let quickBusy=false,timer=0;
async function quickCheck(){if(quickBusy)return;quickBusy=true;try{const d=await request('/system/check?quick=1');if(!busy){last=d;badge(d)}}catch{}quickBusy=false}
async function check(){if(busy)return;busy=true;const t0=Date.now(),stop=new AbortController(),limit=setTimeout(()=>stop.abort(),90000);let note='';
 const wait=()=>{if(dialog.open&&busy)draw(null,`Đang kiểm tra (FFmpeg, card đồ họa, thử key qua mạng)… ${Math.round((Date.now()-t0)/1000)} giây`)};wait();clearInterval(timer);timer=setInterval(wait,1000);
 try{last=await request('/system/check',{signal:stop.signal});badge(last)}
 catch(e){note=stop.signal.aborted?'Kiểm tra quá 90 giây chưa xong: bấm ↻ Kiểm tra lại, hoặc khởi động lại app.':'Không kiểm tra được: '+e.message+' (nếu vừa cập nhật, hãy tắt app rồi mở lại).'}
 clearTimeout(limit);clearInterval(timer);busy=false;if(dialog.open)draw(last,note)}
window.openSystemCheck=()=>{dialog.showModal();check()};open.onclick=()=>window.openSystemCheck();
document.addEventListener('keys-changed',quickCheck);
quickCheck();
})();
