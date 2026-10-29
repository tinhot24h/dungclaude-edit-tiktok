'use strict';
// Video tools of "Cắt & vị trí video" (design on): align the video box on the 720×1280 frame, quick fill/fit sizes,
// zoom presets and rotation. The section's CapCut-style panel (design_tab.js) shows these buttons.
(()=>{
const edit=window.editorState;
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
{const sec=$('section-video'),N=id=>Number($(id).value)||0,design=window.studioApi;
 const set=values=>{for(const[k,v]of Object.entries(values)){const e=$(k);if(!e)continue;e.value=typeof v==='number'?Math.round(Math.max(Number(e.min||-1e9),Math.min(Number(e.max||1e9),v))*10)/10:v}design.schedule();window.appHistory?.checkpoint()};
 const source=()=>{const v=edit.current();return v&&v.width&&v.height?v.width/v.height:9/16};
 // what is seen: the box W×H scaled by zoom around its centre; "Giữ toàn bộ hình" shows the whole picture inside it
 // (smaller than the box when the shapes differ), then the rotation. Aligning puts that outline against the edge:
 // dw×dh = its size on screen, ox/oy = video_x/y that puts its left/top edge at 0.
 const shown=()=>{const z=N('video_zoom')/100||1,w=N('video_width'),h=N('video_height');let pw=w*z,ph=h*z;
  if($('video_fit')?.value==='contain'&&!window.nearFit?.(source(),1,pw/ph,1)){const r=source();if(pw/ph>r)pw=ph*r;else ph=pw/r}
  const t=N('video_rotation')*Math.PI/180,c=Math.abs(Math.cos(t)),sn=Math.abs(Math.sin(t)),dw=pw*c+ph*sn,dh=pw*sn+ph*c;
  return {z,w,h,dw,dh,ox:(dw-w)/2,oy:(dh-h)/2}};
 const group=(title,...buttons)=>el('div',{className:'video-tools'},el('div',{className:'group-label',textContent:title}),el('div',{className:'frame-tools'},...buttons));
 const btn=(text,title,fn)=>{const b=el('button',{type:'button',textContent:text,title,ariaLabel:title});b.onclick=fn;return b};
 const align=group('CĂN CHỈNH TRÊN KHUNG HÌNH',
  btn('⇤','Căn trái',()=>{const s=shown();set({video_x:s.ox})}),btn('↔','Căn giữa ngang',()=>{const s=shown();set({video_x:(720-s.dw)/2+s.ox})}),btn('⇥','Căn phải',()=>{const s=shown();set({video_x:720-s.dw+s.ox})}),
  btn('⤒','Căn trên',()=>{const s=shown();set({video_y:s.oy})}),btn('↕','Căn giữa dọc',()=>{const s=shown();set({video_y:(1280-s.dh)/2+s.oy})}),btn('⤓','Căn dưới',()=>{const s=shown();set({video_y:1280-s.dh+s.oy})}),
  btn('⊕ Giữa khung','Đặt video vào chính giữa khung hình',()=>{const s=shown();set({video_x:(720-s.dw)/2+s.ox,video_y:(1280-s.dh)/2+s.oy})}));
 const fit=group('KÍCH THƯỚC NHANH',
  btn('Lấp đầy 9:16','Phủ kín khung 720×1280, cắt phần thừa',()=>{$('video-lock').checked=true;set({video_x:0,video_y:0,video_width:720,video_height:1280,video_zoom:100,video_fit:'cover'})}),
  btn('Giữ toàn bộ hình','Hiện đủ khung hình gốc, viền trống nếu khác tỷ lệ',()=>set({video_x:0,video_y:0,video_width:720,video_height:1280,video_zoom:100,video_fit:'contain'})),
  btn('Vừa chiều ngang','Rộng bằng khung hình theo đúng tỷ lệ video gốc, đặt giữa dọc',()=>{$('video-lock').checked=false;const h=Math.round(720/source());set({video_width:720,video_height:Math.min(3840,Math.max(320,h)),video_x:0,video_y:(1280-h)/2,video_zoom:100,video_fit:'cover'})}),
  btn('Vừa chiều dọc','Cao bằng khung hình theo đúng tỷ lệ video gốc, đặt giữa ngang',()=>{$('video-lock').checked=false;const w=Math.round(1280*source());set({video_width:Math.min(2160,Math.max(180,w)),video_height:1280,video_x:(720-w)/2,video_y:0,video_zoom:100,video_fit:'cover'})}));
 const zoom=group('ZOOM',...[100,110,125,150,200].map(z=>btn(z+'%','Zoom '+z+'% quanh tâm video',()=>set({video_zoom:z}))));
 const rot=el('div',{className:'video-tools'},el('div',{className:'group-label',textContent:'XOAY'}));
 const slider=el('input',{type:'range',min:-180,max:180,step:1,id:'video-rotation-range',ariaLabel:'Góc xoay'});slider.oninput=()=>{$('video_rotation').value=slider.value;design.schedule()};slider.onchange=()=>window.appHistory?.checkpoint();
 const turn=d=>{let v=N('video_rotation')+d;while(v>180)v-=360;while(v<-180)v+=360;set({video_rotation:v})};
 rot.append(el('div',{className:'range-row'},slider),el('div',{className:'frame-tools'},btn('↺ 90°','Xoay trái 90°',()=>turn(-90)),btn('↻ 90°','Xoay phải 90°',()=>turn(90)),btn('180°','Xoay 180°',()=>turn(180)),btn('0°','Bỏ xoay',()=>set({video_rotation:0})),
  btn('⇋ Lật ngang','Lật ngang (soi gương)',()=>{const f=$('video_flip').value;set({video_flip:f==='h'?'none':f==='v'?'hv':f==='hv'?'v':'h'})}),btn('⇵ Lật dọc','Lật dọc',()=>{const f=$('video_flip').value;set({video_flip:f==='v'?'none':f==='h'?'hv':f==='hv'?'h':'v'})})));
 const at=$('video_zoom').closest('.control');at.before(align,fit,zoom);$('video_rotation').closest('.control').after(rot);
 const syncRot=()=>{slider.value=N('video_rotation')};document.addEventListener('design-changed',syncRot);syncRot()}
})();
