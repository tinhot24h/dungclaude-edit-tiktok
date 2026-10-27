'use strict';
// Projects, design templates, media library, drag-and-drop import and batch export.
(()=>{
const design=window.studioApi,edit=window.editorState;
const panel=document.querySelector('.source-panel');
let projectId='',lastSaved='',selectedVideos=new Set(),autosave=true;
try{projectId=localStorage.getItem('review-project-id')||'';autosave=localStorage.getItem('review-autosave')!=='0'}catch{}
const remember=(k,v)=>{try{localStorage.setItem(k,v)}catch{}};
const json=(url,body)=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const time=iso=>{try{return new Date(iso).toLocaleString('vi-VN',{dateStyle:'short',timeStyle:'short'})}catch{return ''}};
function say(text){$('workspace-status').textContent=text}

// Left column tabs: source/export, media library, projects & templates.
const main=el('div',{id:'pane-source',className:'source-pane'});main.append(...[...panel.children]);
const library=el('div',{id:'pane-library',className:'source-pane',hidden:true});
const projects=el('div',{id:'pane-projects',className:'source-pane',hidden:true});
const tabs=el('div',{className:'source-tabs',role:'tablist'});
for(const[id,label]of [['source','Nguồn & xuất'],['library','Thư viện'],['projects','Dự án & mẫu']]){const b=el('button',{type:'button',id:'source-tab-'+id,textContent:label});b.setAttribute('role','tab');b.onclick=()=>show(id);tabs.append(b)}
function show(id){for(const name of ['source','library','projects']){$('pane-'+name).hidden=name!==id;$('source-tab-'+name).setAttribute('aria-selected',String(name===id))}if(id==='library')loadLibrary();if(id==='projects')loadProjects()}
panel.append(tabs,main,library,projects,el('p',{id:'workspace-status',className:'helper'}));panel.querySelector('#workspace-status').setAttribute('role','status');show('source');

// ---- Projects
projects.innerHTML=`<div class="panel-heading"><h2>Dự án</h2><span id="project-current"></span></div>
<div class="result-actions"><button type="button" id="project-save" class="primary-action">Lưu dự án · Ctrl+S</button><button type="button" id="project-new" class="outline-action">Dự án mới</button></div>
<label class="check-row"><input type="checkbox" id="project-autosave"> Tự lưu mỗi phút khi có thay đổi</label>
<label for="project-list">Dự án gần đây</label><select id="project-list" size="6"></select>
<div class="result-actions"><button type="button" id="project-open" class="outline-action">Mở</button><button type="button" id="project-delete" class="outline-action danger-action">Xóa</button></div>
<div class="result-actions"><button type="button" id="project-export" class="outline-action">Tải file .json</button><label class="outline-action file-button">Mở file .json<input type="file" id="project-import" accept="application/json,.json" hidden></label></div>
<p class="helper">Dự án lưu thiết kế, chữ, điểm cắt, mốc và lựa chọn audio. Video/MP3 vẫn nằm trong thư viện của ứng dụng, không chép vào file dự án.</p>
<hr><div class="panel-heading"><h2>Mẫu của tôi</h2></div>
<label for="template-list">Mẫu đã lưu</label><select id="template-list"><option value="">— Chọn mẫu —</option></select>
<div class="result-actions"><button type="button" id="template-apply" class="outline-action">Áp dụng mẫu</button><button type="button" id="template-save" class="outline-action">Lưu thiết kế thành mẫu</button><button type="button" id="template-delete" class="outline-action danger-action">Xóa mẫu</button></div>
<p class="helper">Mẫu giữ màu, khung, font, vị trí chữ và video, không giữ nội dung chữ hay media.</p>`;
$('project-autosave').checked=autosave;$('project-autosave').onchange=()=>{autosave=$('project-autosave').checked;remember('review-autosave',autosave?'1':'0')};
function data(){return {version:1,design:design.snapshot(),edit:edit.snapshot(),media:edit.media()}}
function current(){$('project-current').textContent=projectId?'Đang mở dự án đã lưu':'Chưa lưu'}
async function saveProject(quiet=false){const body=data(),text=JSON.stringify(body);try{const r=await json('/library/projects/save',{id:projectId||undefined,name:$('project-name').value.trim()||'Dự án review',data:body});projectId=r.id;lastSaved=text;remember('review-project-id',projectId);current();if(!quiet)say(`Đã lưu dự án "${r.name}" lúc ${time(r.updated_at)}.`);if(!projects.hidden)loadProjects()}catch(e){if(!quiet)say(e.message)}}
async function applyProject(d){if(!d||typeof d!=='object'||!d.design||!d.edit)throw Error('File dự án không đúng định dạng Review Studio.');design.apply(d.design);edit.apply(d.edit);const m=d.media||{};const notes=[];if(m.video_id)await edit.openVideo(m.video_id,false).catch(()=>notes.push('video gốc không còn trong thư viện'));await edit.useAudio(m.audio_asset_id||'').catch(()=>notes.push('MP3 giọng đọc không còn'));await edit.useMusic(m.music_asset_id||'').catch(()=>{});edit.apply(d.edit);window.appHistory?.reset();return notes}
async function openProject(id){try{const r=await request('/library/projects/'+id);const notes=await applyProject(r.data);projectId=r.id;lastSaved=JSON.stringify(data());remember('review-project-id',projectId);current();show('source');say(`Đã mở "${r.name}".`+(notes.length?' Lưu ý: '+notes.join(', ')+'.':''))}catch(e){say(e.message)}}
async function loadProjects(){try{const [p,t]=await Promise.all([request('/library/projects'),request('/library/templates')]);$('project-list').replaceChildren(...p.items.map(i=>new Option(`${i.name} · ${time(i.updated_at)}`,i.id)));if(!p.items.length)$('project-list').append(new Option('Chưa có dự án nào',''));const keep=$('template-list').value;$('template-list').replaceChildren(new Option('— Chọn mẫu —',''),...t.items.map(i=>new Option(i.name,i.id)));$('template-list').value=keep}catch(e){say(e.message)}}
$('project-save').onclick=()=>saveProject();
$('project-new').onclick=()=>{if(!confirm('Bắt đầu dự án mới? Dự án hiện tại vẫn giữ trong danh sách nếu đã lưu.'))return;projectId='';lastSaved='';remember('review-project-id','');$('project-name').value='Review-video';current();say('Dự án mới: chọn video ở tab Nguồn & xuất. Thiết kế hiện tại được giữ làm điểm bắt đầu.')};
$('project-open').onclick=()=>$('project-list').value&&openProject($('project-list').value);$('project-list').ondblclick=$('project-open').onclick;
$('project-delete').onclick=async()=>{const id=$('project-list').value;if(!id||!confirm('Xóa dự án đã lưu này? Video và MP3 trong thư viện không bị xóa.'))return;try{await request(`/library/projects/${id}/delete`,{method:'POST'});if(id===projectId){projectId='';remember('review-project-id','');current()}loadProjects();say('Đã xóa dự án.')}catch(e){say(e.message)}};
$('project-export').onclick=()=>{const blob=new Blob([JSON.stringify({app:'ReviewStudio',name:$('project-name').value,data:data()},null,1)],{type:'application/json'});const a=el('a',{href:URL.createObjectURL(blob),download:($('project-name').value||'du-an')+'.reviewstudio.json'});a.click();setTimeout(()=>URL.revokeObjectURL(a.href),2000)};
async function importFile(file){try{const raw=JSON.parse(await file.text());const notes=await applyProject(raw.data||raw);projectId='';if(raw.name)$('project-name').value=raw.name;await saveProject(true);show('source');say(`Đã mở file ${file.name} và lưu thành dự án mới.`+(notes.length?' Lưu ý: '+notes.join(', ')+'.':''))}catch(e){say(e instanceof SyntaxError?'File không phải JSON hợp lệ.':e.message)}}
$('project-import').onchange=()=>{const f=$('project-import').files[0];if(f)importFile(f);$('project-import').value=''};
$('template-save').onclick=async()=>{const name=prompt('Tên mẫu thiết kế:','Mẫu '+new Date().toLocaleDateString('vi-VN'));if(!name)return;try{await json('/library/templates/save',{name,data:{design:design.snapshot(false)}});loadProjects();say(`Đã lưu mẫu "${name}".`)}catch(e){say(e.message)}};
$('template-apply').onclick=async()=>{const id=$('template-list').value;if(!id)return;try{const r=await request('/library/templates/'+id);design.apply(r.data.design);window.appHistory?.checkpoint();say(`Đã áp dụng mẫu "${r.name}". Hoàn tác bằng Ctrl+Z.`)}catch(e){say(e.message)}};
$('template-delete').onclick=async()=>{const id=$('template-list').value;if(!id||!confirm('Xóa mẫu này?'))return;try{await request(`/library/templates/${id}/delete`,{method:'POST'});$('template-list').value='';loadProjects()}catch(e){say(e.message)}};
setInterval(()=>{if(!autosave||!edit.media().video_id)return;const text=JSON.stringify(data());if(text!==lastSaved)saveProject(true).then(()=>{$('save-indicator').textContent='Đã tự lưu dự án lúc '+new Date().toLocaleTimeString('vi-VN',{timeStyle:'short'})})},60000);
document.addEventListener('video-changed',()=>{if(!projectId)return;projectId='';lastSaved='';remember('review-project-id','');current();say('Video mới được tính là dự án mới; dự án cũ vẫn giữ trong tab Dự án & mẫu.')});
current();
window.workspace={saveProject:()=>saveProject(),openProject,importFile};

// ---- Media library
library.innerHTML=`<div class="panel-heading"><h2>Thư viện media</h2><button type="button" id="library-refresh" class="outline-action small-action">Làm mới</button></div>
<p class="helper">Kéo thả video, MP3, PNG hoặc file dự án .json vào cửa sổ để nhập.</p>
<h3 class="library-heading">Video</h3><div id="library-videos" class="media-grid"></div>
<div class="batch-box"><button type="button" id="batch-export" class="primary-action" disabled>Xuất hàng loạt 0 video</button><p class="helper">Áp dụng thiết kế hiện tại cho các video đã tích; mỗi video giữ nguyên độ dài và tiếng gốc. Video được xếp hàng và xuất lần lượt.</p><ol id="batch-list" class="batch-list"></ol></div>
<h3 class="library-heading">Âm thanh</h3><div id="library-audio" class="media-list"></div>
<h3 class="library-heading">Khung PNG</h3><div id="library-frames" class="media-grid frames"></div>`;
async function loadLibrary(){try{const [v,f]=await Promise.all([request('/media/videos'),request('/frames')]);await edit.reloadAssets();const current=edit.media();
 $('library-videos').replaceChildren(...v.videos.map(item=>{const card=el('div',{className:'media-card'+(item.id===current.video_id?' active':'')});const pick=el('input',{type:'checkbox',checked:selectedVideos.has(item.id),title:'Chọn để xuất hàng loạt'});pick.onchange=()=>{pick.checked?selectedVideos.add(item.id):selectedVideos.delete(item.id);batchLabel()};const use=el('button',{type:'button',className:'media-use',title:'Mở video này để chỉnh'},el('img',{src:item.thumb,alt:'',loading:'lazy'}),el('span',{textContent:item.name}),el('small',{textContent:`${item.duration.toFixed(1)}s · ${item.width}×${item.height}`}));use.onclick=async()=>{try{await edit.openVideo(item.id,true);window.appHistory?.checkpoint();show('source');say('Đã mở '+item.name+'.')}catch(e){say(e.message)}};card.append(use,pick);return card}));
 if(!v.videos.length)$('library-videos').append(el('p',{className:'helper',textContent:'Chưa có video. Chọn hoặc kéo thả video vào ứng dụng.'}));
 for(const id of [...selectedVideos])if(!v.videos.some(x=>x.id===id))selectedVideos.delete(id);batchLabel();
 $('library-audio').replaceChildren(...edit.assets().map(a=>{const row=el('div',{className:'media-row'},el('span',{textContent:`${a.name} · ${a.duration.toFixed(1)}s`}));const voice=el('button',{type:'button',className:'outline-action small-action',textContent:'Giọng đọc'});voice.onclick=async()=>{await edit.useAudio(a.asset_id);window.appHistory?.checkpoint();say('Đã dùng '+a.name+' làm giọng đọc.')};const bed=el('button',{type:'button',className:'outline-action small-action',textContent:'Nhạc nền'});bed.onclick=async()=>{await edit.useMusic(a.asset_id);window.appHistory?.checkpoint();say('Đã dùng '+a.name+' làm nhạc nền.')};row.append(voice,bed);return row}));
 if(!edit.assets().length)$('library-audio').append(el('p',{className:'helper',textContent:'Chưa có MP3. Nhập file hoặc tạo giọng ai33.'}));
 $('library-frames').replaceChildren(...f.frames.map(fr=>{const b=el('button',{type:'button',className:'media-frame',title:'Dùng khung PNG này'},el('img',{src:fr.url,alt:'Khung PNG',loading:'lazy'}));b.onclick=()=>{design.apply({frame_id:fr.id,frame_style:'custom'});window.appHistory?.checkpoint();say('Đã dùng khung PNG.')};return b}));
 if(!f.frames.length)$('library-frames').append(el('p',{className:'helper',textContent:'Chưa có khung PNG.'}))}catch(e){say(e.message)}}
$('library-refresh').onclick=loadLibrary;
function batchLabel(){$('batch-export').textContent=`Xuất hàng loạt ${selectedVideos.size} video`;$('batch-export').disabled=!selectedVideos.size}
$('batch-export').onclick=async()=>{let base;try{base=options()}catch(e){say(e.message);return}const ids=[...selectedVideos],videos=(await request('/media/videos')).videos;$('batch-list').replaceChildren();$('batch-export').disabled=true;
 const jobs=[];for(const id of ids){const item=videos.find(v=>v.id===id);if(!item)continue;const row=el('li',{textContent:item.name+' · đang gửi…'});$('batch-list').append(row);
  const opts={...base,id,video_start:0,video_end:0,video_cuts:[],audio_mode:'original',audio_asset_id:'',duration_policy:'video',project_name:item.name.replace(/\.[^.]+$/,'')};delete opts.preview_at;
  try{await json('/render',opts);jobs.push({id,row,name:item.name})}catch(e){row.textContent=`${item.name} · ${e.message}`}}
 while(jobs.some(j=>!j.done)){await new Promise(r=>setTimeout(r,1500));for(const j of jobs.filter(j=>!j.done)){try{const r=await request('/jobs/'+j.id);if(r.state==='done'){j.done=true;j.row.replaceChildren(el('a',{href:r.url+'?t='+Date.now(),download:(r.name||'video')+'.mp4',textContent:`${j.name} · xong ${r.duration.toFixed(1)}s ↓`}))}else if(r.state==='error'||r.state==='cancelled'){j.done=true;j.row.textContent=`${j.name} · ${r.error||'đã hủy'}`}else j.row.textContent=`${j.name} · ${r.state==='queued'?'đang chờ lượt':(r.progress||0)+'%'+(r.eta!=null?' · còn khoảng '+r.eta+'s':'')}`}catch(e){j.done=true;j.row.textContent=`${j.name} · ${e.message}`}}}
 batchLabel();say(`Xuất hàng loạt xong ${jobs.length} video.`);try{if(document.hidden&&window.Notification?.permission==='granted')new Notification('Review Studio',{body:`Đã xuất xong ${jobs.length} video.`})}catch{}};

// ---- Drag and drop from the file manager
const drop=el('div',{id:'drop-overlay',hidden:true},el('div',{textContent:'Thả video, MP3, khung PNG hoặc file dự án .json'}));document.body.append(drop);
let depth=0;
const files=e=>[...(e.dataTransfer?.items||[])].some(i=>i.kind==='file');
addEventListener('dragenter',e=>{if(!files(e))return;e.preventDefault();depth++;drop.hidden=false});
addEventListener('dragover',e=>{if(files(e))e.preventDefault()});
addEventListener('dragleave',()=>{depth=Math.max(0,depth-1);if(!depth)drop.hidden=true});
function feed(input,file){const t=new DataTransfer();t.items.add(file);input.files=t.files;input.dispatchEvent(new Event('change'))}
addEventListener('drop',async e=>{if(!files(e))return;e.preventDefault();depth=0;drop.hidden=true;const list=[...e.dataTransfer.files];if(!list.length)return;switchView('editor');
 const videos=list.filter(f=>f.type.startsWith('video/')||/\.(mp4|mov|m4v|webm|mkv)$/i.test(f.name)),audio=list.filter(f=>f.type.startsWith('audio/')||/\.(mp3|wav|m4a|flac|ogg)$/i.test(f.name)),frames=list.filter(f=>f.type==='image/png'),projectsFiles=list.filter(f=>/\.json$/i.test(f.name));
 if(projectsFiles[0])return importFile(projectsFiles[0]);
 if(frames[0])feed($('frame-file'),frames[0]);
 for(const f of audio.slice(0,1))feed($('audio-file'),f);
 for(const f of audio.slice(1)){say('Đang nhập '+f.name+'…');await request('/audio/upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(f.name)},body:f}).catch(err=>say(err.message))}
 if(videos[0]){show('source');feed($('file'),videos[0])}
 for(const f of videos.slice(1)){say('Đang tải '+f.name+' vào thư viện…');try{await request('/upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(f.name)},body:f})}catch(err){say(f.name+': '+err.message)}}
 if(videos.length>1||audio.length>1){say(`Đã nhập ${videos.length} video và ${audio.length} audio. Mở tab Thư viện để chọn hoặc xuất hàng loạt.`);if(audio.length>1)edit.reloadAssets()}
});
})();
