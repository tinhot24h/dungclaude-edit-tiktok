'use strict';
// "Dựng & lồng tiếng" (one tab since 0.22) = the dubbing page (settings · queue · preview) with the editor's own
// design tools: the background/frame/title/body/video panels and the 9:16 stage of the old editor live in this page
// (moved in once; the old timeline tab is gone). Every video runs the same way, from the MP4 to the finished file:
// OpenAI recognises and translates, ai33 reads the Vietnamese voice. "Nền & khung", "Tiêu đề" and "Nội dung" are
// three separate groups, each with its own on/off switch; everything set here is saved in a template.
(()=>{
const api=window.dubApi,studio=window.studioApi,edit=window.editorState;
if(!api||!studio)return;
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const setup=document.querySelector('#view-dub .dub-setup');
let moved=false;

// ---- three groups with a switch on their header: 🎨 Nền & khung, 🅣 Tiêu đề, ¶ Nội dung
const sec=(id,icon,title,body)=>{const d=el('details',{className:'dub-sec dt-group',id:'sec-'+id});
 d.innerHTML=`<summary><span class="dub-sec-icon">${icon}</span><span class="dub-sec-title">${title}</span><small class="dub-sec-sum" id="sum-${id}"></small><label class="dt-toggle" title="Bật/tắt cả nhóm"><input type="checkbox" id="dt-${id}-on"><i></i></label></summary><div class="dub-sec-body"><p class="helper dt-off-note" id="dt-${id}-off">Nhóm này đang tắt: video xuất không có phần này. Bật công tắc ở tiêu đề mục để dùng.</p><div class="dt-body" id="dt-${id}-body">${body}</div></div>`;
 // the switch toggles the group, not the section
 d.querySelector('.dt-toggle').addEventListener('click',e=>{e.preventDefault();e.stopPropagation();const c=d.querySelector('input');c.checked=!c.checked;c.dispatchEvent(new Event('change',{bubbles:true}))});
 return d};
const SRC=`<option value="ai">AI viết (cùng lần dịch)</option><option value="fixed">Cố định (ô bên dưới)</option><option value="file">Tên file video</option>`;
const design=sec('design','🎨','Nền &amp; khung',`<div id="dt-bg-host"></div><p class="helper">Kiểu nền, màu chính/màu chuyển, vùng hòa nền (vị trí bắt đầu, chiều cao vùng chuyển, độ đục), khung có sẵn hoặc PNG. Kéo khung trên khung xem trước.</p>`);
const title=sec('title','🅣','Tiêu đề',`<div class="dt-src"><label for="dt-title-src">Nguồn chữ</label><select id="dt-title-src">${SRC}</select><span>tối đa</span><input id="dt-title-chars" type="number" min="5" max="160" value="30" aria-label="Số ký tự tối đa của tiêu đề"><span>ký tự</span></div>
 <div class="group-label">CHỮ CỐ ĐỊNH / CHỮ MẪU TRÊN KHUNG XEM TRƯỚC</div><div id="dt-title-text"></div>
 <div class="group-label">KIỂU CHỮ · KÉO, ĐỔI CỠ, NHẤP ĐÚP ĐỂ SỬA TRÊN KHUNG XEM TRƯỚC</div><div id="dt-title-style"></div>`);
const body=sec('body','¶','Nội dung',`<div class="dt-src"><label for="dt-body-src">Nguồn chữ</label><select id="dt-body-src">${SRC}</select><span>từ</span><input id="dt-body-min" type="number" min="0" max="600" value="50" aria-label="Số ký tự tối thiểu của nội dung"><span>–</span><input id="dt-body-max" type="number" min="10" max="600" value="100" aria-label="Số ký tự tối đa của nội dung"><span>ký tự</span></div>
 <div class="group-label">CHỮ CỐ ĐỊNH / CHỮ MẪU TRÊN KHUNG XEM TRƯỚC</div><div id="dt-body-text"></div>
 <div class="group-label">KIỂU CHỮ · KÉO, ĐỔI CỠ, NHẤP ĐÚP ĐỂ SỬA TRÊN KHUNG XEM TRƯỚC</div><div id="dt-body-style"></div>`);
setup.querySelector('#sec-input').after(design,title,body);
// shared by title and body: the AI part lives with the translation (same OpenAI call)
const aiBox=el('div',{id:'dt-ai-box'});aiBox.innerHTML=`<div class="group-label">AI VIẾT TIÊU ĐỀ &amp; NỘI DUNG · CÙNG LẦN DỊCH</div><label class="check-row"><input id="dt-review" type="checkbox"> ⏸ Dừng lại để duyệt chữ AI trước khi xuất <small>(sửa hàng loạt trong một bảng rồi bấm Xuất tất cả)</small></label><p class="helper" id="dt-ai-note"></p>`;
$('sec-translate').querySelector('.dub-sec-body').append(aiBox);
const videoHost=el('div',{id:'dt-video-host'});
$('sec-frame').querySelector('.dub-sec-body').append(videoHost);
// one section open at a time keeps the column short
for(const d of [design,title,body])d.addEventListener('toggle',()=>{if(d.open)for(const o of setup.querySelectorAll('.dub-sec'))if(o!==d)o.open=false});
for(const d of setup.querySelectorAll('.dub-sec'))d.addEventListener('toggle',()=>{if(d.open)for(const o of [design,title,body])if(o!==d)o.open=false});
// the editor stage takes the place of the dubbing preview while a group is on
const stageHost=el('div',{id:'dt-stage-host',className:'dt-stage-host',hidden:true});
$('dub-frame').closest('.dub-frame-wrap').after(stageHost);
// API keys are managed once in the header (🔑), not on this page
$('sec-keys').hidden=true;

// ---- order and visibility
const ORDER=['input','design','title','body','frame','overlay','image','translate','voice','audio','export'];
const bgOn=()=>$('dt-design-on').checked,titleOn=()=>$('dt-title-on').checked,bodyOn=()=>$('dt-body-on').checked;
const on=()=>bgOn()||titleOn()||bodyOn();
// with a design the editor's video box places the video; without it the dub frame tools do
const frameTools=()=>[...$('sec-frame').querySelector('.dub-sec-body').children].filter((c,i)=>i>0&&c!==videoHost);
function layout(){for(const id of ORDER){const s=$('sec-'+id);if(s)setup.append(s)}
 for(const k of ['design','title','body']){const o=$(`dt-${k}-on`).checked;$(`dt-${k}-body`).hidden=!o;$(`dt-${k}-off`).hidden=o;$('sec-'+k).classList.toggle('off',!o)}
 for(const e of frameTools())e.hidden=on();videoHost.hidden=!on();
 $('sec-translate').querySelector('.dub-sec-title').textContent='Nhận diện, dịch & viết chữ';
 document.querySelector('#view-dub .dub-bar-title h1').textContent='Dựng & lồng tiếng hàng loạt';
 document.querySelector('#view-dub .dub-bar-title .eyebrow').textContent='MP4 → OPENAI DỊCH → AI33 ĐỌC → NỀN, KHUNG, CHỮ → VIDEO HOÀN THIỆN';
 $('dub-preset-save').textContent='💾 Lưu mẫu';api.startLabel()}

// ---- the editor's panels and stage live in this page (moved in once)
function park(node,host){if(!node)return;host.append(node);node.hidden=false}
function moveIn(){if(moved)return;moved=true;
 park($('section-background'),$('dt-bg-host'));park($('section-frame'),$('dt-bg-host'));
 for(const k of ['title','body']){park(document.querySelector(`label[for=${k}]`),$(`dt-${k}-text`));park($(k),$(`dt-${k}-text`));park($('section-'+k),$(`dt-${k}-style`))}
 park($('section-video'),videoHost);
 // only the 9:16 stage: the timeline's own transport, loudness meter and layer list stay behind (not used here)
 park(document.querySelector('#view-editor .preview-workspace'),stageHost);stageHost.append(transport);
 // the old editor's tab code still hides the sections that are not its current tab: keep ours shown
 const keep=new MutationObserver(list=>{for(const m of list)if(m.target.hidden)m.target.hidden=false});
 for(const id of ['section-background','section-frame','section-title','section-body','section-video'])keep.observe($(id),{attributes:true,attributeFilter:['hidden']})}
// a small transport for the stage (the overlay video follows it)
const transport=el('div',{className:'dub-transport dt-transport'}),tPlay=el('button',{type:'button',className:'fm-play',textContent:'▶',title:'Phát/dừng'}),tSeek=el('input',{type:'range',min:0,max:1,step:.01,value:0}),tTime=el('output',{textContent:'0:00.0'});
tSeek.setAttribute('aria-label','Vị trí');transport.append(tPlay,tSeek,tTime);
const clock=t=>`${Math.floor(t/60)}:${(t%60).toFixed(1).padStart(4,'0')}`;
// plays only the part kept by "Cắt đầu / Cắt cuối", like the export
const cut=()=>{const o=api.settings(),d=$('video').duration||0;return[Math.min(o.trim_start||0,d),Math.max(0,d-(o.trim_end||0))]};
tPlay.onclick=()=>{const v=$('video'),[a,b]=cut();if(v.paused){if(v.currentTime<a||v.currentTime>=b-.05)v.currentTime=a;v.play().catch(()=>{})}else v.pause()};
tSeek.oninput=()=>{const[a]=cut();$('video').currentTime=a+Number(tSeek.value)};
function trimView(){const v=$('video'),[a,b]=cut();tSeek.max=Math.max(.1,b-a);if(v.paused&&(v.currentTime<a||v.currentTime>b))v.currentTime=a}
$('video').addEventListener('loadedmetadata',trimView);
// the camera zoom (Hiệu ứng máy quay) of the stage follows the playback of the kept part
window.motionClock=()=>{const v=$('video'),[a,b]=cut();return{t:Math.max(0,v.currentTime-a),d:Math.max(.1,b-a)}};
$('video').addEventListener('seeked',()=>window.renderVideoTransform?.());
$('video').addEventListener('timeupdate',()=>{const v=$('video'),[a,b]=cut();window.renderVideoTransform?.();if(!v.paused&&v.currentTime>=b)v.pause();tSeek.value=Math.max(0,v.currentTime-a);tTime.textContent=clock(Math.max(0,v.currentTime-a))});
for(const id of ['dub-trim-start','dub-trim-end'])$(id).addEventListener('input',()=>{trimView();const[a]=cut();$('video').currentTime=a});
$('video').addEventListener('play',()=>{tPlay.textContent='❚❚'});$('video').addEventListener('pause',()=>{tPlay.textContent='▶'});
$('dub-pv-mute').addEventListener('click',()=>setTimeout(()=>{$('video').muted=$('dub-preview-video').dataset.mute==='1'}));

// ---- settings: everything is saved (also the groups that are off), the server drops what is switched off
const KEEP=new Set(['units','template','frame_id','images']);
function designOptions(){const o=options(),keep=new Set([...studio.fields,...window.TEXT_KEYS,...KEEP]);return Object.fromEntries(Object.entries(o).filter(([k])=>keep.has(k)))}
const num=(id,d)=>{const v=parseInt($(id).value,10);return Number.isFinite(v)?v:d};
function extend(o){try{o.design=designOptions()}catch(e){o.design=null;o.design_error=e.message}
 Object.assign(o,{design_bg:bgOn(),design_title:titleOn(),design_body:bodyOn(),title_source:$('dt-title-src').value,body_source:$('dt-body-src').value,
  title_chars:num('dt-title-chars',30),body_min_chars:num('dt-body-min',50),body_max_chars:num('dt-body-max',100),review_texts:$('dt-review').checked})}
function apply(o){const had=!!o.design;
 // older settings: one "chữ" switch (design_text) or the design itself meaning on
 $('dt-design-on').checked=o.design_bg??had;$('dt-title-on').checked=o.design_title??o.design_text??(had&&o.title_source!=='none');$('dt-body-on').checked=o.design_body??o.design_text??(had&&o.body_source!=='none');
 for(const[id,k]of [['dt-title-src','title_source'],['dt-body-src','body_source']])if(['ai','fixed','file'].includes(o[k]))$(id).value=o[k];
 if(o.review_texts!=null)$('dt-review').checked=!!o.review_texts;
 for(const[id,k]of [['dt-title-chars','title_chars'],['dt-body-min','body_min_chars'],['dt-body-max','body_max_chars']])if(o[k]!=null)$(id).value=o[k];
 if(o.design&&typeof o.design==='object'){studio.apply({...o.design,images:o.design.images||[]})}
 layout();moveIn();designPreview()}

// ---- preview: the editor stage shows the selected video with what is switched on, the overlay plays in sync
let shownId='',current=null,jobShown=null;
async function showVideo(f){if(!f)return;if(f.path&&!f.id){if(f.importing)return;f.importing=true;try{await api.localImport(f)}catch(e){f.error=e.message;api.draw();return}finally{f.importing=false}}
 if(f.id&&f.id!==shownId){shownId=f.id;try{await edit.openVideo(f.id,true)}catch(e){api.say(e.message)}}
 else if(f.file&&!f.id&&shownId!==f.name){shownId=f.name;$('video').src=URL.createObjectURL(f.file);$('placeholder').hidden=true}}
// what the stage shows = what the export will make: switched-off groups are left out, "tên file" shows the file name
function designPreview(){const stem=n=>(n||'').replace(/^.*[\\/]/,'').replace(/\.[^.]+$/,''),name=stem(jobShown?.name||current?.name),o={};
 if(!bgOn())Object.assign(o,{background:'none',frame_style:'none'});
 for(const k of ['title','body']){const src=$(`dt-${k}-src`).value;if(!$(`dt-${k}-on`).checked)o[k]='';else if(jobShown?.texts)o[k]=jobShown.texts[k]||'';else if(src==='file')o[k]=k==='title'?name:''}
 window.designPreview=o;studio.schedule()}
function overlayLayer(){const still=$('dub-ovi');let img=$('dt-ovi');
 if(!img){img=el('img',{id:'dt-ovi',className:'art',alt:''});img.style.pointerEvents='none';$('overlay').after(img)}
 img.hidden=still.hidden||!still.dataset.src;if(!img.hidden){if(img.dataset.src!==still.dataset.src){img.src=still.dataset.src;img.dataset.src=still.dataset.src}Object.assign(img.style,{opacity:still.style.opacity,mixBlendMode:still.style.mixBlendMode,objectFit:'cover',width:'720px',height:'1280px',left:0,top:0})}
 const src=$('dub-ovv'),show=!src.hidden&&src.dataset.src;let v=$('dt-ovv');
 if(!v){v=el('video',{id:'dt-ovv',className:'art',muted:true,loop:true,playsInline:true});v.style.pointerEvents='none';$('overlay').after(v)}
 v.hidden=!show;if(!show)return;if(v.dataset.src!==src.dataset.src){v.src=src.dataset.src;v.dataset.src=src.dataset.src}
 Object.assign(v.style,{opacity:src.style.opacity,mixBlendMode:src.style.mixBlendMode,objectFit:'cover',width:'720px',height:'1280px',left:0,top:0});
 const main=$('video');if(main.paused)v.pause();else v.play().catch(()=>{});
 if(v.duration&&Math.abs(v.currentTime-(main.currentTime%v.duration))>.3)v.currentTime=main.currentTime%v.duration}
// image layer and TikTok safe zone: the dub page's boxes move onto the stage (image under the frame and text, like the export)
function stageLayers(use){const box=$('dub-imgbox'),safe=$('dub-safe').checked;
 if(use){const o=api.settings(),scene=$('scene'),anchor=o.image_layer==='above'||!$('dt-ovi')?$('frame-art'):$('dt-ovi');if(box.parentNode!==scene||box.nextSibling!==anchor)scene.insertBefore(box,anchor);
  api.drawImage(o,720,1280);box.style.zIndex='auto'}
 else{const frame=$('dub-frame');if(box.parentNode!==frame)frame.insertBefore(box,$('dub-frame-empty'))}
 // the stage's own TikTok safe zone (720×1280 design pixels) follows the "Vùng an toàn TikTok" box of this page
 if($('safe-zone'))$('safe-zone').hidden=!(use&&safe);$('dub-safezone').hidden=use||!safe}
for(const ev of ['play','pause','seeked'])$('video').addEventListener(ev,()=>on()&&overlayLayer());
function previewJob(job){jobShown=job&&job.texts&&on()?job:null;designPreview();api.preview()}
function preview(f){const use=on();if(jobShown)f={id:jobShown.video_id,name:jobShown.name};
 if((f?.id||f?.name)!==(current?.id||current?.name)){current=f;designPreview()}
 stageHost.hidden=!use;$('dub-frame').closest('.dub-frame-wrap').hidden=use;document.querySelector('#view-dub .dub-transport')?.toggleAttribute('hidden',use);
 stageLayers(use);if(!use)return false;
 showVideo(f);overlayLayer();setTimeout(()=>{overlayLayer();stageLayers(true)},50);
 $('dub-preview-info').textContent=jobShown?`${jobShown.name} · chữ AI của video này (đã dựng) · bấm lại vào video trong hàng đợi để thôi xem`:f?`${f.name} · thiết kế 720×1280 → xuất 1080×1920`:'Chọn video ở mục 🎬 để xem trước';
 $('dub-preview-note').textContent='Kéo video, khung, chữ trên khung hình; nhấp đúp chữ để sửa. Chữ AI của từng video thay cho chữ mẫu khi xuất.';return true}

// ---- summaries
function labels(){const bg=({solid:'một màu',gradient:'chuyển hai màu',none:'không nền'})[$('background').value]||'',fr=$('frame_style').selectedOptions[0]?.textContent.split('·')[0].trim();
 const src=v=>({ai:'AI viết',fixed:'cố định',file:'tên file'})[v];
 $('sum-design').textContent=bgOn()?`${bg} · hòa nền từ ${$('fade_start').value}px · ${fr}`:'tắt';
 $('sum-title').textContent=titleOn()?`${src($('dt-title-src').value)}${$('dt-title-src').value==='ai'?' · ≤ '+$('dt-title-chars').value+' ký tự':''} · cỡ ${$('title_size').value}px`:'tắt';
 $('sum-body').textContent=bodyOn()?`${src($('dt-body-src').value)}${$('dt-body-src').value==='ai'?' · '+$('dt-body-min').value+'–'+$('dt-body-max').value+' ký tự':''} · cỡ ${$('body_size').value}px`:'tắt';
 if(on()){const n=v=>Number($(v)?.value)||0;$('sum-frame').textContent=[n('dub-trim-start')||n('dub-trim-end')?`cắt ${n('dub-trim-start')}s đầu · ${n('dub-trim-end')}s cuối`:'không cắt',`video ${$('video_width').value}×${$('video_height').value}`].join(' · ')}
 $('dub-export-note').textContent='Video lưu vào thư mục xuất (nút thông số xuất ở góc trên) với tên “…-long-tieng.mp4”.';
 $('dub-drop').textContent='Kéo thả video hoặc cả thư mục vào đây · .srt cùng tên sẽ bỏ qua bước nhận diện';
 const ai=(titleOn()&&$('dt-title-src').value==='ai')||(bodyOn()&&$('dt-body-src').value==='ai');aiBox.hidden=!ai;
 $('dt-ai-note').textContent=ai?'Tiêu đề và nội dung do AI viết trong cùng lần gọi dịch (không thêm lượt gọi). Chế độ "ai33 tự lồng tiếng" cần thêm 1 lần gọi ngắn.':''}
for(const id of ['dt-title-src','dt-body-src','dt-title-chars','dt-body-min','dt-body-max','dt-design-on','dt-title-on','dt-body-on','dt-review'])$(id).addEventListener('change',()=>{layout();designPreview();api.remember();api.labels();labels();api.preview()});
document.addEventListener('design-changed',()=>{if(!$('view-dub').hidden){labels();clearTimeout(labels.t);labels.t=setTimeout(()=>api.remember(),400)}});

// ---- one tab: the old "Lồng tiếng" and timeline entries are gone; anything that opened the editor opens this page
$('nav-dub').hidden=true;$('nav-editor').textContent='Dựng & lồng tiếng';
const view0=window.switchView;window.switchView=v=>view0(v==='editor'?'dub':v);
function mark(){$('nav-editor').classList.toggle('active',!$('view-dub').hidden);$('nav-dub').classList.remove('active')}
let started=false;
function enter(){if(!started){started=true;api.load();api.loadPresets();api.refresh();api.draw()}
 layout();moveIn();window.switchView('dub');mark();labels();api.preview()}
$('nav-editor').onclick=()=>enter();$('nav-dub').onclick=()=>enter();
document.addEventListener('view-change',e=>{if(e.detail==='editor')setTimeout(enter);setTimeout(mark)});

// ---- design templates saved earlier (old editor) in the template list: they set the design only
async function addTemplates(){const pick=$('dub-preset');pick.querySelector('optgroup.dt-old')?.remove();
 try{const t=(await request('/library/templates')).items;if(!t.length)return;const g=el('optgroup',{className:'dt-old',label:'Thiết kế đã lưu trước đây'});for(const x of t)g.append(new Option(x.name,'tpl:'+x.id));pick.append(g)}catch{}}
$('dub-preset').addEventListener('change',async e=>{const v=$('dub-preset').value;if(!v.startsWith('tpl:'))return;e.stopImmediatePropagation();
 try{const r=await request('/library/templates/'+v.slice(4));studio.apply(r.data.design);studio.schedule();api.remember();api.say(`Đã áp dụng thiết kế "${r.name}". Bấm 💾 Lưu mẫu để lưu kèm mọi thông số.`)}catch(err){api.say(err.message)}},true);
new MutationObserver(()=>{if(!$('dub-preset').querySelector('optgroup.dt-old'))addTemplates()}).observe($('dub-preset'),{childList:true});

window.dubProfile={name:'dub',extend,apply,preview,labels,previewJob};
// the start page; its saved settings load once the dubbing defaults are known
document.addEventListener('dub-ready',()=>enter(),{once:true});
const ready=setInterval(()=>{if(document.querySelector('#dub-style option')){clearInterval(ready);document.dispatchEvent(new Event('dub-ready'))}},100);
})();
