'use strict';
// Clip properties: clicking a clip on the timeline opens its settings in the properties column.
(()=>{
const parent=id=>$(id).closest('label');
const note=(box,text)=>{const p=document.createElement('p');p.className='helper';p.textContent=text;box.append(p)};
const group=(box,text)=>{const d=document.createElement('div');d.className='group-label';d.textContent=text;box.append(d)};
const grid=(box,ids)=>{const g=document.createElement('div');g.className='edit-grid';for(const id of ids)g.append(parent(id));box.append(g);return g};
const details=document.querySelector('.numeric-timeline'),heads=details.querySelectorAll('.track-head');

const video=section('clip-video','Clip video'),voice=section('clip-audio','Giọng đọc'),music=section('clip-music','Nhạc nền');
for(const[box,key]of [[video,'video'],[voice,'audio'],[music,'music']])box.dataset.clip=key;

note(video,'Bấm thanh video trên timeline để mở bảng này. Kéo hai mép trên timeline hoặc nhập số chính xác.');
video.append(heads[0],$('video-track'));
group(video,'CẮT & TỐC ĐỘ');grid(video,['video-start','video-end','video-speed']);
group(video,'ÂM THANH GỐC');grid(video,['original-volume']);
const fitVideo=document.createElement('div');fitVideo.className='result-actions';fitVideo.append($('fit-video-to-audio'));video.append(fitVideo);
note(video,'Tách/xóa đoạn: đặt đầu phát rồi bấm ✂ Tách (S), bấm đoạn và Delete. Hiệu ứng phóng to từ từ nằm ở tab Video.');
// Speed of the pieces selected on the timeline (each piece keeps its own speed, multiplied by the track speed above).
group(video,'TỐC ĐỘ ĐOẠN ĐANG CHỌN');
const speedBox=document.createElement('div');speedBox.className='piece-speed';
speedBox.innerHTML='<p class="helper" id="piece-speed-note">Bấm một đoạn video trên timeline (Shift+bấm để chọn nhiều). Tách đoạn bằng ✂ hoặc phím S.</p><div class="range-row"><input id="piece-speed-range" type="range" min="0.25" max="4" step="0.05" value="1" aria-label="Tốc độ đoạn"><div class="numeric-shell"><input id="piece-speed" type="number" min="0.25" max="4" step="0.05" value="1"><span class="unit">×</span></div></div><div class="speed-presets"></div><button type="button" id="piece-speed-all" class="outline-action small-action">Áp dụng cho mọi đoạn</button>';
video.append(speedBox);
for(const k of [0.5,0.75,1,1.25,1.5,2,3]){const b=document.createElement('button');b.type='button';b.className='chip-button';b.textContent=k+'×';b.onclick=()=>window.timelineActions.pieceSpeed(k);speedBox.querySelector('.speed-presets').append(b)}
let chosen=[];
const setSpeed=(v,all)=>{const k=Number(v);if(Number.isFinite(k)&&k>=.25&&k<=4)window.timelineActions.pieceSpeed(k,all)};
$('piece-speed-range').oninput=()=>{$('piece-speed').value=$('piece-speed-range').value};$('piece-speed-range').onchange=()=>setSpeed($('piece-speed-range').value);
$('piece-speed').onchange=()=>setSpeed($('piece-speed').value);$('piece-speed-all').onclick=()=>setSpeed($('piece-speed').value,true);
document.addEventListener('piece-select',e=>{chosen=e.detail;const on=chosen.length>0;for(const el of speedBox.querySelectorAll('input,.speed-presets button'))el.disabled=!on;
 if(on){const k=chosen[0].k;$('piece-speed').value=k;$('piece-speed-range').value=k;$('piece-speed-note').textContent=chosen.length>1?`${chosen.length} đoạn đang chọn · tốc độ ${chosen.map(x=>x.k+'×').join(', ')}`:`Đoạn ${(chosen[0].b-chosen[0].a).toFixed(2)}s nguồn → ${(chosen[0].end-chosen[0].start).toFixed(2)}s trên video · ${k}×`}
 else $('piece-speed-note').textContent='Bấm một đoạn video trên timeline (Shift+bấm để chọn nhiều). Tách đoạn bằng ✂ hoặc phím S.'});

note(voice,'Bấm thanh MP3 trên timeline để mở bảng này. Kéo thân MP3 để đổi thời điểm vào. Đổi file ở cột trái hoặc tab Thư viện.');
voice.append(heads[1],$('audio-track'));
group(voice,'CẮT & TỐC ĐỘ');grid(voice,['audio-start','audio-end','audio-speed','audio-offset']);
group(voice,'ÂM LƯỢNG & CÁCH XUẤT');grid(voice,['audio-volume']);
group(voice,'KHỚP THỜI LƯỢNG VỚI VIDEO');voice.append(details.querySelector('.fit-mode-box'),details.querySelector('.two-col'));
const fitAudio=document.createElement('div');fitAudio.className='result-actions';fitAudio.append($('fit-audio-to-video'));voice.append(fitAudio);

note(music,'Bấm thanh nhạc nền trên timeline để mở bảng này. Nhạc chạy suốt video xuất và tự lặp nếu bật.');
music.append(document.querySelector('.music-block'));
details.hidden=true;

const labels={video:'VIDEO',audio:'GIỌNG ĐỌC',music:'NHẠC NỀN'};
function open(kind){activate('clip-'+kind);if(kind!=='music')$('tl-selected').value=kind;$('settings-title').textContent='Thuộc tính · '+labels[kind];document.querySelector('.settings').scrollTop=0}
document.addEventListener('timeline-select',e=>open(e.detail));
for(const b of document.querySelectorAll('#tabs [role=tab]'))b.addEventListener('click',()=>{const clip=b.id.startsWith('tab-clip-');$('settings-title').textContent=clip?'Thuộc tính · '+labels[b.id.slice(9)]:'Thuộc tính · thiết kế';for(const id of ['tl-video','tl-audio','tl-music'])if(!clip)$(id).classList.remove('picked')});
$('tl-numbers').onclick=()=>open($('tl-selected').value);
})();
