'use strict';
// Editor shell: project bar, tool categories, collapsible panels, resizable timeline,
// transport (timecode, cut jumps, level meter, loudness) and review notes pinned on the preview.
(()=>{
const api=window.editorTimeline,edit=window.editorState,form=$('form'),view=$('view-editor');
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const store=(k,v)=>{try{localStorage.setItem(k,v)}catch{}},load=k=>{try{return localStorage.getItem(k)}catch{return null}};
const fps=()=>Number($('fps').value)||30;
function tc(t){t=Math.max(0,t||0);const f=Math.floor((t%1)*fps()+1e-6);return `${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}:${String(f).padStart(2,'0')}`}
function list(id){try{const v=JSON.parse($(id).value||'[]');return Array.isArray(v)?v:[]}catch{return []}}

// ---- project bar (replaces the page heading and step buttons on wide screens)
const bar=el('div',{className:'project-bar'});
bar.innerHTML=`<div class="pb-left"><span class="pb-mark" aria-hidden="true">▦</span><div class="pb-name"><label for="project-name" class="sr-only">Tên dự án</label></div><button type="button" id="pb-new" class="pb-button">Tạo mới</button><button type="button" id="pb-save" class="pb-button" title="Lưu dự án (Ctrl+S)">Lưu</button><span id="pb-state" class="pb-state"></span></div>
<div class="pb-right"><span id="pb-stats" class="pb-stats"></span><span class="pb-group"><button type="button" class="pb-icon" data-panel="left" title="Ẩn/hiện cột công cụ">◧</button><button type="button" class="pb-icon" data-panel="props" title="Ẩn/hiện cột thuộc tính">▥</button><button type="button" class="pb-icon" data-panel="theater" title="Chế độ trình phát lớn">⛶</button></span><button type="button" id="pb-keys" class="pb-icon" title="Phím tắt (?)">⌨</button><button type="button" id="pb-export" class="pb-export">Xuất bản ↗</button></div>`;
view.prepend(bar);
const name=$('project-name');bar.querySelector('.pb-name').append(name);name.placeholder='Tên dự án';name.title='Tên dự án và tên file xuất';
document.querySelector('label[for=project-name]:not(.sr-only)')?.remove();
$('pb-new').onclick=()=>$('project-new').click();$('pb-save').onclick=()=>window.workspace.saveProject();$('pb-export').onclick=()=>$('submit').click();$('pb-keys').onclick=()=>$('open-shortcuts').click();
const state=()=>{$('pb-state').textContent=$('save-indicator').textContent};new MutationObserver(state).observe($('save-indicator'),{childList:true,characterData:true,subtree:true});state();

// ---- layout toggles, remembered per browser
let layout={left:true,props:true,theater:false};try{Object.assign(layout,JSON.parse(load('review-layout')||'{}'))}catch{}
function applyLayout(){form.classList.toggle('no-left',!layout.left||layout.theater);form.classList.toggle('no-props',!layout.props||layout.theater);form.classList.toggle('theater',layout.theater);
 for(const b of bar.querySelectorAll('[data-panel]'))b.setAttribute('aria-pressed',String(b.dataset.panel==='theater'?layout.theater:layout[b.dataset.panel]));store('review-layout',JSON.stringify(layout));dispatchEvent(new Event('resize'))}
for(const b of bar.querySelectorAll('[data-panel]'))b.onclick=()=>{const k=b.dataset.panel;layout[k]=!layout[k];if(k!=='theater')layout.theater=false;applyLayout()};
applyLayout();

// ---- tool categories in the left column
const panel=document.querySelector('.source-panel'),source=$('pane-source');
const panes={media:el('div',{id:'pane-media',className:'source-pane'}),sound:el('div',{id:'pane-sound',className:'source-pane'}),text:el('div',{id:'pane-text',className:'source-pane'}),export:el('div',{id:'pane-export',className:'source-pane'}),notes:el('div',{id:'pane-notes',className:'source-pane'})};
let into=panes.media;
for(const node of [...source.children]){if(node.matches('.panel-heading'))continue;if(node.matches('label[for=title]'))into=panes.text;if(node.tagName==='HR'){into=panes.export;node.remove();continue}into.append(node)}
source.replaceWith(...Object.values(panes));
panes.media.prepend(el('div',{className:'pane-title',textContent:'Media'}));panes.media.append($('storage-info'),$('cleanup-storage').parentElement);
const sound=panes.media.querySelector('.source-audio');panes.sound.append(el('div',{className:'pane-title',textContent:'Âm thanh'}),sound);
const go=(tab,text)=>{const b=el('button',{type:'button',className:'outline-action small-action',textContent:text});b.onclick=()=>{if(!layout.props){layout.props=true;applyLayout()}activate(tab)};return b};
panes.sound.append(el('div',{className:'result-actions'},go('clip-audio','Thông số giọng đọc ›'),go('clip-music','Nhạc nền ›'),go('clip-video','Âm thanh gốc video ›')));
panes.text.prepend(el('div',{className:'pane-title',textContent:'Chữ trên video'}));{const add=el('button',{type:'button',className:'primary-action small-action',textContent:'＋ Thêm chữ'});add.onclick=()=>window.timelineActions.addText();panes.text.append(el('div',{className:'result-actions'},add,go('title','Kiểu chữ tiêu đề ›'),go('body','Kiểu chữ nội dung ›')),el('p',{className:'helper',textContent:'Mỗi lớp chữ là một thanh trên timeline: kéo thân để dời, kéo mép để đổi thời gian hiện, Delete để xóa. Phím T thêm chữ tại đầu phát.'}))}
panes.export.prepend(el('div',{className:'pane-title',textContent:'Xuất video'}));
const tabs=panel.querySelector('.source-tabs');tabs.hidden=true;
const chips=el('div',{className:'tool-chips',role:'tablist'});
// Library, projects and review notes stay available to code (saving, autosave) but are not shown as tools.
const CATS=[['media','Media'],['sound','Âm thanh'],['text','Chữ'],['export','Xuất']];
for(const[id,text]of CATS){const b=el('button',{type:'button',id:'tool-'+id,textContent:text});b.setAttribute('role','tab');b.onclick=()=>tool(id);chips.append(b)}
panel.prepend(chips);
function tool(id){if(id==='library'||id==='projects')$('source-tab-'+id).click();for(const p of panel.querySelectorAll('.source-pane'))p.hidden=p.id!=='pane-'+id;for(const b of chips.children)b.setAttribute('aria-selected',String(b.id==='tool-'+id));if(!layout.left){layout.left=true;layout.theater=false;applyLayout()}store('review-tool',id)}
window.studioTool=tool;tool(CATS.some(c=>c[0]===load('review-tool'))?load('review-tool'):'media');

// ---- resizable boundary between the upper panels and the timeline
const handle=el('div',{className:'split-handle',title:'Kéo để đổi chiều cao timeline · nhấp đúp để đặt lại'});$('timeline-panel').prepend(handle);
const setTop=px=>{if(px)view.style.setProperty('--top-h',Math.round(Math.max(300,Math.min(innerHeight-140,px)))+'px');else view.style.removeProperty('--top-h');store('review-top-h',px?String(Math.round(px)):'');dispatchEvent(new Event('resize'))};
if(Number(load('review-top-h')))setTop(Number(load('review-top-h')));
handle.onpointerdown=e=>{e.preventDefault();handle.setPointerCapture(e.pointerId);const start=e.clientY,top=document.querySelector('.workspace>.settings').getBoundingClientRect().height;handle.onpointermove=m=>setTop(top+m.clientY-start);handle.onpointerup=()=>{handle.onpointermove=null}};
handle.ondblclick=()=>setTop(0);
document.addEventListener('timeline-expand',()=>{const now=document.querySelector('.workspace>.settings').getBoundingClientRect().height;setTop(now>420?340:0)});

// ---- transport bar: timecode, cut jumps, level meter, loudness
const play=document.querySelector('.playback');
const transport=el('div',{className:'transport'});
transport.innerHTML=`<div class="tp-row"><span class="tp-time"><strong id="tp-now">0:00:00</strong><small id="tp-total">/ 0:00:00</small></span><span class="tp-buttons"><button type="button" id="tp-prev" title="Về điểm cắt/mốc trước">⏮</button><button type="button" id="tp-back" title="Lùi 1 giây (J)">«</button><span id="tp-play-slot"></span><button type="button" id="tp-fwd" title="Tới 1 giây (L)">»</button><button type="button" id="tp-next" title="Tới điểm cắt/mốc sau">⏭</button></span><canvas id="tp-meter" width="220" height="22" title="Mức âm lượng khi phát (dBFS)"></canvas></div><div class="tp-row tp-seek-row"></div><div class="tp-row tp-tools"><span id="tp-loud" class="tp-loud" title="Độ lớn âm thanh theo chuẩn EBU R128">Âm lượng bản xuất: chưa đo</span><button type="button" id="tp-measure" class="chip-button" title="Đo LUFS và True Peak của bản xuất gần nhất">Đo bản xuất</button><button type="button" id="tp-measure-voice" class="chip-button" title="Đo MP3 giọng đọc đang chọn">Đo giọng</button></div>`;
play.before(transport);
$('tp-play-slot').replaceWith($('play'));$('play').textContent='▶';$('play').classList.add('tp-play');
transport.querySelector('.tp-seek-row').append($('seek'));
transport.querySelector('.tp-tools').prepend(...[...play.children]);play.remove();
const seek=d=>{const s=api.state();api.seek(Math.max(0,Math.min(s.plan?.duration||0,s.clock+d)))};
$('tp-back').onclick=()=>seek(-1);$('tp-fwd').onclick=()=>seek(1);$('tp-prev').onclick=()=>window.timelineActions.jump(-1);$('tp-next').onclick=()=>window.timelineActions.jump(1);
function clock(t){const s=api.state(),p=s.plan;$('tp-now').textContent=tc(t);$('tp-total').textContent='/ '+tc(p?.duration||0);$('play').textContent=s.playing?'❚❚':'▶';label(t,p);pins(t)}
document.addEventListener('timeline-clock',e=>clock(e.detail));document.addEventListener('timeline-refresh',()=>{clock(api.state().clock);stats()});
const meter=$('tp-meter'),ctx=meter.getContext('2d');let hold=-60,holdAt=0,buffer;
function drawMeter(){requestAnimationFrame(drawMeter);if(document.hidden||view.hidden)return;const cw=Math.round(meter.clientWidth*devicePixelRatio),ch=Math.round(meter.clientHeight*devicePixelRatio);if(cw&&(meter.width!==cw||meter.height!==ch)){meter.width=cw;meter.height=ch}const a=window.editorMeter,playing=api.state().playing;let db=-60;
 if(a&&playing){buffer=buffer||new Float32Array(a.fftSize);a.getFloatTimeDomainData(buffer);let peak=0;for(const v of buffer)peak=Math.max(peak,Math.abs(v));db=peak>0?Math.max(-60,20*Math.log10(peak)):-60}
 const now=performance.now();if(db>=hold||now-holdAt>1200){hold=db;holdAt=now}const w=meter.width,h=meter.height,x=v=>(v+60)/60*w;ctx.clearRect(0,0,w,h);ctx.fillStyle='#1b2433';ctx.fillRect(0,4,w,h-8);
 const grad=ctx.createLinearGradient(0,0,w,0);grad.addColorStop(0,'#3fd18b');grad.addColorStop(.75,'#3fd18b');grad.addColorStop(.88,'#f4d35e');grad.addColorStop(1,'#ff5a5f');ctx.fillStyle=grad;ctx.fillRect(0,4,x(db),h-8);
 ctx.fillStyle=hold>-1?'#ff5a5f':'#e7edf6';ctx.fillRect(Math.max(0,x(hold)-2),2,2,h-4);ctx.fillStyle='#7f8ea3';ctx.font='9px system-ui';for(const v of [-48,-24,-12,-6,0])ctx.fillRect(x(v)-.5,h-3,1,3)}
requestAnimationFrame(drawMeter);
async function measure(body,labelText){$('tp-loud').textContent='Đang đo '+labelText.toLowerCase()+'…';try{const d=await request('/media/loudness',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const lufs=d.lufs==null?'—':d.lufs.toFixed(1),tp=d.true_peak==null?'—':d.true_peak.toFixed(1),warn=d.true_peak!=null&&d.true_peak>-1?' ⚠ đỉnh quá cao':d.lufs!=null&&(d.lufs<-18||d.lufs>-10)?' · TikTok khuyên ≈ −14':'';$('tp-loud').textContent=`${labelText} ${lufs} LUFS · TP ${tp} dBTP${warn}`}catch(e){$('tp-loud').textContent=e.message}}
$('tp-measure').onclick=()=>{const id=edit.media().video_id;if(!id){$('tp-loud').textContent='Chọn video và xuất trước khi đo.';return}measure({job:id},'BẢN XUẤT')};
$('tp-measure-voice').onclick=()=>{const id=edit.media().audio_asset_id;if(!id){$('tp-loud').textContent='Chưa chọn MP3 giọng đọc.';return}measure({asset:id},'GIỌNG')};

// ---- label of the piece under the playhead, shown on the preview
const tag=el('div',{id:'stage-tag',className:'stage-tag'});$('stage').append(tag);
function label(t,p){if(!p){tag.hidden=true;return}let at=0,index=0;const n=p.segs.length;for(let i=0;i<n;i++){const len=(p.segs[i][1]-p.segs[i][0])/((p.segs[i][2]||1)*p.vr);if(t<at+len||i===n-1){index=i;break}at+=len}tag.hidden=false;tag.textContent=`Đoạn ${String(index+1).padStart(2,'0')}/${String(n).padStart(2,'0')} · ${tc(t)}`}
function stats(){const s=api.state(),p=s.plan,tracks=1+(s.audio?1:0)+(s.music?1:0);$('pb-stats').textContent=p?`${tracks} track · ${p.segs.length} đoạn · ${tc(p.duration).slice(0,-3)} phút`:'Chưa có video'}

// ---- review notes: press C (or the button), click the frame, type the note
const N=panes.notes;
N.innerHTML=`<div class="pane-title">Góp ý</div><button type="button" id="note-mode" class="note-toggle">◎ Bật chế độ Góp ý (C)</button><div id="note-filters" class="note-filters"></div><div id="note-list" class="note-list"></div><p class="helper">Dừng hình ở chỗ cần sửa, bấm C rồi bấm lên khung hình để ghim góp ý đúng thời điểm và vị trí. Góp ý lưu cùng dự án.</p>`;
let noteMode=false,filter='all',focus='';
const STATES=[['open','Mở'],['doing','Đang sửa'],['done','Xong']];
const notes=()=>list('review-notes').filter(n=>n&&typeof n.id==='string');
function saveNotes(rows){$('review-notes').value=JSON.stringify(rows);$('review-notes').dispatchEvent(new Event('input',{bubbles:true}));window.appHistory?.checkpoint();renderNotes();pins(api.state().clock)}
function setMode(on){noteMode=on;$('stage').classList.toggle('note-mode',on);$('note-mode').textContent=on?'◉ Tắt chế độ Góp ý (C / Esc)':'◎ Bật chế độ Góp ý (C)';$('note-mode').setAttribute('aria-pressed',String(on));if(on){tool('notes');api.state().playing&&$('play').click()}else closePop()}
$('note-mode').onclick=()=>setMode(!noteMode);
function renderNotes(){const rows=notes(),count=k=>rows.filter(n=>k==='all'||n.status===k).length;$('note-filters').replaceChildren(...[['all','Tất cả'],...STATES].map(([k,t])=>{const b=el('button',{type:'button',className:'chip-button',textContent:`${t} ${count(k)}`});b.setAttribute('aria-pressed',String(filter===k));b.onclick=()=>{filter=k;renderNotes()};return b}));
 const shown=rows.map((n,i)=>({...n,index:i+1})).filter(n=>filter==='all'||n.status===filter).sort((a,b)=>a.t-b.t);
 $('note-list').replaceChildren(...(shown.length?shown.map(n=>{const st=el('select',{},...STATES.map(([k,t])=>new Option(t,k)));st.value=n.status||'open';st.onchange=()=>saveNotes(notes().map(x=>x.id===n.id?{...x,status:st.value}:x));
  const jump=el('button',{type:'button',className:'note-time',textContent:`#${n.index} · ${tc(n.t)}`});jump.onclick=()=>{api.seek(n.t);focus=n.id;renderNotes();pins(n.t)};
  const drop=el('button',{type:'button',className:'icon-button',textContent:'✕',title:'Xóa góp ý'});drop.onclick=()=>saveNotes(notes().filter(x=>x.id!==n.id));
  return el('div',{className:'note-card '+(n.status||'open')+(focus===n.id?' focus':'')},el('div',{className:'note-head'},jump,st,drop),el('p',{textContent:n.text}))}):[el('div',{className:'note-empty'},el('div',{textContent:'◎'}),el('strong',{textContent:'Chưa có góp ý'}),el('p',{className:'helper',textContent:'Bấm C rồi bấm lên khung hình ở chỗ cần sửa.'}))]));
 const open=rows.filter(n=>n.status!=='done').length;if($('tool-notes'))$('tool-notes').textContent=open?`Góp ý ${open}`:'Góp ý'}
const layer=el('div',{id:'note-pins',className:'note-pins'});$('stage').append(layer);
function pins(t){const rows=notes();layer.replaceChildren(...rows.map((n,i)=>({n,i})).filter(({n})=>Math.abs(n.t-t)<=1.5||n.id===focus).map(({n,i})=>{const pin=el('button',{type:'button',className:'note-pin '+(n.status||'open'),textContent:String(i+1),title:n.text});Object.assign(pin.style,{left:(n.x/720*100)+'%',top:(n.y/1280*100)+'%'});pin.onclick=e=>{e.stopPropagation();focus=n.id;tool('notes');renderNotes()};pin.onpointerdown=e=>e.stopPropagation();return pin}))}
const pop=el('div',{id:'note-pop',className:'note-pop',hidden:true});pop.innerHTML='<textarea id="note-text" placeholder="Muốn sửa gì ở chỗ này? (Enter xuống dòng · Ctrl+Enter lưu)"></textarea><div class="result-actions"><button type="button" id="note-cancel" class="outline-action small-action">Hủy</button><button type="button" id="note-save" class="primary-action small-action">Lưu góp ý</button></div>';$('stage').append(pop);
let draft=null;
function closePop(){pop.hidden=true;draft=null}
$('stage').addEventListener('pointerdown',e=>{if(!noteMode||e.target.closest('#note-pop,.note-pin'))return;e.preventDefault();e.stopImmediatePropagation();const b=$('stage').getBoundingClientRect(),x=(e.clientX-b.x)/b.width,y=(e.clientY-b.y)/b.height;
 draft={x:Math.round(x*720),y:Math.round(y*1280),t:Math.round(api.state().clock*1000)/1000};pop.hidden=false;Object.assign(pop.style,{left:Math.min(58,x*100)+'%',top:Math.min(70,y*100)+'%'});$('note-text').value='';$('note-text').focus();pins(draft.t);
 const ghost=el('span',{className:'note-pin ghost',textContent:'+'});Object.assign(ghost.style,{left:x*100+'%',top:y*100+'%'});layer.append(ghost)},true);
$('note-cancel').onclick=()=>{closePop();pins(api.state().clock)};
$('note-save').onclick=()=>{const text=$('note-text').value.trim();if(!draft||!text){$('note-text').focus();return}const id='n'+Date.now().toString(36)+Math.random().toString(36).slice(2,6);saveNotes([...notes(),{id,t:draft.t,x:draft.x,y:draft.y,text:text.slice(0,1000),status:'open',created:new Date().toISOString()}]);focus=id;closePop();renderNotes();pins(api.state().clock)};
$('note-text').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();$('note-save').click()}else if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closePop();pins(api.state().clock)}});
document.addEventListener('keydown',e=>{if(view.hidden||e.ctrlKey||e.metaKey||e.altKey)return;const t=e.target;if(t.closest?.('textarea,select,input:not([type=checkbox]):not([type=range])'))return;if(e.key==='Escape'&&noteMode)setMode(false)});
document.addEventListener('note-focus',e=>{focus=e.detail;tool('notes');renderNotes();pins(api.state().clock)});
document.addEventListener('history-applied',()=>{renderNotes();pins(api.state().clock);stats()});
document.addEventListener('video-changed',()=>{focus='';renderNotes()});
renderNotes();clock(api.state().clock);stats();
})();
