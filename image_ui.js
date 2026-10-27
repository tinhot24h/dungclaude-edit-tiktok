'use strict';
// Image / logo / sticker layers: drawn on the preview above the frame and below the text, dragged and resized
// directly on the frame, one row each on the timeline and their own properties tab. Stored in #image-layers.
(()=>{
const design=window.studioApi,api=window.editorTimeline;
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
let chosen='',clock=0,drag=null,meta=new Map();
const layers=()=>design.imageLayers(),find=uid=>layers().find(l=>l.uid===uid);
const uid=()=>'i'+Date.now().toString(36)+Math.random().toString(36).slice(2,6);
function save(rows,checkpoint=true){design.setImageLayers(rows);if(checkpoint)window.appHistory?.later(0)}
function update(id,values,checkpoint=true){save(layers().map(l=>l.uid===id?{...l,...values}:l),checkpoint)}

// ---- preview layer + selection box with 8 handles and a rotate handle
const holder=el('div',{id:'image-layer',className:'image-layer-host'});$('texts').before(holder);
const box=el('div',{id:'image-selection',hidden:true},el('span',{className:'image-selection-label'}));
for(const dir of ['n','s','e','w','ne','nw','se','sw']){const h=el('button',{type:'button',className:'image-handle handle-'+dir,ariaLabel:'Đổi kích thước ảnh'});h.dataset.dir=dir;box.append(h)}
box.append(el('button',{type:'button',className:'image-rotate',title:'Kéo để xoay ảnh (giữ Shift: bước 15°)',ariaLabel:'Xoay ảnh'}));
$('scene').append(box);
function visible(l){const end=l.end||Infinity;return clock>=l.start-1e-3&&clock<=end+1e-3}
function draw(){const rows=layers();for(const img of [...holder.children])if(!rows.some(l=>l.uid===img.dataset.uid))img.remove();
 rows.forEach((l,i)=>{let img=holder.querySelector(`[data-uid="${l.uid}"]`);if(!img){img=el('img',{className:'image-layer',alt:l.name||'Ảnh',draggable:false});img.dataset.uid=l.uid;img.onpointerdown=e=>{e.stopPropagation();e.preventDefault();select(l.uid);begin(e,'move')};holder.append(img)}
  if(img.dataset.src!==l.id){img.src='/images/'+l.id;img.dataset.src=l.id}
  Object.assign(img.style,{left:l.x+'px',top:l.y+'px',width:l.width+'px',height:l.height+'px',opacity:l.opacity/100,transform:`rotate(${l.rotation||0}deg)`,zIndex:i+1});
  img.classList.toggle('off-time',!visible(l));img.classList.toggle('chosen',l.uid===chosen)});
 outline();$('tab-image').hidden=!rows.length;if(chosen&&!find(chosen))deselect();fill()}
function outline(){const l=find(chosen);box.hidden=!l;if(!l)return;Object.assign(box.style,{left:l.x+'px',top:l.y+'px',width:l.width+'px',height:l.height+'px',transform:`rotate(${l.rotation||0}deg)`});box.querySelector('.image-selection-label').textContent=`ẢNH · ${Math.round(l.width)} × ${Math.round(l.height)} px${l.rotation?' · '+Math.round(l.rotation)+'°':''}`}
function select(id,fromTimeline=false){chosen=id;api.selectLayer('');$('drag-target').value='none';activate('image');$('settings-title').textContent='Thuộc tính · ẢNH';if(!fromTimeline)window.timelineActions?.markLayer('img:'+id);draw()}
function deselect(){if(!chosen)return;chosen='';box.hidden=true;for(const img of holder.children)img.classList.remove('chosen');fill()}
$('stage').addEventListener('pointerdown',e=>{if(!e.target.closest('.image-layer,#image-selection'))deselect()},true);

function coords(e){const b=$('stage').getBoundingClientRect();return {x:(e.clientX-b.x)/b.width*720,y:(e.clientY-b.y)/b.height*1280}}
function ratio(l){const m=meta.get(l.id);return m?m.width/m.height:l.width/Math.max(1,l.height)}
function begin(e,mode,dir=''){const l=find(chosen);if(!l)return;const c=coords(e);drag={mode,dir,x:c.x,y:c.y,l:{...l}};$('stage').setPointerCapture(e.pointerId)}
for(const h of box.querySelectorAll('.image-handle'))h.onpointerdown=e=>{e.stopPropagation();e.preventDefault();begin(e,'resize',h.dataset.dir)};
box.querySelector('.image-rotate').onpointerdown=e=>{e.stopPropagation();e.preventDefault();begin(e,'rotate')};
const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
$('stage').addEventListener('pointermove',e=>{if(!drag)return;e.stopImmediatePropagation();const c=coords(e),o=drag.l;let dx=c.x-drag.x,dy=c.y-drag.y,next={};
 if(drag.mode==='move'){if(!e.altKey&&window.snapLayer){const s=window.snapLayer(o.x+dx,o.y+dy,o.width,o.height);dx+=s.dx;dy+=s.dy}next={x:clamp(o.x+dx,-720,1440),y:clamp(o.y+dy,-1280,2560)}}
 else if(drag.mode==='rotate'){const cx=o.x+o.width/2,cy=o.y+o.height/2;let deg=Math.atan2(c.y-cy,c.x-cx)*180/Math.PI+90;if(deg>180)deg-=360;if(e.shiftKey)deg=Math.round(deg/15)*15;else if(Math.abs(deg)<3)deg=0;next={rotation:Math.round(deg*10)/10}}
 else{const d=drag.dir,lock=$('image-lock').checked!==e.shiftKey,r=ratio(o);let w=o.width,h=o.height;if(d.includes('e'))w=o.width+dx;if(d.includes('w'))w=o.width-dx;if(d.includes('s'))h=o.height+dy;if(d.includes('n'))h=o.height-dy;
  if(lock){if(d==='n'||d==='s')w=h*r;else if(d==='e'||d==='w')h=w/r;else{const k=Math.max(w/o.width,h/o.height);w=o.width*k;h=w/r}}w=clamp(w,8,2160);h=clamp(h,8,3840);
  let x=o.x,y=o.y;if(d.includes('w'))x=o.x+o.width-w;if(d.includes('n'))y=o.y+o.height-h;if(lock&&(d==='e'||d==='w'))y=o.y+(o.height-h)/2;if(lock&&(d==='n'||d==='s'))x=o.x+(o.width-w)/2;next={x,y,width:w,height:h}}
 for(const k of Object.keys(next))next[k]=Math.round(next[k]*10)/10;update(chosen,next,false)},true);
const end=()=>{if(!drag)return;drag=null;document.dispatchEvent(new Event('layer-moved'))};
$('stage').addEventListener('pointerup',end,true);$('stage').addEventListener('pointercancel',end,true);

// ---- properties tab
const sec=section('image','Ảnh');
sec.innerHTML=`<div class="image-head"><img id="image-thumb" alt=""><div><strong id="image-name">Chưa chọn ảnh</strong><small id="image-size" class="helper"></small></div></div>
<label for="image-pick">Lớp ảnh</label><select id="image-pick"></select>
<div class="group-label">VỊ TRÍ & KÍCH THƯỚC</div>
<div class="two-col"><div class="control"><label for="image-x">X · trái</label><div class="numeric-shell"><input id="image-x" type="number" min="-720" max="1440" step="1"><span class="unit">px</span></div></div><div class="control"><label for="image-y">Y · trên</label><div class="numeric-shell"><input id="image-y" type="number" min="-1280" max="2560" step="1"><span class="unit">px</span></div></div></div>
<div class="two-col"><div class="control"><label for="image-width">W · rộng</label><div class="numeric-shell"><input id="image-width" type="number" min="8" max="2160" step="1"><span class="unit">px</span></div></div><div class="control"><label for="image-height">H · cao</label><div class="numeric-shell"><input id="image-height" type="number" min="8" max="3840" step="1"><span class="unit">px</span></div></div></div>
<label class="check-row"><input type="checkbox" id="image-lock" checked> Giữ tỷ lệ ảnh khi kéo góc/cạnh (giữ Shift để tạm đổi)</label>
<div class="frame-tools" id="image-tools"></div>
<div class="two-col"><div class="control"><label for="image-rotation">Góc xoay</label><div class="numeric-shell"><input id="image-rotation" type="number" min="-180" max="180" step="1"><span class="unit">°</span></div></div><div class="control"><label for="image-opacity">Độ đục</label><div class="numeric-shell"><input id="image-opacity" type="number" min="0" max="100" step="1"><span class="unit">%</span></div></div></div>
<div class="group-label">THỜI GIAN HIỆN</div>
<div class="two-col"><div class="control"><label for="image-start">Bắt đầu (giây)</label><div class="numeric-shell"><input id="image-start" type="number" min="0" max="1800" step="0.1"><span class="unit">s</span></div></div><div class="control"><label for="image-end">Kết thúc · 0 = hết video</label><div class="numeric-shell"><input id="image-end" type="number" min="0" max="1800" step="0.1"><span class="unit">s</span></div></div></div>
<div class="result-actions"><button type="button" id="image-up" class="outline-action small-action" title="Đưa lên trên các ảnh khác">↑ Lên trên</button><button type="button" id="image-down" class="outline-action small-action" title="Đưa xuống dưới các ảnh khác">↓ Xuống dưới</button><button type="button" id="image-copy" class="outline-action small-action">Nhân bản</button><button type="button" id="image-remove" class="outline-action small-action danger-action">Xóa lớp ảnh</button></div>
<p class="helper">Bấm ảnh trên khung hình để chọn, kéo để di chuyển, kéo ô vuông ở góc/cạnh để đổi kích thước, kéo nút tròn phía trên để xoay. Ảnh nằm trên khung và dưới chữ; thanh ảnh trên timeline đổi được thời gian hiện.</p>`;
const tools=$('image-tools'),place=v=>{const l=find(chosen);if(l)update(chosen,v)};
for(const[text,title,fn]of [['⇤','Căn trái',l=>({x:0})],['↔','Căn giữa ngang',l=>({x:(720-l.width)/2})],['⇥','Căn phải',l=>({x:720-l.width})],['⤒','Căn trên',l=>({y:0})],['↕','Căn giữa dọc',l=>({y:(1280-l.height)/2})],['⤓','Căn dưới',l=>({y:1280-l.height})],
 ['Góc logo','Góc trên phải, rộng 160 px',l=>{const w=160,h=w/ratio(l);return {x:720-w-40,y:100,width:w,height:h}}],['Vừa chiều ngang','Rộng bằng khung hình, giữ tỷ lệ',l=>{const h=720/ratio(l);return {x:0,width:720,height:h,y:Math.min(l.y,1280-h)}}],['Tỷ lệ gốc','Chỉnh cao theo tỷ lệ ảnh gốc',l=>({height:l.width/ratio(l)})]]){
 const b=el('button',{type:'button',textContent:text,title,ariaLabel:title});b.onclick=()=>{const l=find(chosen);if(l)place(Object.fromEntries(Object.entries(fn(l)).map(([k,v])=>[k,Math.round(v)])))};tools.append(b)}
const FIELDS=['x','y','width','height','rotation','opacity','start','end'];
function fill(){const rows=layers(),l=find(chosen);$('image-pick').replaceChildren(...(rows.length?rows.map((r,i)=>new Option(`${i+1}. ${r.name||'Ảnh'}`,r.uid)):[new Option('Chưa có lớp ảnh · bấm ＋ trên ảnh ở kho Media','')]));$('image-pick').value=chosen;
 for(const f of FIELDS){const e=$('image-'+f);e.disabled=!l;if(l&&document.activeElement!==e)e.value=Math.round(l[f]*10)/10}
 for(const b of sec.querySelectorAll('button'))b.disabled=!l;$('image-thumb').src=l?'/images/'+l.id:'';$('image-thumb').hidden=!l;$('image-name').textContent=l?(l.name||'Ảnh'):'Chưa chọn ảnh';const m=l&&meta.get(l.id);$('image-size').textContent=m?`Ảnh gốc ${m.width} × ${m.height} px`:''}
$('image-pick').onchange=()=>$('image-pick').value&&select($('image-pick').value);
for(const f of FIELDS)$('image-'+f).addEventListener('input',()=>{const l=find(chosen),e=$('image-'+f);if(!l||!Number.isFinite(e.valueAsNumber))return;let v=clamp(e.valueAsNumber,Number(e.min),Number(e.max));const next={[f]:v};
 if($('image-lock').checked&&(f==='width'||f==='height')){const r=ratio(l);if(f==='width')next.height=Math.round(v/r*10)/10;else next.width=Math.round(v*r*10)/10}
 if(f==='end'&&v&&v<=l.start+.05)return;update(chosen,next,false)});
function move(step){const rows=layers(),i=rows.findIndex(l=>l.uid===chosen),j=i+step;if(i<0||j<0||j>=rows.length)return;[rows[i],rows[j]]=[rows[j],rows[i]];save(rows)}
$('image-up').onclick=()=>move(1);$('image-down').onclick=()=>move(-1);
$('image-copy').onclick=()=>{const l=find(chosen);if(!l)return;if(layers().length>=12){status('Tối đa 12 lớp ảnh.');return}const copy={...l,uid:uid(),x:l.x+30,y:l.y+30};save([...layers(),copy]);select(copy.uid)};
$('image-remove').onclick=()=>remove(chosen);
function status(text){const s=$('workspace-status');if(s)s.textContent=text;$('tl-hint').textContent=text}

// ---- add / remove (used by the media bin and the timeline)
async function info(id){if(meta.has(id))return meta.get(id);try{const d=await request('/images');for(const r of d.images)meta.set(r.id,r)}catch{}return meta.get(id)}
async function add(record){if(layers().length>=12){status('Tối đa 12 lớp ảnh. Xóa bớt một lớp để thêm.');return}const m=await info(record.id)||record,r=(m.width||1)/(m.height||1);let w=Math.min(360,m.width||360),h=w/r;if(h>640){h=640;w=h*r}
 const layer={uid:uid(),id:record.id,name:(record.name||m.name||'Ảnh').replace(/\.[^.]+$/,''),x:Math.round((720-w)/2),y:Math.round((1280-h)/2-120),width:Math.round(w),height:Math.round(h),opacity:100,rotation:0,start:0,end:0};
 save([...layers(),layer]);select(layer.uid);status(`Đã thêm ảnh "${layer.name}". Kéo trên khung hình để đặt vị trí; kéo thanh ảnh trên timeline để đổi thời gian hiện.`)}
function remove(id){const l=find(id);if(!l)return;save(layers().filter(x=>x.uid!==id));if(chosen===id)deselect();status(`Đã xóa lớp ảnh "${l.name||'Ảnh'}". Ctrl+Z để hoàn tác.`)}
function nudge(dx,dy){const l=find(chosen);if(!l)return false;update(chosen,{x:clamp(l.x+dx,-720,1440),y:clamp(l.y+dy,-1280,2560)});return true}
window.imageLayers={list:layers,add,remove,select:id=>select(id,true),chosen:()=>chosen,nudge,usedIds:()=>new Set(layers().map(l=>l.id)),
 update:(id,values)=>update(id,values,false),refreshMeta:()=>{meta.clear();return info('')}};

document.addEventListener('design-changed',draw);document.addEventListener('history-applied',draw);
document.addEventListener('timeline-clock',e=>{clock=e.detail;for(const img of holder.children){const l=find(img.dataset.uid);if(l)img.classList.toggle('off-time',!visible(l))}});
info('').then(draw);draw();
})();
