'use strict';
// Global undo/redo, keyboard shortcuts, snap guides and the TikTok safe zone overlay.
(()=>{
const design=window.studioApi,edit=window.editorState,timeline=()=>window.timelineActions,api=window.editorTimeline;
let stack=[],cursor=-1,timer,applying=false;
function snapshot(){return JSON.stringify({design:design.snapshot(),edit:edit.snapshot()})}
function buttons(){$('tl-undo').disabled=cursor<=0;$('tl-redo').disabled=cursor>=stack.length-1}
function checkpoint(){if(applying)return;clearTimeout(timer);const value=snapshot();if(stack[cursor]===value)return;stack=stack.slice(0,cursor+1);stack.push(value);if(stack.length>100)stack.shift();cursor=stack.length-1;buttons()}
function later(ms=0){if(applying)return;clearTimeout(timer);timer=setTimeout(checkpoint,ms)}
function go(delta){checkpoint();const to=cursor+delta;if(to<0||to>=stack.length)return;cursor=to;applying=true;try{const v=JSON.parse(stack[cursor]);design.apply(v.design);edit.apply(v.edit)}finally{applying=false}document.dispatchEvent(new Event('history-applied'));buttons();$('status').textContent=delta<0?'Đã hoàn tác.':'Đã làm lại.'}
window.appHistory={checkpoint,later,undo:()=>go(-1),redo:()=>go(1),reset:()=>{stack=[];cursor=-1;checkpoint()}};
document.addEventListener('change',e=>{if(e.target.closest('#view-editor')&&!e.target.closest('#visual-timeline'))later(0)},true);
for(const id of ['title','body','preview-text-editor'])$(id).addEventListener('input',()=>later(900));
document.addEventListener('layer-moved',()=>later(0));
setTimeout(checkpoint,1500);

// TikTok covers the top bar, the right-hand buttons and the caption at the bottom (1080×1920 guide scaled to 720×1280).
const SAFE={left:40,right:627,top:87,bottom:1027};
const zone=document.createElement('div');zone.id='safe-zone';zone.setAttribute('aria-hidden','true');zone.innerHTML='<div class="sz sz-top">Thanh trên TikTok</div><div class="sz sz-right">Nút thả tim / bình luận</div><div class="sz sz-bottom">Tên kênh · caption · thanh nhạc</div><div class="sz-frame"></div>';
const vertical=document.createElement('div'),horizontal=document.createElement('div');vertical.className='guide guide-v';horizontal.className='guide guide-h';vertical.hidden=horizontal.hidden=true;$('scene').append(zone,vertical,horizontal);
let safeOn=false;try{safeOn=localStorage.getItem('review-safe-zone')==='1'}catch{}
const toggle=document.createElement('button');toggle.type='button';toggle.id='toggle-safe';toggle.title='Hiện vùng bị giao diện TikTok che (phím G)';$('mute').after(toggle);
function showSafe(on){safeOn=on;zone.hidden=!on;toggle.textContent=on?'Ẩn vùng an toàn':'Vùng an toàn TikTok';toggle.setAttribute('aria-pressed',String(on));try{localStorage.setItem('review-safe-zone',on?'1':'0')}catch{}}
toggle.onclick=()=>showSafe(!safeOn);showSafe(safeOn);
window.snapLayer=(x,y,w,h)=>{const xs=[0,360,720,...(safeOn?[SAFE.left,SAFE.right]:[])],ys=[0,640,1280,...(safeOn?[SAFE.top,SAFE.bottom]:[])];
 function best(start,size,targets){let hit=null;for(const edge of [start,start+size/2,start+size])for(const t of targets){const d=t-edge;if(Math.abs(d)<=8&&(!hit||Math.abs(d)<Math.abs(hit.d)))hit={d,t}}return hit}
 const bx=best(x,w,xs),by=best(y,h,ys);vertical.hidden=!bx;horizontal.hidden=!by;if(bx)vertical.style.left=bx.t+'px';if(by)horizontal.style.top=by.t+'px';return {dx:bx?bx.d:0,dy:by?by.d:0}};
document.addEventListener('layer-moved',()=>{vertical.hidden=horizontal.hidden=true});

const KEYS=[['Space / K','Phát hoặc dừng (kể cả khi vừa bấm nút)'],['J / L','Lùi / tới 1 giây'],['← / →','Lùi / tới 1 khung hình (Shift: 10 khung)'],['Home / End','Về đầu / cuối video xuất'],['S','Tách đoạn video tại đầu phát'],['Delete / Backspace','Xóa đoạn hoặc clip đang chọn trên timeline (video, MP3, nhạc nền)'],['Q / W (hoặc I / O)','Cắt phía trước / phía sau đầu phát'],['Kéo một đoạn','Đổi thứ tự đoạn video'],['Ctrl + lăn chuột','Phóng to / thu nhỏ timeline'],['M','Thêm mốc tại đầu phát'],['+ / −','Phóng to / thu nhỏ timeline'],['Ctrl+Z','Hoàn tác'],['Ctrl+Shift+Z / Ctrl+Y','Làm lại'],['Alt + mũi tên','Nhích lớp đang chọn 1 px (Shift: 10 px)'],['Giữ Alt khi kéo','Tắt bám đường gióng'],['Shift + bấm đoạn','Chọn nhiều đoạn để xóa cùng lúc'],['G','Bật/tắt vùng an toàn TikTok'],['Ctrl+S','Lưu dự án'],['P','Xuất thử 5 giây'],['Ctrl+Enter','Xuất video'],['Esc','Bỏ chọn đoạn'],['?','Bảng phím tắt này']];
const help=document.createElement('dialog');help.id='shortcut-help';help.innerHTML='<h2>Phím tắt</h2><p class="helper">Dùng khi con trỏ không nằm trong ô nhập chữ.</p><table></table><form method="dialog"><button class="primary-action">Đóng</button></form>';
for(const[k,v]of KEYS){const row=help.querySelector('table').insertRow();row.insertCell().innerHTML='<kbd></kbd>';row.cells[0].firstChild.textContent=k;row.insertCell().textContent=v}
document.body.append(help);
const helpButton=document.createElement('button');helpButton.type='button';helpButton.id='open-shortcuts';helpButton.textContent='⌨ Phím tắt';helpButton.title='Bảng phím tắt (?)';helpButton.onclick=()=>help.showModal();toggle.after(helpButton);

function nudge(dx,dy){const key=$('drag-target').value;if(!['video','frame','title','body'].includes(key))return false;for(const[axis,d]of [['x',dx],['y',dy]]){const e=$(key+'_'+axis);if(d)e.value=Math.round(Math.max(Number(e.min),Math.min(Number(e.max),Number(e.value)+d)))}design.schedule();later(500);return true}
document.addEventListener('keydown',e=>{
 if($('view-editor').hidden||help.open||e.defaultPrevented)return;
 const t=e.target,field=t.closest?.('textarea,select,[contenteditable="true"]')||(t.tagName==='INPUT'&&!['checkbox','button','radio','range'].includes(t.type)),mod=e.ctrlKey||e.metaKey,key=e.key.length===1?e.key.toLowerCase():e.key;
 const act=fn=>{e.preventDefault();fn()};
 if(mod&&key==='s')return act(()=>window.workspace?.saveProject());
 if(field)return;
 if(mod&&key==='z')return act(()=>go(e.shiftKey?1:-1));
 if(mod&&key==='y')return act(()=>go(1));
 if(mod&&e.key==='Enter')return act(()=>$('submit').click());
 if(e.altKey&&e.key.startsWith('Arrow')){const step=e.shiftKey?10:1,d={ArrowLeft:[-step,0],ArrowRight:[step,0],ArrowUp:[0,-step],ArrowDown:[0,step]}[e.key];if(nudge(...d))e.preventDefault();return}
 if(mod||e.altKey)return;
 const state=api.state(),end=state.plan?.duration||0,seek=v=>api.seek(Math.max(0,Math.min(end,v)));
 if(t.type==='range'&&key.startsWith('Arrow'))return;
 switch(key){
  case ' ':case 'k':return act(()=>{if(t.tagName==='BUTTON'||t.type==='range')t.blur();$('play').click()});
  case 'j':return act(()=>seek(state.clock-1));
  case 'l':return act(()=>seek(state.clock+1));
  case 'ArrowLeft':return act(()=>seek(state.clock-(e.shiftKey?10:1)/30));
  case 'ArrowRight':return act(()=>seek(state.clock+(e.shiftKey?10:1)/30));
  case 'Home':return act(()=>seek(0));
  case 'End':return act(()=>seek(end));
  case 's':return act(()=>timeline().split());
  case 'Delete':case 'Backspace':return act(()=>timeline().remove());
  case 'i':case 'q':return act(()=>timeline().trim('start'));
  case 'o':case 'w':return act(()=>timeline().trim('end'));
  case 'm':return act(()=>timeline().marker());
  case '+':case '=':return act(()=>timeline().zoom(1));
  case '-':return act(()=>timeline().zoom(-1));
  case 'g':return act(()=>showSafe(!safeOn));
  case 'p':return act(()=>$('preview-export').click());
  case '?':return act(()=>help.showModal());
  case 'Escape':return timeline().clear();
 }
});
})();
