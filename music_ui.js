'use strict';
// Royalty-free music browser (Openverse: CC0 / public domain / CC BY / CC BY-SA, commercial use and edits allowed).
// Preview plays straight from the provider; "+ Nhạc nền" imports the track into the MP3 library and puts it on the music track.
(()=>{
const edit=window.editorState,pane=$('pane-sound');
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const json=(url,body)=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const time=t=>t==null?'--:--':`${Math.floor(t/60)}:${String(Math.round(t%60)).padStart(2,'0')}`;
const MOODS=[['Vui tươi','happy upbeat'],['Nhẹ nhàng','calm soft'],['Sôi động','energetic'],['Lofi','lofi'],['Piano','piano'],['Acoustic','acoustic guitar'],['Quảng cáo','corporate'],['Điện ảnh','cinematic'],['Điện tử','electronic']];
let page=1,query='',rows=[],playing='',busy=false;

const box=el('div',{className:'free-music',id:'free-music'});
box.innerHTML=`<div class="pane-subtitle">Nhạc miễn phí bản quyền</div>
<div class="fm-search"><input id="fm-query" type="search" maxlength="100" placeholder="Tìm nhạc: happy, piano, lofi…"><select id="fm-category" aria-label="Loại âm thanh"><option value="music">Nhạc</option><option value="sound_effect">Hiệu ứng</option><option value="all">Tất cả</option></select><button type="button" id="fm-go" class="primary-action small-action">Tìm</button></div>
<div class="fm-moods" id="fm-moods"></div>
<div id="fm-status" class="helper" role="status"></div>
<div id="fm-list" class="fm-list"></div>
<button type="button" id="fm-more" class="outline-action small-action" hidden>Xem thêm</button>
<p class="helper fm-legal">Nguồn: Openverse (Jamendo, Freesound, Wikimedia, ccMixter…). Chỉ hiện nhạc có giấy phép cho phép dùng thương mại và chỉnh sửa. Bản <b>CC BY</b> cần ghi tên tác giả trong mô tả video. Kiểm tra lại giấy phép ở trang nguồn trước khi đăng.</p>
<audio id="fm-player" preload="none"></audio>`;
const audioBlock=pane.querySelector('.source-audio');if(audioBlock)audioBlock.after(box);else pane.append(box);
for(const[label,q]of MOODS){const b=el('button',{type:'button',className:'chip-button',textContent:label});b.onclick=()=>{$('fm-query').value=q;search(true)};$('fm-moods').append(b)}
const player=$('fm-player');player.onended=()=>{playing='';draw()};player.onerror=()=>{if(playing){$('fm-status').textContent='Không phát thử được bản này (máy chủ nguồn chặn hoặc hết hạn). Vẫn có thể thêm để tải về.';playing='';draw()}};

async function search(fresh){if(busy)return;busy=true;if(fresh){page=1;query=$('fm-query').value.trim();rows=[]}$('fm-status').textContent='Đang tìm trên Openverse…';$('fm-go').disabled=true;
 try{const d=await json('/music/search',{q:query,page,category:$('fm-category').value});rows=fresh?d.results:[...rows,...d.results];$('fm-more').hidden=page>=d.pages||!d.results.length;
  $('fm-status').textContent=rows.length?`${d.count>rows.length?'Khoảng '+d.count.toLocaleString('vi-VN'):rows.length} kết quả · bấm ▶ để nghe thử`:'Không có kết quả. Thử từ khóa tiếng Anh như "happy", "piano", "lofi".';draw()}
 catch(e){$('fm-status').textContent=e.message}finally{busy=false;$('fm-go').disabled=false}}
function draw(){$('fm-list').replaceChildren(...rows.map(r=>{const play=el('button',{type:'button',className:'fm-play'+(playing===r.id?' on':''),textContent:playing===r.id?'❚❚':'▶',title:'Nghe thử',ariaLabel:'Nghe thử '+r.title});
  play.onclick=()=>{if(playing===r.id){player.pause();playing=''}else{player.src=r.preview;player.play().catch(()=>{});playing=r.id}draw()};
  const add=el('button',{type:'button',className:'outline-action small-action fm-add',textContent:'＋ Nhạc nền',title:'Tải về thư viện và đặt làm nhạc nền'});add.onclick=()=>use(r,add);
  const meta=el('small',{},el('span',{textContent:[r.creator,time(r.duration),r.source].filter(Boolean).join(' · ')}),el('span',{className:'fm-license'+(r.attribution_required?' credit':''),textContent:r.license_label.split(' ·')[0],title:r.license_label}));
  const info=el('div',{className:'fm-info'},el('strong',{textContent:r.title,title:r.title}),meta);
  if(r.landing)info.append(el('a',{href:r.landing,target:'_blank',rel:'noopener noreferrer',className:'fm-link',textContent:'Trang nguồn ↗'}));
  return el('div',{className:'fm-row'},play,info,add)}))}
async function use(r,button){button.disabled=true;button.textContent='Đang tải…';player.pause();playing='';
 try{const a=await json('/music/import',{id:r.id});await edit.useMusic(a.asset_id);window.mediaBin?.reload();document.dispatchEvent(new Event('audio-created'));setTimeout(()=>window.appHistory?.checkpoint(),200);
  $('fm-status').textContent=`Đã thêm "${a.name}" làm nhạc nền.`+(a.attribution_required?' Nhớ ghi nguồn trong mô tả video (bảng Nhạc nền có nút sao chép).':'');button.textContent='✓ Đã thêm'}
 catch(e){$('fm-status').textContent=e.message;button.textContent='＋ Nhạc nền';button.disabled=false}draw()}
$('fm-go').onclick=()=>search(true);$('fm-query').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();search(true)}};$('fm-more').onclick=()=>{page++;search(false)};
$('fm-category').onchange=()=>rows.length&&search(true);
document.addEventListener('view-change',()=>{player.pause();playing='';draw()});

// ---- attribution of the current background track, shown in the music clip properties
const credit=el('div',{className:'music-credit',id:'music-credit',hidden:true},el('div',{className:'group-label',textContent:'GHI NGUỒN NHẠC'}),el('p',{id:'music-credit-text',className:'helper'}),el('div',{className:'result-actions'}));
const copy=el('button',{type:'button',className:'outline-action small-action',textContent:'Sao chép ghi nguồn'});credit.lastChild.append(copy);
$('section-clip-music')?.append(credit);
let current='';
function showCredit(){const id=edit.media().music_asset_id,a=edit.assets().find(x=>x.asset_id===id);current=a?.credit?`Nhạc: ${a.credit}${a.source_url?' — '+a.source_url:''}`:'';credit.hidden=!current;$('music-credit-text').textContent=current?`${current}${a.license?' · '+a.license:''}`:''}
copy.onclick=async()=>{try{await navigator.clipboard.writeText(current);copy.textContent='✓ Đã sao chép'}catch{prompt('Sao chép dòng ghi nguồn:',current)}setTimeout(()=>{copy.textContent='Sao chép ghi nguồn'},1500)};
document.addEventListener('timeline-refresh',showCredit);document.addEventListener('audio-created',()=>setTimeout(showCredit,500));showCredit();
})();
