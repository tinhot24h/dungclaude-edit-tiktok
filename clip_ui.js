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

note(voice,'Bấm thanh MP3 trên timeline để mở bảng này. Kéo thân MP3 để đổi thời điểm vào. Đổi file ở cột trái hoặc tab Thư viện.');
voice.append(heads[1],$('audio-track'));
group(voice,'CẮT & TỐC ĐỘ');grid(voice,['audio-start','audio-end','audio-speed','audio-offset']);
group(voice,'ÂM LƯỢNG & CÁCH XUẤT');grid(voice,['audio-volume']);
voice.append(details.querySelector('.two-col'));
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
