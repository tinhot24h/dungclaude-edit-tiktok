'use strict';
// Text editing inside the Title/Body tabs, the text-layer list in the Text tool, and the user's own saved
// text styles (per layer) and whole designs (colours, frame, fonts, layout, image layers — no text, no media).
(()=>{
const design=window.studioApi,keys=window.TEXT_KEYS;
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const json=(url,body)=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const LABEL=k=>k==='title'?'Tiêu đề':k==='body'?'Nội dung':'Chữ '+k.slice(4);
const say=text=>{const s=$('workspace-status');if(s)s.textContent=text;$('preview-state').textContent=text};

// ---- title / body text boxes move into their own properties tab (same element ids, so AI and projects keep working)
for(const k of ['title','body']){const sec=$('section-'+k),area=$(k),lab=document.querySelector(`label[for=${k}]`);lab.classList.add('text-content-label');area.rows=k==='title'?2:5;area.classList.add('text-content');sec.prepend(lab,area)}
const hint=[...$('pane-text').querySelectorAll('p.helper')].find(p=>p.textContent.startsWith('Enter để xuống dòng'));if(hint)hint.remove();
for(const k of keys){const area=$(k),meta=el('div',{className:'text-count'});area.after(meta);const count=()=>{meta.textContent=`${area.value.length}/${area.maxLength} ký tự · Enter xuống dòng · nhấp đúp chữ trên khung hình để sửa tại chỗ`};area.addEventListener('input',count);document.addEventListener('history-applied',count);count()}

// ---- list of text layers in the Text tool: click opens the layer's tab, the text is edited there
const list=el('div',{id:'text-layer-list',className:'text-layer-list'});
$('pane-text').querySelector('.pane-title').after(list);
function layers(){list.replaceChildren(...keys.filter(k=>k==='title'||k==='body'||$(k).value.trim()).map(k=>{const text=$(k).value.replace(/\s+/g,' ').trim(),start=Number($(k+'_start').value)||0,end=Number($(k+'_end').value)||0;
 const row=el('button',{type:'button',className:'text-layer-row'},el('span',{className:'tl-icon-t',textContent:'T'}),el('span',{className:'text-layer-info'},el('strong',{textContent:LABEL(k)}),el('small',{textContent:text||'(trống · không hiện trên video)'})),el('em',{textContent:start||end?`${start}s → ${end?end+'s':'hết'}`:'cả video'}));
 row.onclick=()=>{activate(k);window.editorTimeline.selectLayer(k);setTimeout(()=>{$(k).focus();$(k).setSelectionRange($(k).value.length,$(k).value.length)},30)};return row}))}
document.addEventListener('design-changed',()=>{clearTimeout(layers.t);layers.t=setTimeout(layers,150)});layers();

// ---- my text styles: one shared list, a picker in every text tab
const PROPS=['font','size','color','align','valign','gap','outline','outline_color','box','box_color','box_opacity','box_pad','box_radius','width'];
let styles=[];
const pickers=[];
for(const k of keys){const sec=$('section-'+k),anchor=[...sec.querySelectorAll('.group-label')].find(g=>g.textContent==='KIỂU CHỮ');
 const pick=el('select',{className:'style-pick',ariaLabel:'Kiểu chữ đã lưu'}),apply=el('button',{type:'button',className:'outline-action small-action',textContent:'Áp dụng'}),save=el('button',{type:'button',className:'outline-action small-action',textContent:'Lưu kiểu này'}),drop=el('button',{type:'button',className:'outline-action small-action danger-action',textContent:'Xóa',title:'Xóa kiểu đã chọn'});
 const row=el('div',{className:'my-styles'},el('div',{className:'group-label',textContent:'KIỂU CHỮ CỦA TÔI'}),pick,el('div',{className:'result-actions'},apply,save,drop));
 (anchor||sec.firstChild).before(row);pickers.push(pick);
 apply.onclick=()=>useStyle(k,pick.value);pick.ondblclick=apply.onclick;save.onclick=()=>saveStyle(k);drop.onclick=()=>dropStyle(pick.value)}
function fillStyles(){for(const p of pickers){const keep=p.value;p.replaceChildren(new Option(styles.length?'— Chọn kiểu đã lưu —':'Chưa có kiểu nào · bấm “Lưu kiểu này”',''),...styles.map(s=>new Option(s.name,s.id)));p.value=styles.some(s=>s.id===keep)?keep:''}}
async function loadStyles(){try{styles=(await request('/library/styles')).items;fillStyles()}catch{}}
async function saveStyle(k){const name=prompt('Tên kiểu chữ:',`${LABEL(k)} · ${$(k+'_size').value}px`);if(!name?.trim())return;const data={};for(const p of PROPS)data[p]=$(k+'_'+p).value;
 try{await json('/library/styles/save',{name:name.trim().slice(0,120),data:{style:data}});await loadStyles();say(`Đã lưu kiểu chữ "${name.trim()}". Dùng được cho mọi lớp chữ.`)}catch(e){say(e.message)}}
async function useStyle(k,id){if(!id){say('Chọn một kiểu chữ đã lưu trước.');return}try{const r=await request('/library/styles/'+id),data=r.data.style||{};for(const p of PROPS)if(data[p]!=null&&$(k+'_'+p))$(k+'_'+p).value=data[p];design.schedule();window.appHistory?.checkpoint();say(`Đã áp dụng kiểu "${r.name}" cho ${LABEL(k)}. Ctrl+Z để hoàn tác.`)}catch(e){say(e.message)}}
async function dropStyle(id){const s=styles.find(x=>x.id===id);if(!s){say('Chọn kiểu cần xóa.');return}if(!confirm(`Xóa kiểu chữ "${s.name}"?`))return;try{await request(`/library/styles/${id}/delete`,{method:'POST'});await loadStyles();say('Đã xóa kiểu chữ.')}catch(e){say(e.message)}}
loadStyles();

// ---- my designs (templates): saved next to the reset button in the properties column
const mine=el('div',{className:'my-designs',id:'my-designs'});
mine.innerHTML='<div class="group-label">THIẾT KẾ CỦA TÔI</div><select id="design-pick" aria-label="Thiết kế đã lưu"></select><div class="result-actions"><button type="button" id="design-apply" class="outline-action small-action">Áp dụng</button><button type="button" id="design-save" class="primary-action small-action">Lưu thiết kế hiện tại</button><button type="button" id="design-delete" class="outline-action small-action danger-action">Xóa</button></div><p class="helper">Giữ màu nền, khung, font, cỡ chữ, vị trí chữ/video và lớp ảnh/logo; không giữ nội dung chữ hay video/MP3.</p>';
$('reset').before(mine);
let designs=[];
async function loadDesigns(){try{designs=(await request('/library/templates')).items;const keep=$('design-pick').value;$('design-pick').replaceChildren(new Option(designs.length?'— Chọn thiết kế đã lưu —':'Chưa có thiết kế nào',''),...designs.map(d=>new Option(d.name,d.id)));$('design-pick').value=designs.some(d=>d.id===keep)?keep:''}catch{}}
$('design-save').onclick=async()=>{const name=prompt('Tên thiết kế:','Thiết kế '+new Date().toLocaleDateString('vi-VN'));if(!name?.trim())return;try{const r=await json('/library/templates/save',{name:name.trim().slice(0,120),data:{design:design.snapshot(false)}});await loadDesigns();$('design-pick').value=r.id;say(`Đã lưu thiết kế "${r.name}".`)}catch(e){say(e.message)}};
$('design-apply').onclick=async()=>{const id=$('design-pick').value;if(!id){say('Chọn một thiết kế đã lưu trước.');return}try{const r=await request('/library/templates/'+id);design.apply(r.data.design);window.appHistory?.checkpoint();say(`Đã áp dụng thiết kế "${r.name}". Ctrl+Z để hoàn tác.`)}catch(e){say(e.message)}};
$('design-pick').ondblclick=$('design-apply').onclick;
$('design-delete').onclick=async()=>{const d=designs.find(x=>x.id===$('design-pick').value);if(!d){say('Chọn thiết kế cần xóa.');return}if(!confirm(`Xóa thiết kế "${d.name}"?`))return;try{await request(`/library/templates/${d.id}/delete`,{method:'POST'});await loadDesigns();say('Đã xóa thiết kế.')}catch(e){say(e.message)}};
loadDesigns();
})();
