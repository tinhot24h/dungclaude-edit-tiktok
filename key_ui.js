'use strict';
// "Lưu key trên máy này" next to every API key field. Saving is opt-in; the key goes to .local/secrets.json on this
// computer (never into the ZIP or updates) and the page only gets a masked hint back. Empty field = use the saved key.
(()=>{
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const json=(url,body)=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const NAMES={gemini:'Gemini',openai:'OpenAI',ai33:'ai33.pro'};
const FIELDS=[['tts-key',()=>'ai33'],['dub-openai',()=>'openai'],['dub-ai33',()=>'ai33']];
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
// ---- one place for every key since 0.22: 🔑 API in the header. The key fields of the pages are no longer shown;
// every feature (translation, voices, dubbing) uses the keys saved here.
const USES=[['gemini','Gemini','Dịch và biên tập; nhận diện lời vẫn dùng OpenAI Whisper'],['openai','OpenAI','Nhận diện lời (Whisper), dịch, viết tiêu đề và nội dung'],['ai33','ai33.pro','Giọng đọc tiếng Việt và lồng tiếng']];
for(const id of ['tts-connection','sec-keys'])$(id)?.classList.add('keys-elsewhere');
const open=el('button',{type:'button',id:'keys-open',className:'header-key',title:'Quản lý API key (OpenAI, ai33) cho mọi chức năng'},el('span',{className:'dot'}),document.createTextNode(' API key'));
(document.querySelector('.header-tools')||document.querySelector('.app-header')).prepend(open);
const dialog=el('dialog',{id:'keys-dialog',className:'dub-dialog'});document.body.append(dialog);
function drawKeys(){const list=USES.map(([p,name,use])=>{const s=state[p]||{},input=el('input',{type:'password',autocomplete:'off',spellcheck:false,placeholder:s.saved?`Đã lưu ${s.hint} · dán key mới để thay`:'Dán API key'});
  const save=el('button',{type:'button',className:'primary-action small-action',textContent:s.saved?'Lưu key mới':'Lưu'}),drop=el('button',{type:'button',className:'outline-action small-action danger-action',textContent:'Xóa',hidden:!s.saved}),note=el('small',{className:'key-note',textContent:s.saved?`✓ Đã lưu ${s.hint}`:'Chưa có key'});
  save.onclick=async()=>{const key=input.value.trim();if(!key){note.textContent='Dán key vào ô trước rồi bấm Lưu.';input.focus();return}
   try{state=await json('/secrets/save',{provider:p,key});changed();drawKeys()}catch(e){note.textContent=e.message}};
  drop.onclick=async()=>{if(!confirm(`Xóa ${name} key đã lưu trên máy này?`))return;try{state=await json('/secrets/delete',{provider:p});changed();drawKeys()}catch(e){note.textContent=e.message}};
  const check=el('button',{type:'button',className:'outline-action small-action',textContent:'Kiểm tra Gemini',hidden:p!=='gemini'});check.onclick=async()=>{check.disabled=true;try{const d=await json('/ai/models/refresh',{});note.textContent=`Đã xác minh ${d.models.length} model generateContent; không gọi tạo nội dung.`}catch(e){note.textContent=e.message}finally{check.disabled=false}};
  return el('div',{className:'keys-row'+(s.saved?' ok':'')},el('div',{className:'keys-name'},el('strong',{textContent:name}),el('small',{textContent:use})),el('div',{className:'keys-edit'},input,save,drop,check),note)});
 const close=el('button',{type:'button',className:'outline-action small-action',textContent:'Đóng'});close.onclick=()=>dialog.close();
 dialog.replaceChildren(el('h2',{textContent:'🔑 API key'}),el('p',{className:'helper',textContent:'Key lưu trong thư mục .local của ứng dụng trên máy này (không đưa vào ZIP hay bản cập nhật), dùng chung cho mọi chức năng. Không gửi key trong chat.'}),...list,el('div',{className:'dub-actions'},close))}
function badge(){const ok=state.openai?.saved&&state.ai33?.saved;open.classList.toggle('ok',!!ok);open.title=ok?'OpenAI ✓ · ai33 ✓ · bấm để quản lý key':'Còn thiếu key: bấm để nhập OpenAI / ai33 key'}
window.openKeys=()=>{drawKeys();dialog.showModal()};open.onclick=()=>window.openKeys();
document.addEventListener('keys-changed',badge);
request('/secrets').then(d=>{state=d;for(const r of rows)r();badge()}).catch(()=>{});
})();
