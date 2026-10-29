'use strict';
// Export settings of the dubbing queue: a badge in the header opens one popover with every export setting
// (video, sound, output folder, file info).
(()=>{
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const SIZES={'720':[720,1280],'1080':[1080,1920],'2k':[1440,2560],'4k':[2160,3840]};

// ---- settings popover, opened from the header badge (or "Thông số xuất ›" in the dubbing tab)
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
// "Theo video gốc": the dubbing queue keeps each source's own size (or 1080 wide for a 9:16 frame)
if(![...$('resolution').options].some(o=>o.value==='source'))$('resolution').append(new Option('Theo video gốc','source'));
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
 row('Tác giả',input('meta-author','Tên kênh hoặc link kênh')),el('small',{className:'meta-map',textContent:'→ Directors, Producers, Writers'}),
 row('Link kênh',input('meta-url','https://www.tiktok.com/@ten_kenh')),el('small',{className:'meta-map',textContent:'→ Author URL, Promotion URL (và Content provider nếu để trống Nhà phát hành)'}),
 row('Nhà phát hành',input('meta-publisher','Tên shop / kênh (không bắt buộc)')),el('small',{className:'meta-map',textContent:'→ Publisher, Content provider'}),
 row('Bản quyền',input('meta-copyright','© 2026 Tên kênh')),
 row('Đánh giá',stars,starNote,rating),
 row('Ngày tạo',el('span',{className:'helper',textContent:'lùi'}),el('input',{type:'number',id:'meta-back-min',min:0,max:365,value:5,'aria-label':'Lùi ít nhất (ngày)'}),el('span',{className:'helper',textContent:'–'}),el('input',{type:'number',id:'meta-back-max',min:0,max:365,value:7,'aria-label':'Lùi nhiều nhất (ngày)'}),el('span',{className:'helper',textContent:'ngày'})),
 el('p',{className:'helper',id:'meta-date-note'}),
 el('p',{className:'helper',textContent:'Không ghi nhóm Media (Contributing artists, Year) và Encoded by. Mỗi video tự có: Tiêu đề = tiêu đề AI viết, Tags = từ khóa AI viết (cùng lần dịch), ngày tạo (Media created) theo ô Ngày tạo. Tags, đánh giá, link kênh, nhà phát hành được Windows ghi sau khi xuất (tự cài pywin32 lần đầu, cần Internet).'}));
const meta=group('Thông tin file (metadata)',fields);meta.querySelector('.cc-head').append(toggle,metaOn);meta.id='meta-group';
function drawMeta(){toggle.classList.toggle('on',metaOn.checked);toggle.setAttribute('aria-pressed',String(metaOn.checked));fields.classList.toggle('off',!metaOn.checked);for(const e of fields.querySelectorAll('input,button'))e.disabled=!metaOn.checked}
toggle.onclick=()=>{metaOn.checked=!metaOn.checked;drawMeta();metaOn.dispatchEvent(new Event('change',{bubbles:true}))};
// example with today's date: 5–7 → each video gets one random day 5, 6 or 7 days before the export
function drawDate(){const lo=Math.max(0,+$('meta-back-min').value||0),hi=Math.max(lo,+$('meta-back-max').value||0),d=n=>{const t=new Date();t.setDate(t.getDate()-n);return t.toLocaleDateString('vi-VN')};
 $('meta-date-note').textContent=hi?`Mỗi video lấy ngẫu nhiên một ngày, ví dụ hôm nay ${new Date().toLocaleDateString('vi-VN')} → ${lo===hi?d(lo):d(hi)+' đến '+d(lo)}. Xuất lại giữ nguyên ngày đã chọn.`:'0 – 0: ngày tạo = ngày xuất.'}
for(const id of ['meta-back-min','meta-back-max'])$(id).addEventListener('input',drawDate);
window.exportMetaRefresh=()=>{drawMeta();drawStars();drawDate()};drawMeta();drawStars();drawDate();
function text(){const [w,h]=SIZES[$('resolution').value]||[1080,1920],fps=$('fps').value,q=$('quality').value==='high'?'Chất lượng cao':'Tiêu chuẩn',enc=$('encoder').selectedOptions[0]?.textContent.replace(/\s*\(.*\)/,'')||'';
 const size=$('resolution').value==='source'?'Theo video gốc':`${w} × ${h}`;badge.innerHTML='';badge.append(el('span',{textContent:size}),el('i'),el('span',{textContent:`${fps} FPS`}),el('b',{textContent:'⚙'}));badge.title=`Thông số xuất: ${size} · ${fps} fps · ${q} · ${enc} — bấm để chỉnh`;}
function place(anchor){const r=anchor.getBoundingClientRect(),w=Math.min(470,innerWidth-24);pop.style.width=w+'px';pop.style.left=Math.max(12,Math.min(innerWidth-w-12,r.right-w))+'px';pop.style.top=Math.min(innerHeight-60,r.bottom+8)+'px'}
function open(anchor){place(anchor);pop.hidden=false;badge.setAttribute('aria-expanded','true');$('resolution').focus()}
function close(){if(pop.hidden)return;pop.hidden=true;badge.setAttribute('aria-expanded','false')}
badge.onclick=()=>pop.hidden?open(badge):close();$('export-pop-close').onclick=close;
document.addEventListener('pointerdown',e=>{if(!pop.hidden&&!pop.contains(e.target)&&e.target!==badge&&!badge.contains(e.target)&&!e.target.closest?.('#dub-out-edit'))close()},true);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!pop.hidden){e.stopPropagation();close()}},true);
addEventListener('resize',()=>{if(!pop.hidden)close()});
for(const id of ['resolution','fps','quality','encoder','loudness'])$(id).addEventListener('change',text);
new MutationObserver(text).observe($('encoder'),{childList:true});text();

})();
