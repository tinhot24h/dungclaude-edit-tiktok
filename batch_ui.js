'use strict';
// Export tool, in working order: ① export settings (badge) → ② saved configurations (design + audio/speed/fit/export
// settings, no per-video media) → ③ export this video → ④ batch export many videos with the same settings.
(()=>{
const pane=$('pane-export'),edit=window.editorState,api=window.editorTimeline,design=window.studioApi;
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const json=(url,body)=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const stem=n=>String(n||'').replace(/\.[^.]+$/,'');
const clock=t=>`${Math.floor(t/60)}:${String(Math.round(t%60)).padStart(2,'0')}`;
const step=(n,text)=>el('div',{className:'export-step'},el('span',{textContent:n}),el('strong',{textContent:text}));

// ---- layout of the pane
const summary=$('export-summary');summary.before(step('1','Thông số xuất'));
const presets=el('div',{className:'preset-box'});presets.innerHTML='<select id="preset-pick" aria-label="Cấu hình đã lưu"></select><div class="result-actions"><button type="button" id="preset-apply" class="outline-action small-action">Áp dụng</button><button type="button" id="preset-save" class="primary-action small-action">Lưu cấu hình hiện tại</button><button type="button" id="preset-delete" class="outline-action small-action danger-action">Xóa</button></div><p class="helper">Lưu cả thiết kế (nền, khung, chữ, logo, vị trí/lật video) và thông số âm thanh, tốc độ, tự khớp, nhạc nền, độ phân giải. Không lưu video/MP3 riêng của từng clip.</p>';
summary.after(step('2','Cấu hình đã lưu'),presets);
$('export-card').before(step('3','Xuất video đang dựng'));
const batch=el('div',{className:'batch-box',id:'batch-box'});
batch.innerHTML=`<div class="batch-head"><label class="check-row"><input type="checkbox" id="batch-all"> Chọn tất cả</label><button type="button" id="batch-reload" class="text-button">Làm mới</button></div>
<div id="batch-videos" class="batch-videos"></div>
<div class="two-col"><div><label for="batch-audio">MP3 cho từng video</label><select id="batch-audio"><option value="auto">Tự tìm MP3 cùng tên</option><option value="none">Không dùng MP3 · giữ tiếng gốc</option><option value="current">Dùng MP3 đang chọn cho tất cả</option></select></div><div><label for="batch-text">Chữ trên video</label><select id="batch-text"><option value="keep">Giữ chữ hiện tại</option><option value="name">Tiêu đề = tên video</option><option value="none">Không có chữ</option></select></div></div>
<p id="batch-note" class="helper"></p>
<div class="result-actions"><button type="button" id="batch-start" class="primary-action">Xuất hàng loạt</button><button type="button" id="batch-stop" class="outline-action danger-action" hidden>Dừng tất cả</button></div>
<ol id="batch-jobs" class="batch-jobs"></ol>`;
pane.append(step('4','Xuất hàng loạt'),batch);

// ---- saved configurations
const EDIT=['video-speed','audio-speed','audio-volume','original-volume','audio-mode','duration-policy','fit-mode','audio-offset','music-volume','music-speed','music-start','music-fade-in','music-fade-out'];
const EXPORT=['resolution','quality','fps','encoder','loudness'];
let list=[];
function snapshot(){const edits={};for(const id of EDIT)edits[id]=$(id).value;const out={};for(const id of EXPORT)out[id]=$(id).value;
 return {design:design.snapshot(false),edit:edits,export:out,music:{asset:edit.media().music_asset_id,duck:$('music-duck').checked,loop:$('music-loop').checked}}}
async function use(data){if(data.design)design.apply(data.design);
 if(data.music){if(typeof data.music.asset==='string'&&edit.assets().some(a=>a.asset_id===data.music.asset))await edit.useMusic(data.music.asset);$('music-duck').checked=data.music.duck!==false;$('music-loop').checked=data.music.loop!==false}
 if(data.export)for(const[id,v]of Object.entries(data.export))if($(id)&&[...$(id).options].some(o=>o.value===v)){$(id).value=v;$(id).dispatchEvent(new Event('change',{bubbles:true}))}
 if(data.edit)api.apply(Object.fromEntries(Object.entries(data.edit).filter(([k,v])=>EDIT.includes(k)&&typeof v==='string')));window.appHistory?.checkpoint()}
async function load(){try{list=(await request('/library/presets')).items;const keep=$('preset-pick').value;$('preset-pick').replaceChildren(new Option(list.length?'— Chọn cấu hình đã lưu —':'Chưa có cấu hình nào',''),...list.map(p=>new Option(p.name,p.id)));$('preset-pick').value=list.some(p=>p.id===keep)?keep:''}catch{}}
const say=t=>{$('batch-note').textContent=t;$('status').textContent=t};
$('preset-save').onclick=async()=>{const name=prompt('Tên cấu hình:',$('project-name').value||'Cấu hình '+new Date().toLocaleDateString('vi-VN'));if(!name?.trim())return;try{const r=await json('/library/presets/save',{name:name.trim().slice(0,120),data:snapshot()});await load();$('preset-pick').value=r.id;say(`Đã lưu cấu hình "${r.name}".`)}catch(e){say(e.message)}};
$('preset-apply').onclick=async()=>{const id=$('preset-pick').value;if(!id){say('Chọn một cấu hình đã lưu.');return}try{const r=await request('/library/presets/'+id);await use(r.data);say(`Đã áp dụng cấu hình "${r.name}". Ctrl+Z để hoàn tác.`)}catch(e){say(e.message)}};
$('preset-pick').ondblclick=$('preset-apply').onclick;
$('preset-delete').onclick=async()=>{const p=list.find(x=>x.id===$('preset-pick').value);if(!p){say('Chọn cấu hình cần xóa.');return}if(!confirm(`Xóa cấu hình "${p.name}"?`))return;try{await request(`/library/presets/${p.id}/delete`,{method:'POST'});await load()}catch(e){say(e.message)}};
load();

// ---- batch export: every checked video, full length, with the settings now in the editor
let videos=[],picked=new Set(),jobs=[];
async function videosLoad(){try{videos=(await request('/media/videos')).videos;await edit.reloadAssets()}catch(e){say(e.message)}draw()}
function match(v){const mode=$('batch-audio').value,assets=edit.assets();if(mode==='none')return null;if(mode==='current')return assets.find(a=>a.asset_id===edit.media().audio_asset_id)||null;
 const key=stem(v.name).toLowerCase();return assets.find(a=>stem(a.name).toLowerCase()===key)||assets.find(a=>stem(a.name).toLowerCase().startsWith(key))||null}
function draw(){$('batch-videos').replaceChildren(...(videos.length?videos.map(v=>{const box=el('input',{type:'checkbox',checked:picked.has(v.id)});box.onchange=()=>{box.checked?picked.add(v.id):picked.delete(v.id);label()};const a=match(v);
  return el('label',{className:'batch-video'},box,el('img',{src:v.thumb,alt:'',loading:'lazy'}),el('span',{className:'batch-video-name',textContent:v.name}),el('small',{textContent:clock(v.duration)+(a?' · ♪ '+stem(a.name):$('batch-audio').value==='auto'?' · không có MP3 cùng tên':'')}))}):[el('p',{className:'helper',textContent:'Kho Media chưa có video. Nhập video ở tab Media.'})]));label()}
function label(){$('batch-start').textContent=`Xuất hàng loạt ${picked.size} video`;$('batch-start').disabled=!picked.size;$('batch-all').checked=videos.length>0&&picked.size===videos.length;
 const fit=$('fit-mode').value;$('batch-note').textContent=`Mỗi video xuất đủ độ dài với thiết kế và thông số đang chọn${fit==='audio'?' · MP3 tự khớp theo video':fit==='video'?' · video tự khớp theo MP3':''}. Video xếp hàng và xuất lần lượt.`}
$('batch-all').onchange=()=>{picked=$('batch-all').checked?new Set(videos.map(v=>v.id)):new Set();draw()};
$('batch-audio').onchange=draw;$('batch-reload').onclick=videosLoad;$('fit-mode').addEventListener('input',label);$('fit-mode').addEventListener('change',label);
function plan(v,base){const o={...base,id:v.id,video_start:0,video_end:0,video_cuts:[],video_segments:[],project_name:stem(v.name)};delete o.preview_at;const a=match(v),fit=$('fit-mode').value;
 if(a){o.audio_asset_id=a.asset_id;o.audio_start=0;o.audio_end=0;if(o.audio_mode==='original')o.audio_mode='replace';
  if(fit==='audio'){const room=v.duration/o.video_speed-o.audio_offset;o.audio_speed=a.duration/room;o.duration_policy='video';if(!(room>.05&&o.audio_speed>=.25&&o.audio_speed<=4))throw Error('MP3 và video chênh lệch quá lớn để tự khớp')}
  else if(fit==='video'){o.video_speed=v.duration/(a.duration/o.audio_speed+o.audio_offset);o.duration_policy='audio';if(!(o.video_speed>=.25&&o.video_speed<=4))throw Error('MP3 và video chênh lệch quá lớn để tự khớp')}}
 else{o.audio_asset_id='';o.audio_mode='original';o.duration_policy='video'}
 const text=$('batch-text').value;if(text==='none')for(const k of window.TEXT_KEYS)o[k]='';if(text==='name'){o.title=stem(v.name).slice(0,160)}
 return o}
$('batch-start').onclick=async()=>{let base;try{base=options()}catch(e){say(e.message);return}const chosen=videos.filter(v=>picked.has(v.id));if(!chosen.length)return;
 $('batch-start').disabled=true;$('batch-stop').hidden=false;jobs=chosen.map(v=>({v,row:el('li',{},el('span',{className:'batch-name',textContent:v.name}),el('div',{className:'export-bar'},el('i')),el('small',{textContent:'đang gửi…'}))}));$('batch-jobs').replaceChildren(...jobs.map(j=>j.row));
 const show=(j,text,p)=>{j.row.querySelector('small').textContent=text;if(p!=null)j.row.querySelector('i').style.width=p+'%'};
 for(const j of jobs){try{await json('/render',plan(j.v,base));j.sent=true;show(j,'đang chờ lượt',0)}catch(e){j.done=true;j.row.classList.add('error');show(j,e.message)}}
 while(jobs.some(j=>j.sent&&!j.done)){await new Promise(r=>setTimeout(r,1500));for(const j of jobs.filter(j=>j.sent&&!j.done)){try{const r=await request('/jobs/'+j.v.id);
   if(r.state==='done'){j.done=true;j.row.classList.add('done');show(j,r.saved_path?'✓ đã lưu '+r.saved_path:'✓ xong',100);if(!r.saved_path)j.row.append(el('a',{href:r.url+'?t='+Date.now(),download:(r.name||'video')+'.mp4',textContent:'Tải về ↓'}))}
   else if(r.state==='error'||r.state==='cancelled'){j.done=true;j.row.classList.add('error');show(j,r.error||'đã dừng')}
   else show(j,r.state==='queued'?'đang chờ lượt':`${r.progress||0}%${r.eta!=null?' · còn ~'+clock(r.eta):''}`,r.progress||0)}catch(e){j.done=true;show(j,e.message)}}}
 const ok=jobs.filter(j=>j.row.classList.contains('done')).length;say(`Xuất hàng loạt xong ${ok}/${jobs.length} video.`);$('batch-stop').hidden=true;label();
 try{if(document.hidden&&window.Notification?.permission==='granted')new Notification('Review Studio',{body:`Đã xuất xong ${ok}/${jobs.length} video.`})}catch{}};
$('batch-stop').onclick=async()=>{for(const j of jobs.filter(j=>j.sent&&!j.done))await json(`/jobs/${j.v.id}/cancel`,{}).catch(()=>{});say('Đang dừng các video còn lại…')};
document.addEventListener('audio-created',()=>setTimeout(videosLoad,400));document.addEventListener('video-changed',()=>setTimeout(videosLoad,400));
videosLoad();
})();
