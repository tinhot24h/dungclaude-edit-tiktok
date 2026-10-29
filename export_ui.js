'use strict';
// Export: compact settings badge in the header (resolution · fps · quality · encoder · folder in one popover),
// progress card + floating toast while rendering, and a sound/notification when the video is finished.
(()=>{
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const SIZES={'720':[720,1280],'1080':[1080,1920],'2k':[1440,2560],'4k':[2160,3840]};
const pane=$('pane-export');

// ---- settings popover, opened from the header badge or the export pane
const old=document.querySelector('.canvas-badge');
const badge=el('button',{type:'button',id:'export-badge',className:'export-badge',title:'Thông số video xuất'});badge.setAttribute('aria-haspopup','dialog');badge.setAttribute('aria-expanded','false');
old?old.replaceWith(badge):document.querySelector('.app-header').append(badge);
const pop=el('div',{id:'export-pop',className:'export-pop',hidden:true,role:'dialog',ariaLabel:'Thông số video xuất'});
pop.innerHTML='<div class="export-pop-head"><strong>Thông số video xuất</strong><button type="button" id="export-pop-close" class="icon-button" aria-label="Đóng">✕</button></div><div class="export-pop-body cc-panel"></div>';
document.body.append(pop);
// grouped like the other panels: Video · Âm thanh · Lưu file · Thông tin file (metadata, with its own switch)
const body=pop.querySelector('.export-pop-body');
const group=(title,...nodes)=>{const g=el('div',{className:'cc-group'},el('div',{className:'cc-head'},title));g.append(...nodes);body.append(g);return g};
const row=(text,...nodes)=>el('div',{className:'cc-row'},el('span',{className:'cc-label',textContent:text}),el('div',{className:'cc-items'},...nodes));
const take=id=>{document.querySelector(`label[for=${id}]`)?.remove();return $(id)};
const note=$('encoder-note'),help=note.nextElementSibling;
group('Video',row('Độ phân giải',take('resolution')),row('Khung hình',take('fps')),row('Chất lượng',take('quality')),row('Bộ mã hóa',take('encoder')),note,...(help?.classList.contains('helper')?[help]:[]));
group('Âm thanh',row('Âm lượng tổng',take('loudness')));
$('fps').closest('.two-col')?.remove();
group('Lưu file',document.querySelector('.output-folder'));
// Thông tin file: the user's own details written into every exported MP4 (title / tags come from the AI per video)
const input=(id,ph,max=300)=>el('input',{type:'text',id,maxLength:max,spellcheck:false,placeholder:ph});
const metaOn=el('input',{type:'checkbox',id:'meta-on',checked:true,hidden:true}),strip=el('input',{type:'checkbox',id:'meta-strip',checked:true});
const rating=el('input',{type:'hidden',id:'meta-rating',value:'0'});
const stars=el('div',{className:'cc-seg meta-stars'},...[1,2,3,4,5].map(n=>{const b=el('button',{type:'button',textContent:'★',title:n+' sao'});b.onclick=()=>{rating.value=String(+rating.value===n?0:n);drawStars();rating.dispatchEvent(new Event('change',{bubbles:true}))};return b}));
function drawStars(){[...stars.children].forEach((b,i)=>b.classList.toggle('on',i<+rating.value));starNote.textContent=+rating.value?rating.value+' sao':'không đánh giá'}
const starNote=el('small',{className:'helper'});
const toggle=el('button',{type:'button',className:'meta-switch',title:'Bật/tắt ghi thông tin file'},el('i'));
const fields=el('div',{className:'meta-fields'},el('label',{className:'check-row'},strip,document.createTextNode(' Không chép metadata của video gốc (link, thiết bị, tiêu đề cũ)')),
 row('Tác giả',input('meta-author','Tên bạn hoặc tên kênh')),row('Link kênh',input('meta-url','https://www.tiktok.com/@ten_kenh')),
 row('Nhà phát hành',input('meta-publisher','Tên shop / kênh (không bắt buộc)')),row('Bản quyền',input('meta-copyright','© 2026 Tên kênh')),
 row('Đánh giá',stars,starNote,rating),
 row('Ngày tạo',el('span',{className:'helper',textContent:'lùi'}),el('input',{type:'number',id:'meta-back-min',min:0,max:365,value:5,'aria-label':'Lùi ít nhất (ngày)'}),el('span',{className:'helper',textContent:'–'}),el('input',{type:'number',id:'meta-back-max',min:0,max:365,value:7,'aria-label':'Lùi nhiều nhất (ngày)'}),el('span',{className:'helper',textContent:'ngày'})),
 el('p',{className:'helper',id:'meta-date-note'}),
 el('p',{className:'helper',textContent:'Mỗi video tự có: Tiêu đề = tiêu đề AI viết, Tags = từ khóa AI viết (cùng lần dịch), ngày tạo theo ô Ngày tạo. Tags, đánh giá, link kênh, nhà phát hành được Windows ghi sau khi xuất (tự cài pywin32 lần đầu, cần Internet).'}));
const meta=group('Thông tin file (metadata)',fields);meta.querySelector('.cc-head').append(toggle,metaOn);meta.id='meta-group';
function drawMeta(){toggle.classList.toggle('on',metaOn.checked);toggle.setAttribute('aria-pressed',String(metaOn.checked));fields.classList.toggle('off',!metaOn.checked);for(const e of fields.querySelectorAll('input,button'))e.disabled=!metaOn.checked}
toggle.onclick=()=>{metaOn.checked=!metaOn.checked;drawMeta();metaOn.dispatchEvent(new Event('change',{bubbles:true}))};
// example with today's date: 5–7 → each video gets one random day 5, 6 or 7 days before the export
function drawDate(){const lo=Math.max(0,+$('meta-back-min').value||0),hi=Math.max(lo,+$('meta-back-max').value||0),d=n=>{const t=new Date();t.setDate(t.getDate()-n);return t.toLocaleDateString('vi-VN')};
 $('meta-date-note').textContent=hi?`Mỗi video lấy ngẫu nhiên một ngày, ví dụ hôm nay ${new Date().toLocaleDateString('vi-VN')} → ${lo===hi?d(lo):d(hi)+' đến '+d(lo)}. Xuất lại giữ nguyên ngày đã chọn.`:'0 – 0: ngày tạo = ngày xuất.'}
for(const id of ['meta-back-min','meta-back-max'])$(id).addEventListener('input',drawDate);
window.exportMetaRefresh=()=>{drawMeta();drawStars();drawDate()};drawMeta();drawStars();drawDate();
const summary=el('button',{type:'button',id:'export-summary',className:'export-summary',title:'Chỉnh thông số xuất'});pane.querySelector('.pane-title').after(summary);
function text(){const [w,h]=SIZES[$('resolution').value]||[1080,1920],fps=$('fps').value,q=$('quality').value==='high'?'Chất lượng cao':'Tiêu chuẩn',enc=$('encoder').selectedOptions[0]?.textContent.replace(/\s*\(.*\)/,'')||'';
 badge.innerHTML='';badge.append(el('span',{textContent:`${w} × ${h}`}),el('i'),el('span',{textContent:`${fps} FPS`}),el('b',{textContent:'⚙'}));badge.title=`Thông số xuất: ${w}×${h} · ${fps} fps · ${q} · ${enc} — bấm để chỉnh`;
 summary.innerHTML='';summary.append(el('span',{className:'export-summary-main',textContent:`${w} × ${h} · ${fps} FPS`}),el('small',{textContent:`${q} · ${enc}${$('loudness').value==='tiktok'?' · −14 LUFS':''}`}),el('b',{textContent:'Chỉnh ›'}))}
function place(anchor){const r=anchor.getBoundingClientRect(),w=Math.min(420,innerWidth-24);pop.style.width=w+'px';pop.style.left=Math.max(12,Math.min(innerWidth-w-12,r.right-w))+'px';pop.style.top=Math.min(innerHeight-60,r.bottom+8)+'px'}
function open(anchor){place(anchor);pop.hidden=false;badge.setAttribute('aria-expanded','true');$('resolution').focus()}
function close(){if(pop.hidden)return;pop.hidden=true;badge.setAttribute('aria-expanded','false')}
badge.onclick=()=>pop.hidden?open(badge):close();summary.onclick=()=>pop.hidden?open(summary):close();$('export-pop-close').onclick=close;
document.addEventListener('pointerdown',e=>{if(!pop.hidden&&!pop.contains(e.target)&&e.target!==badge&&e.target!==summary&&!badge.contains(e.target)&&!summary.contains(e.target))close()},true);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!pop.hidden){e.stopPropagation();close()}},true);
addEventListener('resize',()=>{if(!pop.hidden)close()});
for(const id of ['resolution','fps','quality','encoder','loudness'])$(id).addEventListener('change',text);
new MutationObserver(text).observe($('encoder'),{childList:true});text();

// ---- progress card in the export pane, floating toast everywhere, progress inside the header export button
const card=el('div',{id:'export-card',className:'export-card',hidden:true});
card.innerHTML='<div class="export-card-top"><strong id="export-card-title">Đang xuất video</strong><span id="export-card-pct">0%</span></div><div class="export-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i></i></div><small id="export-card-meta"></small>';
$('submit').before(card);
const toast=el('div',{id:'export-toast',className:'export-toast',hidden:true,role:'status'});
toast.innerHTML='<div class="export-toast-icon" aria-hidden="true"></div><div class="export-toast-body"><strong id="export-toast-title"></strong><div class="export-bar"><i></i></div><small id="export-toast-meta"></small><div class="export-toast-actions"></div></div><button type="button" id="export-toast-close" class="icon-button" aria-label="Đóng thông báo">✕</button>';
document.body.append(toast);
const base=document.title;let hideTimer;
$('export-toast-close').onclick=()=>{toast.hidden=true};
function bars(p){for(const b of document.querySelectorAll('.export-bar')){b.querySelector('i').style.width=p+'%';b.setAttribute('aria-valuenow',String(p))}const pb=$('pb-export');if(pb){pb.style.setProperty('--progress',p+'%');pb.classList.add('exporting');pb.textContent=`Đang xuất ${p}%`}}
function actions(...buttons){toast.querySelector('.export-toast-actions').replaceChildren(...buttons)}
function button(textContent,onclick,primary=false){const b=el('button',{type:'button',className:(primary?'primary-action':'outline-action')+' small-action',textContent});b.onclick=onclick;return b}
function show(state){clearTimeout(hideTimer);toast.hidden=false;toast.dataset.state=state}
document.addEventListener('export-progress',e=>{const d=e.detail,p=d.state==='done'?100:Math.max(0,Math.min(100,d.progress||0));
 const title=d.state==='queued'?'Đang chờ lượt xuất…':d.state==='cancelling'?'Đang hủy xuất…':d.state==='preparing'?'Đang chuẩn bị dựng video…':`Đang xuất ${d.label||''}`;
 const meta=[d.state==='rendering'?(d.eta_text?'còn khoảng '+d.eta_text:'đang ước tính thời gian…'):'',d.encoder&&d.encoder!=='cpu'?'card đồ họa':d.state==='rendering'?'CPU':'',d.note||''].filter(Boolean).join(' · ');
 card.hidden=false;card.dataset.state='busy';$('export-card-title').textContent=title;$('export-card-pct').textContent=p+'%';$('export-card-meta').textContent=meta;
 show('busy');$('export-toast-title').textContent=`${title} · ${p}%`;$('export-toast-meta').textContent=(d.name?d.name+' · ':'')+meta;actions(button('Hủy xuất',()=>$('cancel-export').click()));bars(p);document.title=`(${p}%) ${base}`});
function finish(){document.title=base;const pb=$('pb-export');if(pb){pb.classList.remove('exporting');pb.style.removeProperty('--progress');pb.textContent='Xuất bản ↗'}}
document.addEventListener('export-done',e=>{const d=e.detail;finish();bars(100);$('pb-export')&&($('pb-export').textContent='Xuất bản ↗');
 card.dataset.state='done';$('export-card-title').textContent='Đã xuất xong';$('export-card-pct').textContent='100%';$('export-card-meta').textContent=d.saved_path?'Đã lưu: '+d.saved_path:'Bấm “Tải video về máy” bên dưới.';
 show('done');$('export-toast-title').textContent='Video đã xuất xong ✓';$('export-toast-meta').textContent=`${d.plan.width}×${d.plan.height} · ${d.duration.toFixed(1)}s · mất ${d.took}${d.saved_path?' · '+d.saved_path:''}${d.save_error?' · '+d.save_error:''}`;
 actions(...(d.saved_path?[button('Mở thư mục',()=>$('open-folder').click(),true)]:[]),button('Tải về',()=>{const a=el('a',{href:d.href,download:(d.name||'review-video')+'.mp4'});document.body.append(a);a.click();a.remove()},!d.saved_path),button('Đóng',()=>{toast.hidden=true}));
 chime();flash('✓ Đã xuất xong')});
document.addEventListener('export-error',e=>{finish();card.dataset.state='error';card.hidden=false;$('export-card-title').textContent='Xuất video lỗi';$('export-card-meta').textContent=e.detail.error;
 show('error');$('export-toast-title').textContent='Xuất video lỗi';$('export-toast-meta').textContent=e.detail.error;actions(button('Đóng',()=>{toast.hidden=true}));chime(true)});
document.addEventListener('export-cancelled',()=>{finish();card.hidden=true;show('cancelled');$('export-toast-title').textContent='Đã hủy xuất video';$('export-toast-meta').textContent='Bạn có thể chỉnh sửa và xuất lại.';actions();hideTimer=setTimeout(()=>{toast.hidden=true},4000)});
// Two soft notes when done (one low note on error); browsers allow it because the export started from a click.
function chime(error=false){try{const AC=window.AudioContext||window.webkitAudioContext;if(!AC)return;const ctx=new AC(),now=ctx.currentTime;(error?[330]:[660,990]).forEach((f,i)=>{const o=ctx.createOscillator(),g=ctx.createGain();o.frequency.value=f;o.type='sine';g.gain.setValueAtTime(0,now+i*.16);g.gain.linearRampToValueAtTime(.18,now+i*.16+.02);g.gain.exponentialRampToValueAtTime(.001,now+i*.16+.5);o.connect(g).connect(ctx.destination);o.start(now+i*.16);o.stop(now+i*.16+.55)});setTimeout(()=>ctx.close(),1200)}catch{}}
function flash(label){if(!document.hidden)return;let on=true;const t=setInterval(()=>{document.title=on?label:base;on=!on},1000);const stop=()=>{clearInterval(t);document.title=base;removeEventListener('focus',stop)};addEventListener('focus',stop)}
})();
