'use strict';
// Mẫu (presets) of the dub page, by part: a preset keeps only the parts ticked when it was saved (Giọng & dịch, Nền &
// khung, Tiêu đề / Nội dung, Video, Overlay…) and applying it changes only those parts, so presets combine. The bar
// shows the preset in use and how many settings differ from it; applying lists what changes and what is missing
// first. Settings of this computer (encoder, videos at once, output folder, keys) are never put in a preset.
// Presets saved before 0.42 hold every part. Stored on this computer in .local/library/dubpresets.
(()=>{
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const json=(url,body)=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const api=()=>window.dubApi,say=m=>api()?.say?.(m),KIND='dubpresets';
const store=(k,v)=>{try{v==null?localStorage.removeItem(k):localStorage.setItem(k,v)}catch{}},read=k=>{try{return localStorage.getItem(k)||''}catch{return''}};
const ACTIVE='dq-preset-active',DEFAULT='dq-preset-default';
// ---- parts: which settings (and which keys of the design) belong where
const MACHINE=new Set(['encoder']);
const NOTE=new Set(['rules_saved','rules_name']);   // which Mẫu câu lệnh a preset carries: information, not a setting to compare
const PARTS=[
 ['run','⚙ Chế độ chạy',k=>k==='run_mode'],
 ['voice','🗣 Giọng & dịch',k=>/^(mode|language|model|style|style_profile|energy|pronoun|rate|notes|no_price|review|voice_id|voice_speed|voice_volume|max_tempo|min_tempo|video_speed_min|video_speed_max|dictionary_id|align|end_with_voice|vision|reuse|instructions|rules_saved|rules_name)$/.test(k)],
 ['audio','🎵 Âm thanh gốc',k=>/^(background|duck_level|background_volume)$/.test(k)],
 ['video','✂ Video (cắt, vị trí, màu)',k=>/^(trim_start|trim_end|edge_trim|frame_(canvas|fit|zoom|x|y|rotate|flip)|adjust.*)$/.test(k),d=>/^(video_|motion_amount$)/.test(d)],
 ['design','🎨 Nền & khung',k=>/^(design_bg|layer_order)$/.test(k),d=>!/^(video_|motion_amount$|title|body|text\d)/.test(d)],
 ['texts','🅣 Tiêu đề & nội dung',k=>/^(design_title|design_body|title_source|body_source|title_chars|body_min_chars|body_max_chars|review_texts|title_style)$/.test(k),d=>/^(title|body|text\d)/.test(d)],
 ['overlay','✨ Video overlay',k=>/^overlay/.test(k)],
 ['image','🖼 Lớp ảnh',k=>/^image/.test(k)],
 ['music','🎶 Nhạc nền',k=>/^music/.test(k)],
 ['captions','💬 Phụ đề chữ chạy',k=>/^caption/.test(k)],
 ['export','⬇ Xuất & thông tin file',k=>/^(out_resolution|out_fps|out_quality|subtitles|loudness|overwrite_export|meta.*)$/.test(k)]];
const ALL=PARTS.map(p=>p[0]),NAME=Object.fromEntries(PARTS.map(p=>[p[0],p[1]]));
const partOf=k=>MACHINE.has(k)||k==='design'?null:(PARTS.find(p=>p[2](k))||PARTS[1])[0];   // unknown keys travel with Giọng & dịch
const designPart=d=>(PARTS.find(p=>p[3]&&p[3](d))||PARTS[4])[0];
// the settings of the chosen parts only
function pick(o,parts){const want=new Set(parts),out={};
 for(const[k,v]of Object.entries(o)){if(k==='design'||k==='design_error')continue;const part=partOf(k);if(part&&want.has(part))out[k]=v}
 if(o.design&&typeof o.design==='object'){const d=Object.fromEntries(Object.entries(o.design).filter(([k])=>want.has(designPart(k))));if(Object.keys(d).length)out.design=d}
 return out}
// current settings with a preset's parts on top (everything else, and this computer's settings, stays)
function merged(cur,saved){const out={...cur};for(const[k,v]of Object.entries(saved)){if(k==='design'||MACHINE.has(k))continue;out[k]=v}
 if(saved.design)out.design={...(cur.design||{}),...saved.design};return out}
const eq=(a,b)=>JSON.stringify(a??null)===JSON.stringify(b??null);
// settings of the preset that differ now, by part
function diff(saved,cur){const by={};const add=(part,k)=>{(by[part]=by[part]||[]).push(k)};
 for(const[k,v]of Object.entries(saved)){if(k==='design'||MACHINE.has(k)||NOTE.has(k))continue;if(!eq(v,cur[k]))add(partOf(k),k)}
 for(const[k,v]of Object.entries(saved.design||{}))if(!eq(v,cur.design?.[k]))add(designPart(k),'design.'+k);return by}
const count=by=>Object.values(by).reduce((a,l)=>a+l.length,0);
// older presets (before 0.42): every part, settings as saved
const partsOf=r=>Array.isArray(r?.data?.parts)?r.data.parts.filter(p=>ALL.includes(p)):ALL;

// ---- state
let list=[],active=null;   // active = full record {id,name,data:{settings,parts,meta}}
async function loadList(){try{list=(await request('/library/'+KIND)).items}catch{list=[]}}
async function getRecord(id){return request(`/library/${KIND}/${id}`)}

// ---- the bar (replaces the old select + save + delete)
const bar=el('div',{className:'preset-bar'});
const nameBtn=el('button',{type:'button',className:'preset-name',title:'Quản lý mẫu: áp dụng, đổi tên, nhân bản, mặc định, xóa'});
const saveBtn=el('button',{type:'button',className:'outline-action small-action',textContent:'💾 Lưu'});
const newBtn=el('button',{type:'button',className:'outline-action small-action',textContent:'＋ Lưu mới'});
const backBtn=el('button',{type:'button',className:'outline-action small-action',textContent:'↺ Về mẫu',title:'Bỏ các thay đổi, áp lại đúng mẫu đang dùng',hidden:true});
bar.append(nameBtn,saveBtn,newBtn,backBtn);
function drawBar(){const cur=api()?.settings?.();nameBtn.replaceChildren();
 if(!active){nameBtn.append(el('span',{className:'preset-label',textContent:'📁 Mẫu'}),el('b',{textContent:list.length?'— chọn mẫu —':'chưa có mẫu'}));backBtn.hidden=true;saveBtn.title='Lưu thông số hiện tại thành mẫu mới';return}
 const by=cur?diff(active.data.settings||{},cur):{},n=count(by);
 nameBtn.append(el('span',{className:'preset-label',textContent:'📁 Mẫu'}),el('b',{textContent:active.name}),...(n?[el('span',{className:'preset-dirty',textContent:`● đã sửa ${n}`})]:[el('span',{className:'preset-clean',textContent:'✓'})]));
 nameBtn.title=n?'Khác mẫu ở: '+Object.entries(by).map(([p,l])=>`${NAME[p]} (${l.length})`).join(', ')+'\nBấm để quản lý mẫu.':'Đang đúng như mẫu. Bấm để quản lý mẫu.';
 backBtn.hidden=!n;saveBtn.title=`Ghi đè mẫu "${active.name}" (${partsOf(active).length} phần) bằng thông số hiện tại`}
let drawTimer=0;const later=()=>{clearTimeout(drawTimer);drawTimer=setTimeout(drawBar,250)};

// ---- save
const sdlg=el('dialog',{id:'preset-save',className:'dub-dialog preset-dialog'});document.body.append(sdlg);
function openSave(mode){const cur=api().settings(),edit=mode==='over'&&active;
 const name=el('input',{type:'text',maxLength:120,value:edit?active.name:'Mẫu '+new Date().toLocaleDateString('vi-VN'),placeholder:'Tên mẫu'});
 const desc=el('input',{type:'text',maxLength:200,value:edit?(active.data.meta?.desc||''):'',placeholder:'Mô tả ngắn (không bắt buộc), ví dụ: review đồ bếp, khung hồng'});
 const start=new Set(edit?partsOf(active):active?partsOf(active):ALL);
 const boxes=PARTS.map(([k,label])=>{const c=el('input',{type:'checkbox',checked:start.has(k)});c.dataset.part=k;return el('label',{className:'preset-part'},c,el('span',{textContent:label}))});
 const all=el('button',{type:'button',className:'chip-button',textContent:'Chọn hết'});all.onclick=()=>boxes.forEach(b=>b.querySelector('input').checked=true);
 const none=el('button',{type:'button',className:'chip-button',textContent:'Bỏ hết'});none.onclick=()=>boxes.forEach(b=>b.querySelector('input').checked=false);
 const def=el('input',{type:'checkbox',checked:edit&&read(DEFAULT)===active.id});
 const note=el('p',{className:'helper'});
 const go=el('button',{type:'button',className:'primary-action small-action',textContent:edit?'💾 Ghi đè mẫu':'💾 Lưu mẫu mới'});
 go.onclick=async()=>{const parts=boxes.map(b=>b.querySelector('input')).filter(c=>c.checked).map(c=>c.dataset.part);const n=name.value.trim();
  if(!n){note.textContent='Đặt tên cho mẫu.';name.focus();return}if(!parts.length){note.textContent='Chọn ít nhất một phần.';return}
  const same=list.find(r=>r.name.toLowerCase()===n.toLowerCase()&&(!edit||r.id!==active.id));
  if(same&&!confirm(`Đã có mẫu tên "${same.name}". Ghi đè mẫu đó?`))return;
  const o={...cur};if(parts.includes('voice')){o.rules_saved=true;o.rules_name=read('review-ai-rules-name')}
  const settings=pick(o,parts),id=edit?active.id:same?.id;
  try{const r=await json(`/library/${KIND}/save`,{id,name:n,data:{v:2,settings,parts,meta:{parts,desc:desc.value.trim().slice(0,200),used:new Date().toISOString()}}});
   if(def.checked)store(DEFAULT,r.id);else if(read(DEFAULT)===r.id)store(DEFAULT,null);
   active=await getRecord(r.id);store(ACTIVE,r.id);await loadList();drawBar();sdlg.close();say(`Đã lưu mẫu "${r.name}" (${parts.length} phần).`)}catch(e){note.textContent=e.message}};
 const close=el('button',{type:'button',className:'outline-action small-action',textContent:'Hủy'});close.onclick=()=>sdlg.close();
 sdlg.replaceChildren(el('h2',{textContent:edit?`💾 Ghi đè mẫu "${active.name}"`:'💾 Lưu thành mẫu mới'}),
  el('label',{className:'preset-field'},el('span',{textContent:'Tên mẫu'}),name),el('label',{className:'preset-field'},el('span',{textContent:'Mô tả'}),desc),
  el('div',{className:'preset-parts-head'},el('strong',{textContent:'Lưu những phần nào'}),all,none),el('div',{className:'preset-parts'},...boxes),
  el('p',{className:'helper',textContent:'Khi áp dụng, mẫu chỉ đổi các phần được chọn; phần khác giữ nguyên, nên ghép được nhiều mẫu (vd. mẫu khung + mẫu giọng). Bộ mã hóa, số video chạy cùng lúc, thư mục xuất và key là của máy này, không lưu vào mẫu.'}),
  el('label',{className:'check-row'},def,' ⭐ Áp dụng mẫu này khi mở app'),note,el('div',{className:'dub-actions'},close,go));
 sdlg.showModal();name.select()}
saveBtn.onclick=()=>openSave(active?'over':'new');newBtn.onclick=()=>openSave('new');
backBtn.onclick=()=>active&&applyRecord(active,{check:false});

// ---- apply: what changes and what is missing, then apply
async function missing(saved){const out=[];const ids=async(url,key)=>{try{return new Set(((await request(url))[key]||[]).map(x=>x.id))}catch{return null}};
 if(Array.isArray(saved.overlay_ids)&&saved.overlay_ids.length){const have=await ids('/overlays','overlays');const lost=have&&saved.overlay_ids.filter(i=>!have.has(i));if(lost?.length)out.push(`${lost.length}/${saved.overlay_ids.length} overlay đã chọn không còn trong thư viện (bỏ qua)`)}
 if(saved.image&&saved.image_id){const have=await ids('/dub/images','images');if(have&&!have.has(saved.image_id))out.push('Ảnh của lớp ảnh không còn trong thư viện: lớp ảnh sẽ trống')}
 if(Array.isArray(saved.music_ids)&&saved.music_ids.length){const have=await ids('/dub/music','music');const lost=have&&saved.music_ids.filter(i=>!have.has(i));if(lost?.length)out.push(`${lost.length}/${saved.music_ids.length} bài nhạc nền không còn trong kho (bỏ qua)`)}
 const frame=saved.design?.frame_id;if(frame&&saved.design?.frame_style==='custom'){const have=await ids('/frames','frames');if(have&&!have.has(frame))out.push('Khung PNG của mẫu không còn: khung sẽ trống')}
 if(saved.style&&String(saved.style).startsWith('c_')&&!window.dubStyles?.rows?.().some(r=>r.id===saved.style))out.push(`Văn phong "${saved.style_profile?.label||saved.style}" của mẫu sẽ được thêm vào máy này`);
 else if(saved.style_profile&&window.dubStyles?.rows?.().some(r=>r.id===saved.style&&r.builtin&&JSON.stringify(r.profile)!==JSON.stringify({...r.profile,...saved.style_profile})))out.push(`Văn phong "${saved.style_profile.label}" sẽ theo bản đã sửa trong mẫu`);
 return out}
const adlg=el('dialog',{id:'preset-apply',className:'dub-dialog preset-dialog'});document.body.append(adlg);
async function applyRecord(rec,{check=true}={}){const saved=rec.data?.settings||{},cur=api().settings(),parts=partsOf(rec);
 const run=async()=>{api().apply(merged(cur,saved));api().remember?.();active=rec;store(ACTIVE,rec.id);
  try{await json(`/library/${KIND}/save`,{id:rec.id,name:rec.name,data:{...rec.data,meta:{...(rec.data.meta||{}),parts,used:new Date().toISOString()}}})}catch{}
  await loadList();drawBar();say(`Đã áp dụng mẫu "${rec.name}" (${parts.length} phần).`)};
 if(!check)return run();
 const by=diff(saved,cur),lost=await missing(saved);
 const close=el('button',{type:'button',className:'outline-action small-action',textContent:'Hủy'});close.onclick=()=>adlg.close();
 const go=el('button',{type:'button',className:'primary-action small-action',textContent:'✓ Áp dụng'});go.onclick=async()=>{adlg.close();await run()};
 adlg.replaceChildren(el('h2',{textContent:`📁 Áp dụng mẫu "${rec.name}"`}),...(rec.data?.meta?.desc?[el('p',{className:'helper',textContent:rec.data.meta.desc})]:[]),
  el('div',{className:'preset-chips'},...parts.map(p=>el('span',{className:'preset-chip'+(by[p]?' on':''),textContent:NAME[p]+(by[p]?` · đổi ${by[p].length}`:' · như hiện tại')}))),
  el('p',{className:'helper',textContent:count(by)?`Sẽ đổi ${count(by)} thông số. Các phần không có trong mẫu và thông số của máy này giữ nguyên.`:'Thông số hiện tại đã giống mẫu này.'}),
  ...(lost.length?[el('div',{className:'group-label',textContent:'CẦN BIẾT'}),el('ul',{className:'dub-check-warn'},...lost.map(t=>el('li',{textContent:t})))]:[]),
  el('div',{className:'dub-actions'},close,go));
 adlg.showModal()}

// ---- manager
const mdlg=el('dialog',{id:'preset-manager',className:'dub-dialog wide preset-manager'});document.body.append(mdlg);
let query='';
function thumb(rec,box){const d=rec.data?.settings?.design;if(!d||!partsOf(rec).some(p=>p==='design'||p==='texts')){box.classList.add('empty');box.textContent='🎙';return}
 request('/design',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...d,title:d.title||'Tiêu đề mẫu',body:d.body||'Nội dung mẫu hiển thị trên khung video.'})}).then(r=>{
  const k=box.clientWidth/720;box.classList.remove('empty');box.replaceChildren(el('img',{src:r.image,alt:''}),...(r.frame_image?[el('img',{src:r.frame_image,alt:''})]:[]),
   ...(r.text||[]).map(t=>el('div',{className:'preset-thumb-text',textContent:t.text,style:`left:${t.x*k}px;top:${(t.content_y??t.y)*k}px;width:${t.width*k}px;font:${Math.max(4,t.size*k)}px/${Math.max(5,(t.size+t.gap)*k)}px ${JSON.stringify(t.family)};color:${t.color};text-align:${t.align==='justify'?'left':t.align}`})))}).catch(()=>{box.classList.add('empty');box.textContent='🎨'})}
async function openManager(){await loadList();drawManager();if(!mdlg.open)mdlg.showModal()}
function drawManager(){const def=read(DEFAULT),q=query.trim().toLowerCase();
 const search=el('input',{type:'search',value:query,placeholder:'🔍 Tìm mẫu…'});search.oninput=()=>{query=search.value;const pos=search.selectionStart;drawManager();const s=mdlg.querySelector('input[type=search]');s.focus();s.setSelectionRange(pos,pos)};
 const add=el('button',{type:'button',className:'primary-action small-action',textContent:'＋ Lưu thông số hiện tại thành mẫu'});add.onclick=()=>{mdlg.close();openSave('new')};
 const shown=list.filter(r=>!q||r.name.toLowerCase().includes(q)||(r.meta?.desc||'').toLowerCase().includes(q));
 const cards=shown.map(r=>{const parts=Array.isArray(r.meta?.parts)?r.meta.parts:ALL,box=el('div',{className:'preset-thumb'});
  const act=(t,cls,fn,title='')=>{const b=el('button',{type:'button',className:cls,textContent:t,title});b.onclick=fn;return b};
  const used=r.meta?.used?new Date(r.meta.used).toLocaleString('vi-VN',{dateStyle:'short',timeStyle:'short'}):'';
  const card=el('div',{className:'preset-card'+(active?.id===r.id?' active':'')},box,el('div',{className:'preset-info'},
   el('div',{className:'preset-title'},el('strong',{textContent:r.name}),...(def===r.id?[el('span',{className:'preset-star',textContent:'⭐ mặc định'})]:[]),...(active?.id===r.id?[el('span',{className:'preset-star',textContent:'đang dùng'})]:[])),
   ...(r.meta?.desc?[el('small',{className:'helper',textContent:r.meta.desc})]:[]),
   el('div',{className:'preset-chips'},...(parts.length===ALL.length?[el('span',{className:'preset-chip',textContent:'Đủ mọi phần'})]:parts.map(p=>el('span',{className:'preset-chip',textContent:NAME[p]||p})))),
   el('small',{className:'helper',textContent:(used?'Dùng lần cuối '+used:'Chưa dùng')}),
   el('div',{className:'preset-actions'},
    act('✓ Áp dụng','primary-action small-action',async()=>{mdlg.close();applyRecord(await getRecord(r.id))}),
    act('✎ Đổi tên','outline-action small-action',async()=>{const n=prompt('Tên mới:',r.name);if(!n?.trim()||n.trim()===r.name)return;try{const full=await getRecord(r.id);await json(`/library/${KIND}/save`,{id:r.id,name:n.trim().slice(0,120),data:full.data});if(active?.id===r.id)active.name=n.trim();await loadList();drawManager();drawBar()}catch(e){say(e.message)}}),
    act('⧉ Nhân bản','outline-action small-action',async()=>{try{const full=await getRecord(r.id);await json(`/library/${KIND}/save`,{name:(r.name+' (bản sao)').slice(0,120),data:{...full.data,meta:{...(full.data.meta||{}),used:''}}});await loadList();drawManager()}catch(e){say(e.message)}}),
    act(def===r.id?'☆ Bỏ mặc định':'⭐ Mặc định','outline-action small-action',()=>{store(DEFAULT,def===r.id?null:r.id);drawManager()},'Áp dụng mẫu này mỗi khi mở app'),
    act('🗑','outline-action small-action danger-action',async()=>{if(!confirm(`Xóa mẫu "${r.name}"?`))return;try{await request(`/library/${KIND}/${r.id}/delete`,{method:'POST'});if(read(DEFAULT)===r.id)store(DEFAULT,null);if(active?.id===r.id){active=null;store(ACTIVE,null)}await loadList();drawManager();drawBar()}catch(e){say(e.message)}},'Xóa mẫu'))));
  box.textContent='…';return {card,box,id:r.id}});
 const close=el('button',{type:'button',className:'outline-action small-action',textContent:'Đóng'});close.onclick=()=>mdlg.close();
 mdlg.replaceChildren(el('div',{className:'dub-review-head'},el('h2',{textContent:'📁 Mẫu đã lưu'}),search,add),
  ...(cards.length?[el('div',{className:'preset-grid'},...cards.map(c=>c.card))]:[el('p',{className:'helper',textContent:list.length?'Không có mẫu khớp ô tìm.':'Chưa có mẫu nào. Chỉnh thông số bên trái rồi bấm "＋ Lưu thông số hiện tại thành mẫu".'})]),
  el('div',{className:'dub-actions'},close));
 // previews: one request per visible card, after the dialog is shown
 setTimeout(async()=>{for(const c of cards.slice(0,40)){if(!mdlg.open)return;try{thumb(await getRecord(c.id),c.box)}catch{}}},30)}
nameBtn.onclick=openManager;

// ---- start: take the place of the old controls, restore the preset in use, apply the default one
function mount(){const old=$('dub-preset');if(!old||!api()?.settings){setTimeout(mount,150);return}
 for(const id of ['dub-preset','dub-preset-save','dub-preset-delete'])$(id).hidden=true;old.before(bar);
 const view=old.closest('#view-dub')||document;view.addEventListener('input',later);view.addEventListener('change',later);document.addEventListener('click',later,true);
 document.addEventListener('dub-ready',start,{once:true});setTimeout(start,document.querySelector('#dub-style option')?900:4000)}
let started=false;
async function start(){if(started)return;started=true;await loadList();const def=read(DEFAULT),last=read(ACTIVE);
 try{if(def&&list.some(r=>r.id===def)){const rec=await getRecord(def);await applyRecord(rec,{check:false});say(`Đã áp dụng mẫu mặc định "${rec.name}".`)}
  else if(last&&list.some(r=>r.id===last))active=await getRecord(last)}catch{}
 drawBar()}
window.dubPresets={pick,merged,diff,partsOf,parts:()=>PARTS.map(p=>p[0]),open:openManager};
mount();
})();
