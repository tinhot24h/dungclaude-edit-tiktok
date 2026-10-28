'use strict';
// "Dựng video" = the dubbing page's layout (settings · queue · preview) with the editor's own design tools:
// the background/frame/title/body/video panels and the 9:16 stage of the old editor are moved into this page while
// it is open and moved back when the timeline editor opens, so every control, saved style and template keeps
// working as before. Both tabs share one queue engine; "Dựng video" runs jobs in the 'design' mode (no translation,
// optional AI title/body in one OpenAI call, same-name MP3), "Lồng tiếng" can add the same design (kết hợp).
(()=>{
const api=window.dubApi,studio=window.studioApi,edit=window.editorState;
if(!api||!studio)return;
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const setup=document.querySelector('#view-dub .dub-setup');
let name='dub',moved=false;
const places=new Map();   // moved node → [parent, next sibling] to put it back exactly

// ---- new sections: 🎨 Nền & khung, 🔤 Tiêu đề & nội dung
const sec=(id,icon,title,body)=>{const d=el('details',{className:'dub-sec',id:'sec-'+id});d.innerHTML=`<summary><span class="dub-sec-icon">${icon}</span><span class="dub-sec-title">${title}</span><small class="dub-sec-sum" id="sum-${id}"></small></summary><div class="dub-sec-body">${body}</div>`;return d};
const design=sec('design','🎨','Nền &amp; khung',`<label class="check-row" id="dt-on-row"><input id="dt-on" type="checkbox"> Thêm nền, khung, tiêu đề &amp; nội dung vào video lồng tiếng (kết hợp)</label>
 <div id="dt-bg-host"></div><p class="helper">Cùng bộ thiết kế với timeline: kiểu nền, màu chính/màu chuyển, vùng hòa nền (vị trí bắt đầu, chiều cao vùng chuyển, độ đục), khung có sẵn hoặc PNG. Kéo khung trên khung xem trước.</p>`);
const text=sec('text','🔤','Tiêu đề &amp; nội dung',`<div class="group-label">NGUỒN CHỮ · AI VIẾT CÙNG LẦN DỊCH (1 LẦN GỌI OPENAI)</div>
 <div class="dt-src"><label for="dt-title-src">Tiêu đề</label><select id="dt-title-src"><option value="ai">AI viết</option><option value="fixed">Cố định (ô bên dưới)</option><option value="file">Tên file</option><option value="none">Không hiện</option></select>
 <span>tối đa</span><input id="dt-title-words" type="number" min="1" max="30" value="6" aria-label="Số từ tối đa của tiêu đề"><span>từ</span></div>
 <div class="dt-src"><label for="dt-body-src">Nội dung</label><select id="dt-body-src"><option value="ai">AI viết</option><option value="fixed">Cố định (ô bên dưới)</option><option value="file">Tên file</option><option value="none">Không hiện</option></select>
 <span>từ</span><input id="dt-body-min" type="number" min="0" max="120" value="10" aria-label="Số từ tối thiểu của nội dung"><span>–</span><input id="dt-body-max" type="number" min="1" max="120" value="20" aria-label="Số từ tối đa của nội dung"></div>
 <label class="check-row"><input id="dt-review" type="checkbox"> ⏸ Dừng lại để duyệt chữ AI trước khi xuất <small>(sửa hàng loạt trong một bảng rồi bấm Xuất tất cả)</small></label>
 <p class="helper" id="dt-ai-note"></p>
 <div class="group-label">CHỮ CỐ ĐỊNH / CHỮ MẪU TRÊN KHUNG XEM TRƯỚC</div><div id="dt-fixed-host"></div>
 <div class="group-label">KIỂU CHỮ · KÉO, ĐỔI CỠ, NHẤP ĐÚP ĐỂ SỬA TRÊN KHUNG XEM TRƯỚC</div>
 <div class="dub-btns" id="dt-style-tabs"><button type="button" data-k="title" class="on">Tiêu đề</button><button type="button" data-k="body">Nội dung</button></div><div id="dt-style-host"></div>`);
const videoHost=el('div',{id:'dt-video-host'});
setup.querySelector('#sec-input').after(design,text);
// one section open at a time (the new sections too) keeps the column short
for(const d of [design,text])d.addEventListener('toggle',()=>{if(d.open)for(const o of setup.querySelectorAll('.dub-sec'))if(o!==d)o.open=false});
for(const d of setup.querySelectorAll('.dub-sec'))d.addEventListener('toggle',()=>{if(d.open)for(const o of [design,text])if(o!==d)o.open=false});
$('sec-frame').querySelector('.dub-sec-body').append(videoHost);
// the editor stage takes the place of the dubbing preview while the design is on
const stageHost=el('div',{id:'dt-stage-host',className:'dt-stage-host',hidden:true});
$('dub-frame').closest('.dub-frame-wrap').after(stageHost);

// ---- order and visibility of the sections per tab
const ORDER={design:['input','keys','design','text','frame','overlay','image','translate','audio','voice','export'],
             dub:['input','keys','frame','overlay','image','design','text','translate','audio','voice','export']};
const TITLES={design:{translate:'AI viết chữ',audio:'Âm thanh gốc',voice:'MP3 cùng tên · khớp thời lượng',frame:'Cắt & vị trí video',export:'Xuất'},
              dub:{translate:'Nhận diện & dịch',audio:'Âm thanh gốc',voice:'Giọng đọc ai33',frame:'Cắt & khung hình video',export:'Xuất & file phụ đề'}};
// parts of the dubbing sections that do not apply to "Dựng video"
const block=e=>e?.closest('.two-col,.folder-row,.check-row,.dub-limits,label')||e;
const hideInDesign=()=>[
 ...['dub-mode','dub-mode-note','dub-rate','dub-pronoun','dub-review'].map(id=>$(id)&&(id==='dub-pronoun'?$(id).parentElement:id==='dub-review'?$(id).closest('label'):$(id))),
 $('dub-mode')&&document.querySelector('label[for=dub-mode]'),document.querySelector('label[for=dub-rate]'),$('dub-rate')?.closest('.dub-range'),
 document.querySelector('label[for=dub-voice]'),$('dub-voice')?.closest('.folder-row'),$('dub-voice-note'),$('dub-voices'),$('dub-speed')?.closest('.two-col'),$('dub-dict')?.parentElement,
 ...[...$('sec-frame').querySelector('.dub-sec-body').children].filter((c,i)=>i>0&&c!==videoHost),
 $('dub-subs')?.parentElement];
const hideInDub=()=>[videoHost];
let hidden=[];
function layout(){for(const e of hidden)if(e)e.hidden=false;hidden=(name==='design'?hideInDesign():hideInDub()).filter(Boolean);for(const e of hidden)e.hidden=true;
 for(const id of ORDER[name]){const s=$('sec-'+id);if(s)setup.append(s)}
 for(const[id,t]of Object.entries(TITLES[name]))$('sec-'+id).querySelector('.dub-sec-title').textContent=t;
 $('dt-on-row').hidden=name==='design';$('sec-text').hidden=!on();
 document.querySelector('#view-dub .dub-bar-title h1').textContent=name==='design'?'Dựng video hàng loạt':'Lồng tiếng video';
 document.querySelector('#view-dub .dub-bar-title .eyebrow').textContent=name==='design'?'NỀN + KHUNG + TIÊU ĐỀ + NỘI DUNG · HÀNG LOẠT':'LỒNG TIẾNG TỰ ĐỘNG · TRUNG · ANH → VIỆT';
 $('dub-preset-save').textContent=name==='design'?'💾 Lưu mẫu dựng':'💾 Lưu cấu hình';
 api.startLabel()}
const on=()=>name==='design'||$('dt-on').checked;

// ---- moving the editor's panels and stage in and out
function park(node,host){if(!node)return;if(!places.has(node))places.set(node,[node.parentNode,node.nextSibling]);host.append(node);node.hidden=false}
function moveIn(){if(moved)return;moved=true;
 park($('section-background'),$('dt-bg-host'));park($('section-frame'),$('dt-bg-host'));
 for(const k of ['title','body']){park(document.querySelector(`label[for=${k}]`),$('dt-fixed-host'));park($(k),$('dt-fixed-host'))}
 park($('section-title'),$('dt-style-host'));park($('section-body'),$('dt-style-host'));styleTab(styleKey);
 park($('section-video'),videoHost);
 const panel=document.querySelector('#view-editor .preview-panel');for(const c of [...panel.children].filter(c=>!c.classList.contains('preview-heading')))park(c,stageHost)}
function moveOut(){if(!moved)return;moved=false;
 // back in reverse order so every node finds its old neighbour
 for(const[node,[parent,next]]of [...places.entries()].reverse()){if(next&&next.parentNode===parent)parent.insertBefore(node,next);else parent.append(node)}
 places.clear();const tab=document.querySelector('#tabs [aria-selected=true]')?.id?.replace('tab-','')||'background';
 for(const e of document.querySelectorAll('#editor .editor-section'))e.hidden=e.id!=='section-'+tab}
let styleKey='title';
function styleTab(k){styleKey=k;for(const b of $('dt-style-tabs').children)b.classList.toggle('on',b.dataset.k===k);$('section-title').hidden=k!=='title';$('section-body').hidden=k!=='body'}
$('dt-style-tabs').onclick=e=>{const b=e.target.closest('button');if(b)styleTab(b.dataset.k)};

// ---- settings sent with each job
const KEEP=new Set(['units','template','frame_id','images']);
function designOptions(){const o=options(),keep=new Set([...studio.fields,...window.TEXT_KEYS,...KEEP]);return Object.fromEntries(Object.entries(o).filter(([k])=>keep.has(k)))}
const num=(id,d)=>{const v=parseInt($(id).value,10);return Number.isFinite(v)?v:d};
function extend(o){if(name==='design')o.mode='design';
 if(!on()){o.design=null;return}
 try{o.design=designOptions()}catch(e){o.design=null;o.design_error=e.message}
 Object.assign(o,{title_source:$('dt-title-src').value,body_source:$('dt-body-src').value,title_words:num('dt-title-words',6),body_min:num('dt-body-min',10),body_max:num('dt-body-max',20),review_texts:$('dt-review').checked})}
function apply(o){if(o.title_source)$('dt-title-src').value=o.title_source;if(o.review_texts!=null)$('dt-review').checked=!!o.review_texts;if(o.body_source)$('dt-body-src').value=o.body_source;
 for(const[id,k]of [['dt-title-words','title_words'],['dt-body-min','body_min'],['dt-body-max','body_max']])if(o[k]!=null)$(id).value=o[k];
 if(name==='dub')$('dt-on').checked=!!o.design;
 if(o.design&&typeof o.design==='object'){studio.apply({...o.design,images:o.design.images||[]});studio.schedule()}
 layout();if(on())moveIn()}

// ---- preview: the editor stage shows the first video with the design; overlay video plays in sync
let shownId='';
async function showVideo(f){if(!f)return;if(f.path&&!f.id){if(f.importing)return;f.importing=true;try{await api.localImport(f)}catch(e){f.error=e.message;api.draw();return}finally{f.importing=false}}
 if(f.id&&f.id!==shownId){shownId=f.id;try{await edit.openVideo(f.id,true)}catch(e){api.say(e.message)}}
 else if(f.file&&!f.id&&shownId!==f.name){shownId=f.name;$('video').src=URL.createObjectURL(f.file);$('placeholder').hidden=true}}
function overlayLayer(){const src=$('dub-ovv'),on=!src.hidden&&src.dataset.src,scene=$('scene');let v=$('dt-ovv');
 if(!v){v=el('video',{id:'dt-ovv',className:'art',muted:true,loop:true,playsInline:true});v.style.pointerEvents='none';$('overlay').after(v)}
 v.hidden=!on;if(!on)return;if(v.dataset.src!==src.dataset.src){v.src=src.dataset.src;v.dataset.src=src.dataset.src}
 Object.assign(v.style,{opacity:src.style.opacity,mixBlendMode:src.style.mixBlendMode,objectFit:'cover',width:'720px',height:'1280px',left:0,top:0});
 const main=$('video');if(main.paused)v.pause();else v.play().catch(()=>{});
 if(v.duration&&Math.abs(v.currentTime-(main.currentTime%v.duration))>.3)v.currentTime=main.currentTime%v.duration}
// image layer: the dub page's box moves onto the stage, under the frame and text like the export
function imageLayer(){const box=$('dub-imgbox'),scene=$('scene'),o=api.settings();if(!places.has(box))places.set(box,[box.parentNode,box.nextSibling]);
 const anchor=o.image_layer==='above'||!$('dt-ovv')?$('frame-art'):$('dt-ovv');if(box.parentNode!==scene||box.nextSibling!==anchor)scene.insertBefore(box,anchor);
 api.drawImage(o,720,1280);box.style.zIndex='auto'}
for(const ev of ['play','pause','seeked'])$('video').addEventListener(ev,()=>on()&&overlayLayer());
let jobShown=null;
function previewJob(job){jobShown=job&&job.texts&&on()?job:null;window.previewTexts=jobShown?{title:jobShown.texts.title||'',body:jobShown.texts.body||''}:null;studio.schedule();api.preview()}
function preview(f){const use=on();if(jobShown)f={id:jobShown.video_id,name:jobShown.name};stageHost.hidden=!use;$('dub-frame').closest('.dub-frame-wrap').hidden=use;$('dub-transport')&&($('dub-transport').hidden=use);
 document.querySelector('#view-dub .dub-transport')?.toggleAttribute('hidden',use);
 if(!use)return false;moveIn();showVideo(f);imageLayer();setTimeout(()=>{overlayLayer();imageLayer()},50);
 $('dub-preview-info').textContent=jobShown?`${jobShown.name} · chữ AI của video này (đã dựng) · bấm lại vào video trong hàng đợi để thôi xem`:f?`${f.name} · thiết kế 720×1280 → xuất 1080×1920`:'Chọn video ở mục 🎬 để xem trước';
 $('dub-preview-note').textContent='Kéo video, khung, chữ trên khung hình; nhấp đúp chữ để sửa. Chữ AI của từng video thay cho chữ mẫu khi xuất.';return true}

// ---- "✎ Chỉnh chi tiết": one finished video in the timeline with its own design and texts
let restore=false;   // the timeline now holds that job's design: the tab's own settings load again on return
async function detail(job){api.say('Đang mở video ở tab Timeline…');const full=await request('/dub/'+job.id);
 if(!restore)api.remember();restore=true;jobShown=null;window.previewTexts=null;switchView('editor');
 await api.toEditor(job);
 const d=full.options?.design;if(d)studio.apply({...d,images:d.images||[]});
 for(const k of ['title','body'])$(k).value=(job.texts||{})[k]||'';studio.schedule();setTimeout(()=>window.appHistory?.checkpoint(),400);
 $('status').textContent=`Đã mở "${job.name}" ở Timeline với nền, khung và chữ của video này (lớp ảnh, overlay của tab Dựng video không đi kèm). Quay lại tab Dựng video thì thiết kế của tab đó được giữ nguyên.`}

// ---- summaries
function labels(){const o={};extend(o);const bg=({solid:'một màu',gradient:'chuyển hai màu',none:'không nền'})[$('background').value]||'',fr=$('frame_style').selectedOptions[0]?.textContent.split('·')[0].trim();
 $('sum-design').textContent=on()?`${bg} · hòa nền từ ${$('fade_start').value}px · ${fr}`:'tắt · không bắt buộc';
 const src=v=>({ai:'AI viết',fixed:'cố định',file:'tên file',none:'không'})[v];
 $('sum-text').textContent=`tiêu đề: ${src($('dt-title-src').value)}${$('dt-title-src').value==='ai'?' ≤ '+$('dt-title-words').value+' từ':''} · nội dung: ${src($('dt-body-src').value)}${$('dt-body-src').value==='ai'?' '+$('dt-body-min').value+'–'+$('dt-body-max').value+' từ':''}`;
 if(name==='design'){const n=v=>Number($(v)?.value)||0;$('sum-frame').textContent=[n('dub-trim-start')||n('dub-trim-end')?`cắt ${n('dub-trim-start')}s đầu · ${n('dub-trim-end')}s cuối`:'không cắt',`video ${$('video_width').value}×${$('video_height').value}`].join(' · ');
  const files=api.files(),m=files.filter(f=>f.mp3).length;$('sum-voice').textContent=files.length?`${m}/${files.length} video có MP3 cùng tên · ${({auto:'tự khớp',voice:'MP3 khớp video',video:'video khớp MP3'})[$('dub-align').value]||''}`:'MP3 cùng tên tự nhận khi chọn video'}
 $('dub-export-note').textContent=`Video lưu vào thư mục xuất (nút thông số xuất ở góc trên) với tên “…-${name==='design'?'dung':'long-tieng'}.mp4”.`;
 $('dub-drop').textContent=name==='design'?'Kéo thả video hoặc cả thư mục vào đây · MP3 cùng tên (vd: a.mp4 + a.mp3) tự ghép làm giọng đọc':'Kéo thả video hoặc cả thư mục vào đây · .srt cùng tên sẽ bỏ qua bước nhận diện';
 const ai=on()&&[$('dt-title-src').value,$('dt-body-src').value].includes('ai');
 $('dt-ai-note').textContent=!ai?'Không dùng AI cho chữ.':name==='design'?'Dựng video: OpenAI nhận diện lời trong video (Whisper) rồi viết tiêu đề + nội dung trong 1 lần gọi. Video không có tiếng hoặc không có key: tiêu đề lấy theo tên file.':'Lồng tiếng: tiêu đề + nội dung được viết cùng lần dịch (không thêm lượt gọi). Chế độ ai33 tự lồng tiếng cần thêm 1 lần gọi ngắn.'}
for(const id of ['dt-title-src','dt-body-src','dt-title-words','dt-body-min','dt-body-max','dt-on','dt-review'])$(id).addEventListener('change',()=>{layout();if(on())moveIn();api.remember();labels();api.preview()});
document.addEventListener('design-changed',()=>{if(on()&&!$('view-dub').hidden){labels();clearTimeout(labels.t);labels.t=setTimeout(()=>api.remember(),400)}});

// ---- tabs: "Dựng video" and "Lồng tiếng" open this page; "Timeline" opens the old editor for one video
const navTimeline=el('button',{type:'button',id:'nav-timeline',className:'nav-item',textContent:'Timeline · chỉnh 1 video',title:'Trình dựng chi tiết: cắt ghép nhiều đoạn, tốc độ từng đoạn, nhạc nền'});
$('nav-dub').after(navTimeline);
function mark(view){for(const[id,active]of [['nav-editor',view==='dub'&&name==='design'],['nav-dub',view==='dub'&&name==='dub'],['nav-timeline',view==='editor']])$(id).classList.toggle('active',active)}
function enter(next){if(next!==name||restore){if(!restore)api.remember();restore=false;name=next;window.dubProfile.name=next;shownId='';jobShown=null;window.previewTexts=null;api.load();api.loadPresets();api.refresh();api.draw()}
 layout();if(on())moveIn();else moveOut();switchView('dub');mark('dub');labels();api.preview()}
$('nav-editor').onclick=()=>enter('design');$('nav-dub').onclick=()=>enter('dub');
navTimeline.onclick=()=>switchView('editor');
document.addEventListener('view-change',e=>{if(e.detail!=='dub')moveOut();setTimeout(()=>mark(e.detail))});

// ---- old design templates (timeline tab) in the "Mẫu dựng" list: they set the design only
async function addTemplates(){if(name!=='design')return;const pick=$('dub-preset');pick.querySelector('optgroup.dt-old')?.remove();
 try{const t=(await request('/library/templates')).items;if(!t.length)return;const g=el('optgroup',{className:'dt-old',label:'Thiết kế đã lưu ở timeline'});for(const x of t)g.append(new Option(x.name,'tpl:'+x.id));pick.append(g)}catch{}}
$('dub-preset').addEventListener('change',async e=>{const v=$('dub-preset').value;if(!v.startsWith('tpl:'))return;e.stopImmediatePropagation();
 try{const r=await request('/library/templates/'+v.slice(4));studio.apply(r.data.design);studio.schedule();api.remember();api.say(`Đã áp dụng thiết kế "${r.name}". Bấm 💾 Lưu mẫu dựng để lưu kèm thông số hàng loạt.`)}catch(err){api.say(err.message)}},true);
new MutationObserver(()=>{if(name==='design'&&!$('dub-preset').querySelector('optgroup.dt-old'))addTemplates()}).observe($('dub-preset'),{childList:true});

window.dubProfile={name,extend,apply,preview,labels,previewJob,detail};
Object.defineProperty(window.dubProfile,'name',{get:()=>name,set:v=>{name=v}});
// "Dựng video" is the start page; its own saved settings load once the dubbing defaults are known
document.addEventListener('dub-ready',()=>enter('design'),{once:true});
const ready=setInterval(()=>{if(document.querySelector('#dub-style option')){clearInterval(ready);document.dispatchEvent(new Event('dub-ready'))}},100);
})();
