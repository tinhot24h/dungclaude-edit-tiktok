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

// ---- source video: align on the 720×1280 frame, fill/fit presets, zoom and rotation shortcuts (Khung hình tab)
{const sec=$('section-video'),N=id=>Number($(id).value)||0,design=window.studioApi;
 const set=values=>{for(const[k,v]of Object.entries(values)){const e=$(k);if(!e)continue;e.value=typeof v==='number'?Math.round(Math.max(Number(e.min||-1e9),Math.min(Number(e.max||1e9),v))*10)/10:v}design.schedule();window.appHistory?.checkpoint()};
 // what is drawn: W×H scaled by zoom around the box centre; aligning moves the box so the drawn video touches the edge
 const shown=()=>{const z=N('video_zoom')/100||1,w=N('video_width'),h=N('video_height');return {z,w,h,dw:w*z,dh:h*z,ox:w*(1-z)/2,oy:h*(1-z)/2}};
 const source=()=>{const v=edit.current();return v&&v.width&&v.height?v.width/v.height:9/16};
 const group=(title,...buttons)=>el('div',{className:'video-tools'},el('div',{className:'group-label',textContent:title}),el('div',{className:'frame-tools'},...buttons));
 const btn=(text,title,fn)=>{const b=el('button',{type:'button',textContent:text,title,ariaLabel:title});b.onclick=fn;return b};
 const align=group('CĂN CHỈNH TRÊN KHUNG HÌNH',
  btn('⇤','Căn trái',()=>{const s=shown();set({video_x:-s.ox})}),btn('↔','Căn giữa ngang',()=>{const s=shown();set({video_x:(720-s.dw)/2-s.ox})}),btn('⇥','Căn phải',()=>{const s=shown();set({video_x:720-s.dw-s.ox})}),
  btn('⤒','Căn trên',()=>{const s=shown();set({video_y:-s.oy})}),btn('↕','Căn giữa dọc',()=>{const s=shown();set({video_y:(1280-s.dh)/2-s.oy})}),btn('⤓','Căn dưới',()=>{const s=shown();set({video_y:1280-s.dh-s.oy})}),
  btn('⊕ Giữa khung','Đặt video vào chính giữa khung hình',()=>{const s=shown();set({video_x:(720-s.dw)/2-s.ox,video_y:(1280-s.dh)/2-s.oy})}));
 const fit=group('KÍCH THƯỚC NHANH',
  btn('Lấp đầy 9:16','Phủ kín khung 720×1280, cắt phần thừa',()=>{$('video-lock').checked=true;set({video_x:0,video_y:0,video_width:720,video_height:1280,video_zoom:100,video_fit:'cover'})}),
  btn('Giữ toàn bộ hình','Hiện đủ khung hình gốc, viền trống nếu khác tỷ lệ',()=>set({video_x:0,video_y:0,video_width:720,video_height:1280,video_zoom:100,video_fit:'contain'})),
  btn('Vừa chiều ngang','Rộng bằng khung hình theo đúng tỷ lệ video gốc, đặt giữa dọc',()=>{$('video-lock').checked=false;const h=Math.round(720/source());set({video_width:720,video_height:Math.min(3840,Math.max(320,h)),video_x:0,video_y:(1280-h)/2,video_zoom:100,video_fit:'cover'})}),
  btn('Vừa chiều dọc','Cao bằng khung hình theo đúng tỷ lệ video gốc, đặt giữa ngang',()=>{$('video-lock').checked=false;const w=Math.round(1280*source());set({video_width:Math.min(2160,Math.max(180,w)),video_height:1280,video_x:(720-w)/2,video_y:0,video_zoom:100,video_fit:'cover'})}));
 const zoom=group('ZOOM',...[100,110,125,150,200].map(z=>btn(z+'%','Zoom '+z+'% quanh tâm video',()=>set({video_zoom:z}))));
 const rot=el('div',{className:'video-tools'},el('div',{className:'group-label',textContent:'XOAY'}));
 const slider=el('input',{type:'range',min:-180,max:180,step:1,id:'video-rotation-range',ariaLabel:'Góc xoay'});slider.oninput=()=>{$('video_rotation').value=slider.value;design.schedule()};slider.onchange=()=>window.appHistory?.checkpoint();
 const turn=d=>{let v=N('video_rotation')+d;while(v>180)v-=360;while(v<-180)v+=360;set({video_rotation:v})};
 rot.append(el('div',{className:'range-row'},slider),el('div',{className:'frame-tools'},btn('↺ 90°','Xoay trái 90°',()=>turn(-90)),btn('↻ 90°','Xoay phải 90°',()=>turn(90)),btn('180°','Xoay 180°',()=>turn(180)),btn('0°','Bỏ xoay',()=>set({video_rotation:0})),
  btn('⇋ Lật ngang','Lật ngang (soi gương)',()=>{const f=$('video_flip').value;set({video_flip:f==='h'?'none':f==='v'?'hv':f==='hv'?'v':'h'})}),btn('⇵ Lật dọc','Lật dọc',()=>{const f=$('video_flip').value;set({video_flip:f==='v'?'none':f==='h'?'hv':f==='hv'?'h':'v'})})));
 const at=$('video_zoom').closest('.control');at.before(align,fit,zoom);$('video_rotation').closest('.control').after(rot);
 const syncRot=()=>{slider.value=N('video_rotation')};document.addEventListener('design-changed',syncRot);syncRot()}

// ---- MP3 tracks: speed chips + slider and volume slider + quick levels (voice A1, music A2)
function audioControls(sectionId,speedId,volumeId,speeds,anchor){const sec=$(sectionId);if(!sec||!$(speedId)||!$(volumeId))return;
 const fire=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const box=el('div',{className:'audio-tools'});
 const sp=el('input',{type:'range',min:.5,max:2,step:.05,ariaLabel:'Tốc độ'}),spOut=el('output'),vol=el('input',{type:'range',min:0,max:300,step:1,ariaLabel:'Âm lượng'}),volOut=el('output');
 sp.oninput=()=>fire(speedId,sp.value);vol.oninput=()=>fire(volumeId,vol.value);for(const e of [sp,vol])e.onchange=()=>window.appHistory?.checkpoint();
 const chips=(values,id,suffix)=>el('div',{className:'speed-chips'},...values.map(v=>{const b=el('button',{type:'button',className:'chip-button',textContent:(v===0&&suffix==='%')?'Tắt':v+suffix});b.dataset.value=v;b.onclick=()=>{fire(id,v);window.appHistory?.checkpoint()};return b}));
 const speedChips=chips(speeds,speedId,'×'),volChips=chips([0,50,100,150,200],volumeId,'%');
 box.append(el('div',{className:'group-label',textContent:'TỐC ĐỘ'}),el('div',{className:'range-row'},sp,spOut),speedChips,el('div',{className:'group-label',textContent:'ÂM LƯỢNG'}),el('div',{className:'range-row'},vol,volOut),volChips);
 (anchor?.()||sec.querySelector('.group-label'))?.before(box);
 const draw=()=>{const k=Number($(speedId).value)||1,v=Number($(volumeId).value)||0;sp.value=k;vol.value=v;spOut.textContent=k.toFixed(2)+'×';volOut.textContent=v+'%';
  for(const b of speedChips.children)b.setAttribute('aria-pressed',String(Math.abs(Number(b.dataset.value)-k)<1e-3));for(const b of volChips.children)b.setAttribute('aria-pressed',String(Number(b.dataset.value)===v))};
 for(const id of [speedId,volumeId])$(id).addEventListener('input',draw);document.addEventListener('timeline-refresh',draw);document.addEventListener('history-applied',draw);draw()}
audioControls('section-clip-audio','audio-speed','audio-volume',[.75,.9,1,1.1,1.25,1.5]);
audioControls('section-clip-music','music-speed','music-volume',[.75,.9,1,1.1,1.25,1.5],()=>$('music-select')?.nextElementSibling);

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
