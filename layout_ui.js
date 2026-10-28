'use strict';
// Editor layout in the style of web editors such as TaoClip: vertical tool rail, contextual properties (only the
// tabs of the selected clip/layer, with a header naming it), speed chips, a one-row player transport with loop and
// preview volume, labelled timeline tools and V/A track ids.
(()=>{
const api=window.editorTimeline,edit=window.editorState;
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const store=(k,v)=>{try{localStorage.setItem(k,v)}catch{}},load=k=>{try{return localStorage.getItem(k)}catch{return null}};

// ---- tool rail (left edge) with icons; "Ảnh" opens the media bin filtered to images/logos
const rail=document.querySelector('.tool-chips'),panel=document.querySelector('.source-panel');
panel.classList.add('with-rail');rail.classList.add('tool-rail');
const ICONS={media:'🎞',sound:'♪',text:'T',export:'⇪'};
for(const b of rail.children){const id=b.id.slice(5);b.innerHTML='';b.append(el('span',{className:'rail-icon',textContent:ICONS[id]||'•'}),el('span',{className:'rail-label',textContent:{media:'Media',sound:'Âm thanh',text:'Văn bản',export:'Xuất'}[id]||id}))}
const logo=el('button',{type:'button',id:'tool-image',role:'tab'},el('span',{className:'rail-icon',textContent:'🖼'}),el('span',{className:'rail-label',textContent:'Ảnh/Logo'}));
logo.onclick=()=>{window.studioTool('media');document.querySelector('.bin-filters [data-filter=image]')?.click();for(const b of rail.children)b.setAttribute('aria-selected',String(b===logo))};
$('tool-text').after(logo);

// ---- contextual properties: header + only the tabs of what is selected
const head=el('div',{className:'ctx-head',id:'ctx-head'},el('span',{className:'ctx-icon'}),el('div',{className:'ctx-text'},el('strong'),el('small')),el('button',{type:'button',className:'ctx-back',textContent:'Thiết kế chung',title:'Về các lớp thiết kế: nền, khung, chữ, video'}));
$('tabs').before(head);
const LABEL=k=>k==='title'?'Tiêu đề':k==='body'?'Nội dung':'Chữ '+k.slice(4);
const GROUPS={design:{icon:'🎨',tabs:[['background','Nền'],['frame','Khung'],['title','Tiêu đề'],['body','Nội dung'],['video','Video']],name:()=>'Thiết kế video',sub:()=>'Nền · khung · chữ · vị trí video'},
 video:{icon:'🎬',tabs:[['clip-video','✂ Cắt & tốc độ'],['video','▭ Khung hình']],name:()=>edit.current()?.name||'Video',sub:()=>'Clip chính · V1'},
 audio:{icon:'🎙',tabs:[['clip-audio','Giọng đọc']],name:()=>api.state().audio?.name||'Giọng đọc',sub:()=>'Âm thanh · A1'},
 music:{icon:'♪',tabs:[['clip-music','Nhạc nền']],name:()=>api.state().music?.name||'Nhạc nền',sub:()=>'Âm thanh · A2'},
 image:{icon:'🖼',tabs:[['image','Ảnh']],name:()=>window.imageLayers?.list().find(l=>l.uid===window.imageLayers.chosen())?.name||'Ảnh',sub:()=>'Lớp ảnh / logo'},
 text:{icon:'T',tabs:[],name:k=>LABEL(k),sub:k=>($(k)?.value||'').replace(/\s+/g,' ').slice(0,60)||'Lớp chữ'}};
let group='design',textKey='';
function groupOf(id){if(id==='clip-video'||(id==='video'&&group==='video'))return 'video';if(id==='clip-audio')return 'audio';if(id==='clip-music')return 'music';if(id==='image')return 'image';
 if((window.TEXT_KEYS||[]).includes(id))return group==='design'&&(id==='title'||id==='body')&&!picking?'design':'text';return 'design'}
let picking=false;
function context(id){group=groupOf(id);if(group==='text')textKey=id;const g=GROUPS[group],tabs=group==='text'?[[id,'Chữ & kiểu']]:g.tabs;
 for(const b of $('tabs').querySelectorAll('[role=tab]')){const key=b.id.slice(4),hit=tabs.find(t=>t[0]===key);if(hit&&!b.dataset.label)b.dataset.label=b.textContent;b.hidden=!hit;if(hit){b.textContent=hit[1];b.style.order=tabs.indexOf(hit)}}
 head.querySelector('.ctx-icon').textContent=g.icon;head.querySelector('strong').textContent=g.name(textKey);head.querySelector('small').textContent=g.sub(textKey);head.querySelector('.ctx-back').hidden=group==='design';
 $('settings-title').textContent='Thuộc tính';$('tabs').dataset.group=group}
const base=window.activate;window.activate=id=>{base(id);context(id)};
head.querySelector('.ctx-back').onclick=()=>{group='design';window.activate('background');for(const id of ['tl-video','tl-audio','tl-music'])$(id)?.classList.remove('picked')};
// selecting a text layer on the frame or timeline opens it as its own context, a design tab click keeps the design group
const select=api.selectLayer;api.selectLayer=k=>{picking=true;try{select(k)}finally{picking=false}};
document.addEventListener('design-changed',()=>context(group==='text'?textKey:document.querySelector('#tabs [aria-selected=true]')?.id.slice(4)||'background'));
document.addEventListener('timeline-select',e=>setTimeout(()=>context('clip-'+e.detail)));
context(document.querySelector('#tabs [aria-selected=true]')?.id.slice(4)||'background');

// ---- speed chips for the whole video track (pieces keep their own speed in "Tốc độ đoạn đang chọn")
const speedRow=el('div',{className:'speed-chips',id:'track-speed-chips'}),length=el('span',{className:'speed-length'});
for(const k of [.5,1,1.5,2,4]){const b=el('button',{type:'button',className:'chip-button',textContent:k+'×'});b.dataset.speed=k;b.onclick=()=>{$('video-speed').value=k;$('video-speed').dispatchEvent(new Event('input',{bubbles:true}));window.appHistory?.checkpoint()};speedRow.append(b)}
speedRow.append(length);$('video-speed').closest('.edit-grid')?.after(speedRow);
function speeds(){const v=Number($('video-speed').value)||1,p=api.state().plan;for(const b of speedRow.querySelectorAll('button'))b.setAttribute('aria-pressed',String(Math.abs(Number(b.dataset.speed)-v)<1e-3));const t=p?.vd||0;length.textContent=`Dài ${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}.${String(Math.floor(t%1*100)).padStart(2,'0')}`}
document.addEventListener('timeline-refresh',speeds);speeds();

// ---- one-row transport: loop + preview volume next to the play buttons
const loop=el('button',{type:'button',id:'tp-loop',title:'Phát lặp lại',textContent:'⟲'});loop.setAttribute('aria-pressed','false');$('tp-next').after(loop);
loop.onclick=()=>{window.editorPlayback.loop=!window.editorPlayback.loop;loop.setAttribute('aria-pressed',String(window.editorPlayback.loop));store('review-loop',window.editorPlayback.loop?'1':'0')};
if(load('review-loop')==='1')loop.click();
const vol=el('input',{type:'range',id:'tp-volume',min:0,max:100,step:1,title:'Âm lượng xem trước (không ảnh hưởng bản xuất)',ariaLabel:'Âm lượng xem trước'});
const volWrap=el('label',{className:'tp-volume'},el('span',{textContent:'🔊'}),vol);$('tp-meter').before(volWrap);
vol.value=Number(load('review-preview-volume')??100);const setVol=()=>{window.editorPlayback.volume=Number(vol.value)/100;volWrap.firstChild.textContent=Number(vol.value)?'🔊':'🔇';window.editorApplyGain?.();store('review-preview-volume',vol.value)};vol.oninput=setVol;setVol();
document.querySelector('.transport')?.classList.add('compact');

// ---- labelled timeline tools and track ids
$('tl-split').textContent='✂ Tách';$('tl-split').classList.add('tl-text');
const magnet=$('tl-magnet'),snapText=()=>{magnet.textContent='Snap: '+($('tl-snap').checked?'bật':'tắt');magnet.classList.toggle('on',$('tl-snap').checked)};magnet.classList.add('tl-text');magnet.addEventListener('click',()=>setTimeout(snapText));snapText();
$('tl-fit').textContent='Vừa khung';$('tl-fit').classList.add('tl-text');$('tl-add-text').textContent='T+ Chữ';$('tl-add-text').classList.add('tl-text');
for(const[k,id]of [['video','V1'],['audio','A1'],['music','A2']]){const strong=document.querySelector(`.tl-head[data-track=${k}] strong`);strong?.prepend(el('span',{className:'track-id',textContent:id}))}

// ---- undo/redo in the project bar
const undo=el('button',{type:'button',className:'pb-icon',title:'Hoàn tác (Ctrl+Z)',textContent:'↶'}),redo=el('button',{type:'button',className:'pb-icon',title:'Làm lại (Ctrl+Shift+Z)',textContent:'↷'});
undo.onclick=()=>window.appHistory?.undo();redo.onclick=()=>window.appHistory?.redo();$('pb-save').after(undo,redo);
const sync=()=>{undo.disabled=$('tl-undo').disabled;redo.disabled=$('tl-redo').disabled};new MutationObserver(sync).observe($('tl-undo'),{attributes:true});new MutationObserver(sync).observe($('tl-redo'),{attributes:true});sync();
})();
