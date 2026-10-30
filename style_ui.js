'use strict';
// Văn phong: "👁 Xem / sửa" shows the guidance each văn phong gives the AI (summary, tone, first 3 seconds, order of
// ideas, words to use / avoid, example opening, title kinds); edit it, reset a built-in one, or make a new one from a
// copy. Saved in .local/dub/styles.json on this computer; the chosen one goes with every job and every preset.
// "Xem toàn bộ câu lệnh gửi AI" shows the exact instructions of the current setup (server: Store.prompt_preview).
(()=>{
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const json=(url,body)=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const say=m=>window.dubApi?.say?.(m);
const FIELDS=[['label','Tên văn phong','Hiện trong ô chọn',1],['summary','Mô tả ngắn','Dùng cả khi dịch theo timestamp (từng dòng): giữ ngắn',2],
 ['tone','Giọng văn','Ví dụ: như bạn bè giới thiệu món đồ hay, gần gũi',2],['open','3 giây đầu','Cách mở để giữ chân người xem',2],
 ['flow','Trình tự ý','Ví dụ: vấn đề → món đồ → lợi ích → câu chốt',2],['use','Nên dùng','Từ / cụm từ nên dùng',2],['avoid','Tránh','Từ / kiểu câu cần tránh',2],
 ['example','Câu mở mẫu','Chỉ để AI cảm giọng, không chép nguyên',1],['titles','Kiểu tiêu đề ưu tiên','Dùng khi Kiểu tiêu đề = Tự chọn',1]];
let rows=[],limits={},loaded=false,wanted='',pending=[];
const sel=()=>$('dub-style');
const row=id=>rows.find(r=>r.id===id);
const same=(a,b)=>FIELDS.every(([k])=>(a?.[k]||'')===(b?.[k]||''));
async function load(){try{const d=await request('/dub/styles');rows=d.styles;limits=d.limits||{};loaded=true;fill();for(const[s,p]of pending.splice(0))await adopt(s,p)}catch(e){say(e.message)}}
function fill(){const s=sel();if(!s)return;const keep=wanted||s.value||'review';
 const built=rows.filter(r=>r.builtin),own=rows.filter(r=>!r.builtin);
 s.replaceChildren(...built.map(r=>new Option(r.profile.label+(r.edited?' ✎':''),r.id)),...(own.length?[el('optgroup',{label:'Văn phong tự tạo'},...own.map(r=>new Option(r.profile.label,r.id)))]:[]));
 s.value=row(keep)?keep:'review';wanted='';window.dubApi?.labels?.()}
// the profile sent with a job: only when it differs from the built-in text (custom ones always)
function profileFor(id){const r=row(id);return r&&(r.edited||!r.builtin)?r.profile:null}
// a preset (or a job being edited) carries its văn phong: a custom one this computer does not have is added, an
// edited built-in one replaces the local text (the preset check lists it before applying)
async function adopt(id,profile){wanted=id;if(!loaded){pending.push([id,profile]);return}
 const r=row(id);if(r&&same(r.profile,profile)){fill();return}
 try{const d=await json('/dub/styles/save',{id,profile});rows=d.styles;fill()}catch(e){say('Không thêm được văn phong của mẫu: '+e.message)}}
window.dubStyles={profileFor,adopt,rows:()=>rows,load};

// ---- "👁 Xem / sửa"
const dlg=el('dialog',{id:'dub-style-dialog',className:'dub-dialog wide style-dialog'});document.body.append(dlg);
function openEditor(id){const r=row(id)||row('review');if(!r)return;const inputs={};
 const pick=el('select',{'aria-label':'Văn phong đang xem'},...rows.map(x=>new Option((x.builtin?'':'★ ')+x.profile.label+(x.builtin&&x.edited?' ✎':''),x.id)));pick.value=r.id;pick.onchange=()=>openEditor(pick.value);
 const grid=el('div',{className:'style-grid'},...FIELDS.map(([k,label,hint,lines])=>{const max=limits[k]||400;
  const box=lines>1?el('textarea',{rows:lines,maxLength:max,value:r.profile[k]||''}):el('input',{type:'text',maxLength:max,value:r.profile[k]||''});
  const def=r.builtin?(r.default[k]||''):'';box.placeholder=def||hint;const count=el('small',{className:'style-count'});
  const changed=el('small',{className:'style-changed',textContent:'đã sửa',hidden:true});
  const sync=()=>{count.textContent=`${box.value.length}/${max}`;changed.hidden=!r.builtin||box.value.trim()===def};box.oninput=sync;sync();inputs[k]=box;
  return el('label',{className:'style-field'},el('span',{},label,changed,count),box,el('small',{className:'helper',textContent:hint}))}));
 const read=()=>Object.fromEntries(FIELDS.map(([k])=>[k,inputs[k].value.trim()]));
 const note=el('p',{className:'helper style-note'});
 const save=el('button',{type:'button',className:'primary-action small-action',textContent:'💾 Lưu'});
 save.onclick=async()=>{try{const d=await json('/dub/styles/save',{id:r.id,profile:read()});rows=d.styles;fill();sel().value=r.id;sel().dispatchEvent(new Event('change',{bubbles:true}));say(`Đã lưu văn phong "${read().label}". Áp dụng cho các video chạy từ giờ.`);openEditor(r.id)}catch(e){note.textContent=e.message}};
 const copy=el('button',{type:'button',className:'outline-action small-action',textContent:'＋ Lưu thành văn phong mới'});
 copy.onclick=async()=>{const name=prompt('Tên văn phong mới:',read().label+' (bản riêng)');if(!name?.trim())return;
  try{const d=await json('/dub/styles/save',{profile:{...read(),label:name.trim().slice(0,60)}});rows=d.styles;fill();sel().value=d.id;sel().dispatchEvent(new Event('change',{bubbles:true}));say(`Đã tạo văn phong "${name.trim()}" và chọn nó.`);openEditor(d.id)}catch(e){note.textContent=e.message}};
 const drop=el('button',{type:'button',className:'outline-action small-action danger-action',textContent:r.builtin?'↺ Về mặc định':'🗑 Xóa văn phong',hidden:r.builtin&&!r.edited});
 drop.onclick=async()=>{if(!confirm(r.builtin?`Đưa "${r.profile.label}" về nội dung mặc định?`:`Xóa văn phong "${r.profile.label}"?`))return;
  try{const d=await json('/dub/styles/delete',{id:r.id});rows=d.styles;fill();if(!r.builtin&&sel().value!==r.id){sel().value='review';sel().dispatchEvent(new Event('change',{bubbles:true}))}say(r.builtin?'Đã về mặc định.':'Đã xóa văn phong.');openEditor(r.builtin?r.id:'review')}catch(e){note.textContent=e.message}};
 const close=el('button',{type:'button',className:'outline-action small-action',textContent:'Đóng'});close.onclick=()=>dlg.close();
 note.textContent=r.builtin?(r.edited?'Văn phong có sẵn, đã được sửa trên máy này.':'Văn phong có sẵn của app. Sửa rồi Lưu là dùng bản của bạn; "Về mặc định" để lấy lại.'):'Văn phong bạn tự tạo.';
 dlg.replaceChildren(el('div',{className:'dub-review-head'},el('h2',{textContent:'🗣 Văn phong'}),pick),note,grid,
  el('p',{className:'helper',textContent:'Mỗi mục là một dòng hướng dẫn gửi AI (để trống = bỏ dòng đó). Mức hào hứng, xưng hô, ghi chú và Mẫu câu lệnh được ghép thêm: xem ở "Xem toàn bộ câu lệnh gửi AI". Văn phong đang chọn được lưu cùng Mẫu.'}),
  el('div',{className:'dub-actions'},drop,copy,save,close));
 if(!dlg.open)dlg.showModal()}

// ---- "Xem toàn bộ câu lệnh gửi AI"
const pdlg=el('dialog',{id:'dub-prompt-dialog',className:'dub-dialog wide prompt-dialog'});document.body.append(pdlg);
async function openPrompt(){const close=el('button',{type:'button',className:'outline-action small-action',textContent:'Đóng'});close.onclick=()=>pdlg.close();
 pdlg.replaceChildren(el('h2',{textContent:'📜 Toàn bộ câu lệnh gửi AI'}),el('p',{className:'helper',textContent:'Đang ghép câu lệnh…'}),el('div',{className:'dub-actions'},close));pdlg.showModal();
 const f=window.dubApi?.files?.()||[],cur=f[0];
 try{const d=await json('/dub/prompt-preview',{options:window.dubApi.settings(),hint:cur?.hint||'',video_name:cur?.name||''});
  const blocks=d.calls.map(c=>{const copy=el('button',{type:'button',className:'chip-button',textContent:'📋 Copy'});copy.onclick=async()=>{try{await navigator.clipboard.writeText(c.text);copy.textContent='✓ Đã copy'}catch{copy.textContent='Không copy được'}};
   return el('section',{className:'prompt-call'},el('div',{className:'prompt-head'},el('strong',{textContent:c.title}),el('small',{textContent:`${c.text.length.toLocaleString('vi-VN')} ký tự`}),copy),el('pre',{textContent:c.text}),el('small',{className:'helper',textContent:c.data||''}))});
  pdlg.replaceChildren(el('h2',{textContent:'📜 Toàn bộ câu lệnh gửi AI'}),el('p',{className:'helper',textContent:d.note+' Theo thiết lập đang chọn ở cột trái'+(cur?` · video: ${cur.name}`:'')+'.'}),...blocks,el('div',{className:'dub-actions'},close))}
 catch(e){pdlg.replaceChildren(el('h2',{textContent:'📜 Toàn bộ câu lệnh gửi AI'}),el('p',{className:'helper',textContent:'Không ghép được: '+e.message}),el('div',{className:'dub-actions'},close))}}

const wire=()=>{const b=$('dub-style-edit');if(!b||!sel()?.options.length){setTimeout(wire,150);return}
 b.onclick=()=>openEditor(sel().value);$('dub-prompt-view').onclick=e=>{e.preventDefault();openPrompt()};load()};
wire();
})();
