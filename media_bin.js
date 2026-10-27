'use strict';
// Media bin: grid of imported videos, audio and PNG frames with thumbnails/waveforms,
// "Đã thêm" badges, + to add, delete, search/filter and drag-and-drop onto timeline tracks.
(()=>{
const edit=window.editorState,design=window.studioApi,pane=$('pane-media');
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const time=t=>{t=Math.round(t||0);return `${String(Math.floor(t/60)).padStart(2,'0')}:${String(t%60).padStart(2,'0')}`};
let items=[],filter='all',peaks=new Map(),waiting=new Set(),uploads=[];

// ---- layout: toolbar, filters, grid; the old upload box stays hidden but keeps working for drag-and-drop
const picker=el('input',{type:'file',multiple:true,accept:'video/*,audio/*,image/png',hidden:true});
const bar=el('div',{className:'bin-bar'},el('button',{type:'button',id:'bin-import',className:'bin-import',textContent:'＋ Nhập'}),el('input',{id:'bin-search',type:'search',placeholder:'Tìm kiếm tệp phương tiện',maxLength:100}),picker);
const chips=el('div',{className:'bin-filters'});for(const[k,t]of [['all','Tất cả'],['video','Video'],['audio','Âm thanh'],['frame','Khung PNG']]){const b=el('button',{type:'button',className:'chip-button',textContent:t});b.dataset.filter=k;b.onclick=()=>{filter=k;render()};chips.append(b)}
const grid=el('div',{id:'bin-grid',className:'bin-grid'});
const hint=el('p',{className:'helper',textContent:'Bấm ＋ hoặc kéo thẻ xuống track trên timeline để dùng. Có thể kéo file từ thư mục máy tính thả thẳng vào đây hoặc vào timeline.'});
pane.querySelector('.pane-title').after(bar,chips,grid,hint);
pane.querySelector('.upload-zone')?.classList.add('bin-legacy');pane.querySelector('label[for=file]')?.classList.add('bin-legacy');
$('bin-import').onclick=()=>picker.click();
picker.onchange=()=>{importFiles([...picker.files]);picker.value=''};
$('bin-search').oninput=()=>render();

// ---- data
async function load(){try{const [v,f]=await Promise.all([request('/media/videos'),request('/frames'),edit.reloadAssets()]);
 items=[...v.videos.map(x=>({kind:'video',id:x.id,name:x.name,duration:x.duration,thumb:x.thumb,width:x.width,height:x.height,stamp:x.uploaded*1000})),
  ...edit.assets().map(a=>({kind:'audio',id:a.asset_id,name:a.name,duration:a.duration,url:a.url,source:a.source,stamp:Date.parse(a.created_at)||0})),
  ...f.frames.map((x,i)=>({kind:'frame',id:x.id,name:'Khung PNG',url:x.url,stamp:-i}))].sort((a,b)=>b.stamp-a.stamp);render()}catch(e){hint.textContent=e.message}}
function used(item){const m=edit.media();if(item.kind==='video')return m.video_id===item.id?'Đã thêm':'';if(item.kind==='audio')return m.audio_asset_id===item.id?'Giọng đọc':m.music_asset_id===item.id?'Nhạc nền':'';return design.snapshot(false).frame_style==='custom'&&design.snapshot(false).frame_id===item.id?'Đã thêm':''}

// ---- waveform thumbnails (local analysis, one at a time)
async function wave(item){if(peaks.has(item.id)||waiting.has(item.id))return;waiting.add(item.id);try{const d=await request('/media/analysis/audio/'+item.id);peaks.set(item.id,d.peaks||[])}catch{peaks.set(item.id,[])}finally{waiting.delete(item.id);const svg=grid.querySelector(`[data-id="${item.id}"] svg`);if(svg)drawWave(svg,peaks.get(item.id))}}
function drawWave(svg,rows){const n=60,step=Math.max(1,Math.floor(rows.length/n)),bars=[];for(let i=0;i<n;i++){const slice=rows.slice(i*step,(i+1)*step);bars.push(slice.length?Math.max(...slice):0)}const top=Math.max(.01,...bars);svg.setAttribute('viewBox',`0 0 ${n*2} 40`);svg.innerHTML=bars.map((v,i)=>`<rect x="${i*2}" y="${20-Math.max(1,v/top*19)}" width="1.3" height="${Math.max(2,v/top*38)}"/>`).join('')}

// ---- cards
function render(){const q=$('bin-search').value.trim().toLocaleLowerCase();for(const b of chips.children)b.setAttribute('aria-pressed',String(b.dataset.filter===filter));
 const list=items.filter(i=>(filter==='all'||i.kind===filter)&&(!q||i.name.toLocaleLowerCase().includes(q)));
 grid.replaceChildren(...uploads.map(u=>el('div',{className:'bin-card uploading'},el('div',{className:'bin-thumb'},el('div',{className:'bin-progress'},el('i',{style:`width:${u.progress}%`})),el('span',{className:'bin-duration',textContent:u.progress+'%'})),el('div',{className:'bin-name',textContent:u.name}))),...list.map(card));
 if(!list.length&&!uploads.length)grid.append(el('div',{className:'bin-empty'},el('strong',{textContent:items.length?'Không có tệp khớp bộ lọc':'Chưa có tệp nào'}),el('span',{textContent:'Bấm ＋ Nhập hoặc kéo file vào đây.'})))}
function card(item){const tag=used(item),box=el('div',{className:'bin-card '+item.kind+(tag?' used':''),draggable:true,title:item.name});box.dataset.id=item.id;box.dataset.kind=item.kind;
 const thumb=el('div',{className:'bin-thumb'});
 if(item.kind==='video')thumb.append(el('img',{src:item.thumb,alt:'',loading:'lazy',draggable:false}));
 else if(item.kind==='frame')thumb.append(el('img',{src:item.url,alt:'',loading:'lazy',draggable:false,className:'frame-img'}));
 else{const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('preserveAspectRatio','none');thumb.append(svg);if(peaks.has(item.id))drawWave(svg,peaks.get(item.id));else wave(item)}
 if(tag)thumb.append(el('span',{className:'bin-badge',textContent:tag}));if(item.duration)thumb.append(el('span',{className:'bin-duration',textContent:time(item.duration)}));
 const add=el('button',{type:'button',className:'bin-add',textContent:'+',title:item.kind==='audio'?'Thêm làm giọng đọc':item.kind==='video'?'Thêm vào timeline':'Dùng làm khung'});add.onclick=e=>{e.stopPropagation();use(item,'audio')};thumb.append(add);
 if(item.kind==='audio'){const bed=el('button',{type:'button',className:'bin-add music',textContent:'♪',title:'Thêm làm nhạc nền'});bed.onclick=e=>{e.stopPropagation();use(item,'music')};thumb.append(bed)}
 if(item.kind!=='frame'){const drop=el('button',{type:'button',className:'bin-del',textContent:'🗑',title:'Xóa khỏi kho media'});drop.onclick=e=>{e.stopPropagation();remove(item)};thumb.append(drop)}
 box.append(thumb,el('div',{className:'bin-name',textContent:item.name}));
 box.ondblclick=()=>use(item,'audio');
 box.ondragstart=e=>{e.dataTransfer.setData('application/x-review-media',JSON.stringify({kind:item.kind,id:item.id}));e.dataTransfer.effectAllowed='copy';document.body.classList.add('dragging-media')};
 box.ondragend=()=>document.body.classList.remove('dragging-media');
 return box}

// ---- actions
async function use(item,lane){try{if(item.kind==='video'){await edit.openVideo(item.id,true);say(`Đã thêm ${item.name} vào track video.`)}
 else if(item.kind==='audio'){if(lane==='music'){await edit.useMusic(item.id);say(`Đã thêm ${item.name} vào track nhạc nền.`)}else{await edit.useAudio(item.id);if($('audio-mode').value==='original'){$('audio-mode').value='replace';$('audio-mode').dispatchEvent(new Event('input',{bubbles:true}))}say(`Đã thêm ${item.name} vào track giọng đọc.`)}}
 else{design.apply({frame_id:item.id,frame_style:'custom'});say('Đã dùng khung PNG.')}
 setTimeout(()=>window.appHistory?.checkpoint(),200);render()}catch(e){say(e.message)}}
async function remove(item){const tag=used(item);if(!confirm(`Xóa "${item.name}" khỏi kho media?${tag?' Tệp đang được dùng trên timeline sẽ bị bỏ ra.':''}${item.kind==='video'?' Video đã xuất của tệp này cũng bị xóa khỏi thư mục ứng dụng (bản đã lưu ra thư mục của bạn vẫn giữ).':''}`))return;
 try{if(item.kind==='video'){if(edit.media().video_id===item.id)edit.clearVideo();await request(`/media/video/${item.id}/delete`,{method:'POST'})}else{if(tag==='Giọng đọc')await edit.useAudio('');if(tag==='Nhạc nền')await edit.useMusic('');await request(`/audio/${item.id}/delete`,{method:'POST'})}
  say(`Đã xóa ${item.name}.`);document.dispatchEvent(new Event('audio-created'));load()}catch(e){say(e.message)}}
function say(text){$('workspace-status').textContent=text}

// ---- import with progress (XHR gives upload progress for big videos)
function send(url,file,u){return new Promise((resolve,reject)=>{const x=new XMLHttpRequest();x.open('POST',url);x.setRequestHeader('X-Filename',encodeURIComponent(file.name));x.upload.onprogress=e=>{if(e.lengthComputable){u.progress=Math.round(e.loaded/e.total*95);render()}};
 x.onload=()=>{let d={};try{d=JSON.parse(x.responseText)}catch{}x.status<300?resolve(d):reject(Error(d.error||'Nhập tệp thất bại.'))};x.onerror=()=>reject(Error('Mất kết nối khi nhập tệp.'));x.send(file)})}
async function importFiles(files,lane){const done=[];for(const file of files){const kind=file.type.startsWith('video/')||/\.(mp4|mov|m4v|webm|mkv)$/i.test(file.name)?'video':file.type.startsWith('audio/')||/\.(mp3|wav|m4a|flac|ogg)$/i.test(file.name)?'audio':file.type==='image/png'?'frame':'';
  if(!kind){say(file.name+': không phải video, audio hoặc PNG.');continue}
  const u={name:file.name,progress:0};uploads.push(u);render();
  try{const d=await send(kind==='video'?'/upload':kind==='audio'?'/audio/upload':'/frame-upload',file,u);done.push({kind,id:kind==='audio'?d.asset_id:d.id,name:d.name||file.name})}catch(e){say(file.name+': '+e.message)}finally{uploads=uploads.filter(x=>x!==u);render()}}
 await load();if(done.length)say(`Đã nhập ${done.length} tệp vào kho media.`);if(lane&&done[0])use(items.find(i=>i.id===done[0].id)||done[0],lane);document.dispatchEvent(new Event('audio-created'));return done}
window.mediaBin={importFiles,reload:load};

// ---- drop OS files on the bin
pane.addEventListener('dragover',e=>{if([...e.dataTransfer.types].includes('Files')){e.preventDefault();pane.classList.add('drop-target')}});
pane.addEventListener('dragleave',e=>{if(!pane.contains(e.relatedTarget))pane.classList.remove('drop-target')});
pane.addEventListener('drop',e=>{if(![...e.dataTransfer.types].includes('Files'))return;e.preventDefault();e.stopPropagation();pane.classList.remove('drop-target');$('drop-overlay').hidden=true;importFiles([...e.dataTransfer.files])});

// ---- drop bin cards or OS files on a timeline track
const canvas=$('tl-canvas'),LANES=['video','audio','music'];
function lane(e){const row=document.elementFromPoint(e.clientX,e.clientY)?.closest('.tl-lane');const all=[...canvas.querySelectorAll('.tl-lane')];return row?LANES[all.indexOf(row)]:null}
function mark(name){for(const[i,row]of [...canvas.querySelectorAll('.tl-lane')].entries())row.classList.toggle('drop-lane',LANES[i]===name)}
canvas.addEventListener('dragover',e=>{const types=[...e.dataTransfer.types];if(!types.includes('application/x-review-media')&&!types.includes('Files'))return;e.preventDefault();e.dataTransfer.dropEffect='copy';mark(lane(e))});
canvas.addEventListener('dragleave',e=>{if(!canvas.contains(e.relatedTarget))mark(null)});
canvas.addEventListener('drop',e=>{const target=lane(e);mark(null);const raw=e.dataTransfer.getData('application/x-review-media');if(!raw&&![...e.dataTransfer.types].includes('Files'))return;e.preventDefault();e.stopPropagation();$('drop-overlay').hidden=true;document.body.classList.remove('dragging-media');
 if(raw){const ref=JSON.parse(raw),item=items.find(i=>i.id===ref.id&&i.kind===ref.kind);if(!item)return;
  if(item.kind==='video'&&target&&target!=='video')return say('Video chỉ thả được vào track video.');if(item.kind==='audio'&&target==='video')return say('MP3 thả vào track giọng đọc hoặc nhạc nền.');
  return use(item,target==='music'?'music':'audio')}
 const files=[...e.dataTransfer.files];importFiles(files,target==='music'?'music':target==='audio'?'audio':files.some(f=>f.type.startsWith('video/'))?'video':'audio')});

for(const name of ['audio-created','video-changed','history-applied'])document.addEventListener(name,()=>setTimeout(load,300));
let last='';document.addEventListener('timeline-refresh',()=>{const m=JSON.stringify(edit.media());if(m!==last){last=m;render()}});
load();
})();
