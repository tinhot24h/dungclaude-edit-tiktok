'use strict';
// In-app updater: checks GitHub a few seconds after start, shows "Có bản mới" in the header, downloads only the
// changed files (verified by SHA-256 on the server side) and restarts the app; user data stays untouched.
(()=>{
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const button=el('button',{type:'button',id:'update-button',className:'update-button',textContent:'⟳',title:'Kiểm tra cập nhật'});
// header tools stay together on the right: update · quit · export settings
const tools=el('div',{className:'header-tools'}),badge=$('export-badge');if(badge){badge.before(tools);tools.append(button,badge)}else{document.querySelector('.app-header').append(tools);tools.append(button)}
// ⏻ quit: the only way to stop the app when it runs without a console window
const quit=el('button',{type:'button',id:'quit-button',className:'update-button',title:'Tắt Review Studio','aria-label':'Tắt Review Studio'});
// drawn as SVG: the ⏻ character is missing from Windows fonts and showed as an empty box
quit.innerHTML='<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M12 3v9"/><path d="M6.3 6.8a8 8 0 1 0 11.4 0"/></svg>';button.after(quit);
quit.onclick=async()=>{if(!confirm('Tắt Review Studio?\n\nVideo đang xuất hoặc đang lồng tiếng sẽ dừng (lần sau bấm Tiếp tục để chạy tiếp). Mở lại bằng MO_REVIEW_STUDIO.vbs hoặc START_WINDOWS.bat.'))return;
 try{await request('/app/quit',{method:'POST'})}catch{}document.body.innerHTML='<main style="padding:60px;text-align:center;font:15px system-ui;color:#c8d4e3"><h1>Đã tắt Review Studio</h1><p>Có thể đóng tab này. Mở lại bằng MO_REVIEW_STUDIO.vbs (không hiện cửa sổ cmd) hoặc START_WINDOWS.bat.</p></main>'};
const box=el('dialog',{id:'update-dialog',className:'update-dialog'});
box.innerHTML='<h2>Cập nhật Review Studio</h2><p id="update-text" class="helper"></p><pre id="update-notes" hidden></pre><div class="result-actions"><button type="button" id="update-run" class="primary-action small-action" hidden>Cập nhật ngay</button><button type="button" id="update-restart" class="primary-action small-action" hidden>Khởi động lại</button><button type="button" id="update-close" class="outline-action small-action">Đóng</button></div><p class="helper">Chỉ tải các file thay đổi từ GitHub và kiểm tra mã SHA-256 từng file. Video, MP3, dự án và cài đặt trong thư mục .local được giữ nguyên; bản cũ được sao lưu trong .local/update.</p>';
document.body.append(box);
let plan=null;
const text=t=>{$('update-text').textContent=t};
function show(d){plan=d;$('update-run').hidden=true;$('update-restart').hidden=true;$('update-notes').hidden=true;
 if(d.git){text(`Bản ${d.current} đang chạy từ git clone: cập nhật bằng lệnh  git pull  rồi mở lại ứng dụng.`);return}
 if(!d.changed.length&&!d.removed.length){text(`Đang dùng bản mới nhất (${d.current}).`);button.classList.remove('has-update');button.textContent='⟳';return}
 button.classList.add('has-update');button.textContent=d.newer?`⬆ Có bản ${d.latest}`:'⬆ Cập nhật';button.title='Có bản cập nhật · bấm để xem';
 text(`Bản đang dùng: ${d.current} · bản trên GitHub: ${d.latest}. Cần tải ${d.changed.length} file (${Math.max(1,Math.round(d.bytes/1024))} KB)${d.removed.length?`, xóa ${d.removed.length} file cũ`:''}.`);
 if(d.notes){$('update-notes').textContent=d.notes.replace(/\*\*/g,'');$('update-notes').hidden=false}$('update-run').hidden=false}
async function check(open){if(open){text('Đang kiểm tra GitHub…');box.showModal()}try{show(await request('/update/check'))}catch(e){if(open)text(e.message)}}
button.onclick=()=>check(true);$('update-close').onclick=()=>box.close();
$('update-run').onclick=async()=>{$('update-run').disabled=true;text(`Đang tải ${plan.changed.length} file và kiểm tra…`);try{const r=await request('/update/apply',{method:'POST'});$('update-run').hidden=true;text(r.updated?`Đã cập nhật lên ${r.version} (${r.files} file). Bấm Khởi động lại để dùng bản mới.`:'Không có gì cần cập nhật.');$('update-restart').hidden=!r.updated;button.classList.remove('has-update');button.textContent='⟳'}catch(e){text(e.message)}finally{$('update-run').disabled=false}};
$('update-restart').onclick=async()=>{$('update-restart').disabled=true;try{const r=await request('/update/restart',{method:'POST'});if(!r.launcher){text('Ứng dụng đã dừng. Mở lại bằng START_WINDOWS.bat (hoặc START_MAC_LINUX.command) để dùng bản mới.');return}text('Đang khởi động lại…');
 const until=Date.now()+60000;await new Promise(r=>setTimeout(r,1500));while(Date.now()<until){try{await request('/health');location.reload();return}catch{await new Promise(r=>setTimeout(r,1000))}}text('Chưa thấy ứng dụng chạy lại. Mở lại bằng START_WINDOWS.bat.')}catch(e){text(e.message);$('update-restart').disabled=false}};
setTimeout(()=>check(false),4000);
})();
