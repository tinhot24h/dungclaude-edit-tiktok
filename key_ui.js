'use strict';
// "Lưu key trên máy này" next to every API key field. Saving is opt-in; the key goes to .local/secrets.json on this
// computer (never into the ZIP or updates) and the page only gets a masked hint back. Empty field = use the saved key.
(()=>{
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const json=(url,body)=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const NAMES={openai:'OpenAI',gemini:'Gemini',ai33:'ai33.pro'};
const FIELDS=[['ai-key',()=>['openai','gemini'].includes($('ai-provider')?.value)?$('ai-provider').value:''],['tts-key',()=>'ai33'],['dub-openai',()=>'openai'],['dub-ai33',()=>'ai33']];
let state={},rows=[];
for(const[id,provider]of FIELDS){const input=$(id);if(!input)continue;const placeholder=input.placeholder;
 const save=el('button',{type:'button',className:'outline-action small-action',textContent:'💾 Lưu key trên máy này'}),drop=el('button',{type:'button',className:'outline-action small-action danger-action',textContent:'Xóa key đã lưu'}),note=el('small',{className:'key-note'});
 const row=el('div',{className:'key-save'},save,drop,note);(input.closest('.folder-row,.key-row')||input).after(row);
 const draw=()=>{const p=provider(),s=state[p];row.hidden=!p;if(!p)return;drop.hidden=!s?.saved;save.textContent=s?.saved?'💾 Lưu key mới':'💾 Lưu key trên máy này';
  note.textContent=s?.saved?`Đã lưu ${NAMES[p]} key ${s.hint} · để trống ô để dùng key này`:'Chưa lưu · key chỉ dùng trong phiên này';input.placeholder=s?.saved?`Đã lưu ${s.hint} — để trống để dùng key đã lưu`:placeholder};
 save.onclick=async()=>{const p=provider(),key=input.value.trim();if(!key){note.textContent='Dán key vào ô trước rồi bấm lưu.';input.focus();return}
  if(!confirm(`Lưu ${NAMES[p]} key trên máy này?\n\nKey nằm trong thư mục .local của ứng dụng (không đưa vào ZIP hay bản cập nhật). Người khác dùng chung máy/tài khoản Windows cũng có thể dùng key này.`))return;
  try{state=await json('/secrets/save',{provider:p,key});input.value='';input.dispatchEvent(new Event('input',{bubbles:true}));changed();note.textContent=`Đã lưu ${NAMES[p]} key ${state[p].hint}.`}catch(e){note.textContent=e.message}};
 drop.onclick=async()=>{const p=provider();if(!confirm(`Xóa ${NAMES[p]} key đã lưu trên máy này?`))return;try{state=await json('/secrets/delete',{provider:p});changed()}catch(e){note.textContent=e.message}};
 rows.push(draw)}
function changed(){for(const d of rows)d();document.dispatchEvent(new Event('keys-changed'))}
$('ai-provider')?.addEventListener('change',()=>{for(const d of rows)d()});for(const b of $('ai-provider-tabs')?.children||[])b.addEventListener('click',()=>setTimeout(()=>{for(const d of rows)d()}));
request('/secrets').then(d=>{state=d;for(const r of rows)r()}).catch(()=>{});
})();
