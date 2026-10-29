'use strict';
// "Lồng tiếng" page. Layout: top bar (saved configurations, key state, start) · left: settings in numbered sections,
// each with a one-line summary · right: live preview of the first input (cut, frame, overlay, subtitle) and a compact
// batch queue with filters and bulk actions. Jobs run on the server one at a time.
(()=>{
const view=$('view-dub'),edit=window.editorState;let bal={},balBusy=false,trial=null,editing=null,noAiTexts=[];
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const json=(url,body)=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
const STORE0='review-dub-v1',STORE='review-dub-v2',profile=()=>window.dubProfile?.name||'dub',storeKey=()=>STORE,presetKind=()=>'dubpresets',STEPS=[['asr','01','Nhận diện'],['translate','02','Dịch'],['separate','03','Tách âm'],['tts','04','Giọng ai33'],['export','05','Xuất']];
const time=t=>{t=Math.max(0,t||0);return `${Math.floor(t/60)}:${(t%60).toFixed(1).padStart(4,'0')}`};
const say=t=>{$('dub-status').textContent=t};window.dubSay=say;
let sel=0,files=[],jobs=[],current='',detail=null,poll=0,caps={demucs:false,openai:false,ai33:false},overlays=[],filter='all';

const section=(id,icon,title,body,open=false)=>`<details class="dub-sec" id="sec-${id}"${open?' open':''}><summary><span class="dub-sec-icon">${icon}</span><span class="dub-sec-title">${title}</span><small class="dub-sec-sum" id="sum-${id}"></small></summary><div class="dub-sec-body">${body}</div></details>`;
view.innerHTML=`<div class="dub-bar"><div class="dub-bar-title"><div class="eyebrow">LỒNG TIẾNG TỰ ĐỘNG · TRUNG · ANH → VIỆT</div><h1>Lồng tiếng video</h1></div>
 <div class="dub-bar-tools"><select id="dub-preset" aria-label="Cấu hình lồng tiếng đã lưu"></select><button type="button" id="dub-preset-save" class="outline-action small-action" title="Lưu toàn bộ thông số bên trái thành cấu hình">💾 Lưu cấu hình</button><button type="button" id="dub-preset-delete" class="outline-action small-action danger-action" title="Xóa cấu hình đang chọn">✕</button>
 <span class="dub-key-chip" id="dub-key-state"></span><div class="dub-run"><button type="button" id="dub-trial" class="dub-trial" title="Chạy 1 video đầu tiên để xem kết quả (giọng, chữ, khung); ưng rồi mới chạy cả lô" hidden>🧪 Chạy thử 1</button><button type="button" id="dub-start" class="primary-action">▶ Bắt đầu lồng tiếng</button></div></div></div>
<p id="dub-status" class="helper dub-status" role="status"></p>
<div class="dub-layout"><section class="panel dub-setup">
${section('input','🎬','Video đầu vào',`<div class="dub-drop" id="dub-drop" tabindex="0">Kéo thả video hoặc cả thư mục vào đây · .srt cùng tên sẽ bỏ qua bước nhận diện</div>
 <div class="result-actions"><label class="outline-action small-action file-button">＋ Chọn video<input id="dub-files" type="file" accept="video/*,.srt,audio/*" multiple hidden></label><button type="button" id="dub-local" class="primary-action small-action" title="Đọc video ngay trên máy, không phải tải lên (nhanh, không tốn thêm dung lượng)">📂 Thư mục trên máy</button><label hidden class="outline-action small-action file-button" title="Trình duyệt tải từng file lên (chậm hơn với nhiều file)">⬆ Tải thư mục lên<input id="dub-folder" type="file" webkitdirectory multiple hidden></label><button type="button" id="dub-from-bin" class="outline-action small-action">Từ kho Media</button><button type="button" id="dub-clear" class="outline-action small-action danger-action" title="Bỏ toàn bộ danh sách (file gốc trên máy không bị xóa)">✕ Bỏ tất cả video</button><button type="button" id="dub-clear-err" class="outline-action small-action" title="Bỏ các video bị lỗi khỏi danh sách">Bỏ video lỗi</button></div>
 <div id="dub-bin" class="dub-bin" hidden></div><div id="dub-list" class="dub-list"></div>`,true)}
${section('keys','🔑','Kết nối API',`<label for="dub-openai">OpenAI API key · nhận diện + dịch</label><input id="dub-openai" type="password" autocomplete="off" spellcheck="false" placeholder="sk-…">
 <label for="dub-ai33">ai33.pro API key · tạo giọng</label><input id="dub-ai33" type="password" autocomplete="off" spellcheck="false" placeholder="Lấy từ trang Âm thanh nếu đã nhập">
 <p class="helper">Dùng chung với trang Dịch AI và Âm thanh. Bấm “Lưu key trên máy này” để lần sau không phải nhập lại.</p>`)}
${section('frame','✂','Cắt & vị trí video',`<div class="two-col"><div><label for="dub-trim-start">Cắt đầu (giây)</label><input id="dub-trim-start" type="number" min="0" max="120" step="0.1" value="0"></div><div><label for="dub-trim-end">Cắt cuối (giây)</label><input id="dub-trim-end" type="number" min="0" max="120" step="0.1" value="0"></div></div>
 <label for="dub-edge">Cắt viền mép video gốc (px mỗi cạnh)</label><input id="dub-edge" type="number" min="0" max="40" step="1" value="0">
 <div class="two-col"><div><label for="dub-canvas">Khung xuất</label><select id="dub-canvas"><option value="source">Giữ khung gốc</option><option value="9:16">9:16 · 1080×1920 (TikTok)</option><option value="4:5">4:5 · 1080×1350</option><option value="1:1">1:1 · 1080×1080</option><option value="16:9">16:9 · 1920×1080</option></select></div><div><label for="dub-fit">Cách đặt hình</label><select id="dub-fit"><option value="cover">Lấp đầy · không viền (cắt phần thừa)</option><option value="contain">Giữ toàn bộ · viền đen</option><option value="blur">Giữ toàn bộ · nền mờ</option></select></div></div>
 <label for="dub-zoom">Zoom <output id="dub-zoom-value"></output></label><input id="dub-zoom" type="range" min="25" max="300" step="0.1" value="100">
 <div class="group-label">VỊ TRÍ & CĂN CHỈNH · KÉO VIDEO TRÊN KHUNG XEM TRƯỚC</div><div class="two-col"><div><label for="dub-x">Vị trí X (ngang) <output id="dub-x-value"></output></label><input id="dub-x" type="range" min="-300" max="300" step="any" value="0"></div><div><label for="dub-y">Vị trí Y (dọc) <output id="dub-y-value"></output></label><input id="dub-y" type="range" min="-300" max="300" step="any" value="0"></div></div>
 <div class="dub-align-grid" id="dub-frame-align"><button type="button" data-a="lt" title="Trên trái">↖</button><button type="button" data-a="ct" title="Trên giữa">↑</button><button type="button" data-a="rt" title="Trên phải">↗</button><button type="button" data-a="lc" title="Giữa trái">←</button><button type="button" data-a="cc" title="Chính giữa">●</button><button type="button" data-a="rc" title="Giữa phải">→</button><button type="button" data-a="lb" title="Dưới trái">↙</button><button type="button" data-a="cb" title="Dưới giữa">↓</button><button type="button" data-a="rb" title="Dưới phải">↘</button></div><p class="helper">X/Y: 100 = dời nửa khung. Căn 9 điểm đặt mép video sát mép khung.</p>
 <label for="dub-rotate">Xoay <output id="dub-rotate-value"></output></label><input id="dub-rotate" type="range" min="-180" max="180" step="0.1" value="0">
 <div class="frame-tools" id="dub-frame-tools"></div><select id="dub-flip" hidden><option value="none">none</option><option value="h">h</option><option value="v">v</option><option value="hv">hv</option></select>`)}
${section('adjust','🎚','Điều chỉnh màu',`<input id="dub-adj-on" type="checkbox" hidden><div class="dub-adjust"><label for="dub-adj-bright">Độ sáng</label><input id="dub-adj-bright" type="range" min="-100" max="100" step="1" value="0">
 <label for="dub-adj-contrast">Độ tương phản</label><input id="dub-adj-contrast" type="range" min="-100" max="100" step="1" value="0">
 <label for="dub-adj-sat">Độ bão hòa</label><input id="dub-adj-sat" type="range" min="-100" max="100" step="1" value="0">
 <label for="dub-adj-sharp">Độ sắc nét</label><input id="dub-adj-sharp" type="range" min="0" max="100" step="1" value="0">
 <button type="button" id="dub-adj-reset" class="outline-action small-action">↺ Đặt lại điều chỉnh</button></div>
 <p class="helper">Chỉ chỉnh video gốc (không ảnh hưởng nền, khung, chữ, overlay). Xem trước cập nhật ngay; video xuất dùng cùng mức chỉnh.</p>`)}
${section('overlay','✨','Overlay ngẫu nhiên',`<label class="check-row"><input id="dub-overlay" type="checkbox"> Thêm overlay ngẫu nhiên vào mỗi video <small>(không bắt buộc)</small></label>
 <div class="result-actions"><label class="outline-action small-action file-button">＋ Thêm file overlay<input id="dub-ov-files" type="file" accept="video/*,image/png,image/gif,image/webp,image/jpeg" multiple hidden></label><button type="button" id="dub-ov-local" class="primary-action small-action" title="Đọc overlay ngay trên máy, không phải tải lên">📂 Thư mục overlay trên máy</button><label hidden class="outline-action small-action file-button">⬆ Tải thư mục lên<input id="dub-ov-folder" type="file" webkitdirectory multiple hidden></label></div>
 <div class="dub-bulkbar" id="dub-ov-bulk"><button type="button" data-b="all">☑ Chọn tất cả</button><button type="button" data-b="none">☐ Bỏ chọn tất cả</button><button type="button" data-b="del" class="danger">🗑 Xóa overlay đang chọn</button><button type="button" data-b="wipe" class="danger">🗑 Xóa toàn bộ thư viện</button></div><div id="dub-ov-list" class="dub-ov-list"></div><p class="helper" id="dub-ov-note"></p>
 <div class="two-col"><div hidden><label for="dub-ov-count">Số overlay mỗi video</label><select id="dub-ov-count"><option value="1">1</option><option value="2">2</option><option value="3">3</option></select></div><div><label for="dub-ov-blend">Hòa trộn</label><select id="dub-ov-blend"><option value="screen">Sáng (screen) · hiệu ứng nền đen</option><option value="normal">Bình thường · theo độ đục</option><option value="key">Tách nền xanh (green screen)</option></select></div></div>
 <div class="two-col"><div><label for="dub-ov-opacity">Độ đục <output id="dub-ov-opacity-value"></output></label><input id="dub-ov-opacity" type="range" min="5" max="100" step="0.1" value="60"></div><div><label for="dub-ov-timing">Thời gian</label><select id="dub-ov-timing"><option value="sequence">Suốt video · 1 overlay, thiếu thì ghép thêm ngẫu nhiên</option><option value="loop">Suốt video · lặp lại 1 overlay</option><option value="random">Một đoạn ngẫu nhiên</option></select></div></div>
 <div class="group-label">CĂN CHỈNH OVERLAY <small>· kéo overlay trên khung xem trước khi mục này đang mở, kéo góc để đổi cỡ</small></div>
 <div class="dub-btns" id="dub-ov-fitbtns"><button type="button" data-f="cover" title="Overlay phủ kín khung của nó (cắt phần thừa)">Lấp đầy</button><button type="button" data-f="contain" title="Hiện trọn overlay, không cắt">Vừa khung</button><select id="dub-ov-fit" hidden><option value="cover">Lấp đầy</option><option value="contain">Vừa khung</option></select></div>
 <label for="dub-ov-scale">Thu phóng <output id="dub-ov-scale-value"></output></label><input id="dub-ov-scale" type="range" min="10" max="400" step="0.1" value="100">
 <div class="two-col"><div><label for="dub-ov-x">Vị trí X <output id="dub-ov-x-value"></output></label><input id="dub-ov-x" type="range" min="-150" max="150" step="any" value="0"></div><div><label for="dub-ov-y">Vị trí Y <output id="dub-ov-y-value"></output></label><input id="dub-ov-y" type="range" min="-150" max="150" step="any" value="0"></div></div>
 <div class="dub-align-grid" id="dub-ov-align"><button type="button" data-a="lt" title="Trên trái">↖</button><button type="button" data-a="ct" title="Trên giữa">↑</button><button type="button" data-a="rt" title="Trên phải">↗</button><button type="button" data-a="lc" title="Giữa trái">←</button><button type="button" data-a="cc" title="Chính giữa">●</button><button type="button" data-a="rc" title="Giữa phải">→</button><button type="button" data-a="lb" title="Dưới trái">↙</button><button type="button" data-a="cb" title="Dưới giữa">↓</button><button type="button" data-a="rb" title="Dưới phải">↘</button></div>
 <label for="dub-ov-rot">Xoay <output id="dub-ov-rot-value"></output></label><input id="dub-ov-rot" type="range" min="-180" max="180" step="0.1" value="0">
 <div class="dub-btns" id="dub-ov-turn"><button type="button" data-r="-90">↺ 90°</button><button type="button" data-r="90">↻ 90°</button><button type="button" data-r="0">0°</button><select id="dub-ov-flip" aria-label="Lật overlay"><option value="none">Không lật</option><option value="h">Lật ngang</option><option value="v">Lật dọc</option><option value="hv">Lật cả hai</option></select><button type="button" id="dub-ov-reset" class="outline-action small-action">↺ Đặt lại căn chỉnh</button></div>`)}
${section('image','🖼','Lớp ảnh',`<label class="check-row"><input id="dub-img" type="checkbox"> Chèn lớp ảnh lên mọi video <small>(không bắt buộc · che chữ gốc, khung, logo, sticker…)</small></label>
 <div class="dub-img-pick"><select id="dub-img-pick" aria-label="Ảnh đang dùng"></select><label class="outline-action small-action dub-file-btn">⬆ Thêm ảnh<input id="dub-img-file" type="file" accept="image/png,image/jpeg,image/webp" hidden></label><button type="button" id="dub-img-del" class="outline-action small-action danger-action" title="Xóa ảnh khỏi thư viện">✕</button></div>
 <div class="group-label">KÍCH THƯỚC & TỶ LỆ</div><label class="check-row"><input id="dub-img-keep" type="checkbox" checked> Giữ tỷ lệ ảnh</label>
 <div class="two-col"><div><label for="dub-img-w">Rộng <output id="dub-img-w-value"></output></label><input id="dub-img-w" type="range" min="1" max="200" step="0.1" value="60"></div><div><label for="dub-img-h">Cao <output id="dub-img-h-value"></output></label><input id="dub-img-h" type="range" min="1" max="200" step="0.1" value="30"></div></div>
 <div class="dub-btns" id="dub-img-fit"><button type="button" data-fit="contain">Vừa khung</button><button type="button" data-fit="cover">Lấp đầy khung</button><button type="button" data-fit="stretch">Kéo giãn full khung</button><button type="button" data-fit="native">Cỡ gốc</button></div>
 <div class="group-label">VỊ TRÍ & CĂN CHỈNH · KÉO ẢNH TRÊN KHUNG XEM TRƯỚC</div>
 <div class="two-col"><div><label for="dub-img-x">Ngang <output id="dub-img-x-value"></output></label><input id="dub-img-x" type="range" min="-100" max="100" step="any" value="0"></div><div><label for="dub-img-y">Dọc <output id="dub-img-y-value"></output></label><input id="dub-img-y" type="range" min="-100" max="100" step="any" value="0"></div></div>
 <div class="dub-align-grid" id="dub-img-align"><button type="button" data-a="lt" title="Trên trái">↖</button><button type="button" data-a="ct" title="Trên giữa">↑</button><button type="button" data-a="rt" title="Trên phải">↗</button><button type="button" data-a="lc" title="Giữa trái">←</button><button type="button" data-a="cc" title="Chính giữa">●</button><button type="button" data-a="rc" title="Giữa phải">→</button><button type="button" data-a="lb" title="Dưới trái">↙</button><button type="button" data-a="cb" title="Dưới giữa">↓</button><button type="button" data-a="rb" title="Dưới phải">↘</button></div>
 <div class="group-label">XOAY & LẬT</div>
 <label for="dub-img-rot">Xoay <output id="dub-img-rot-value"></output></label><input id="dub-img-rot" type="range" min="-180" max="180" step="0.1" value="0">
 <div class="dub-btns" id="dub-img-turn"><button type="button" data-r="-90">↺ 90°</button><button type="button" data-r="90">↻ 90°</button><button type="button" data-r="0">0°</button><select id="dub-img-flip" aria-label="Lật ảnh"><option value="none">Không lật</option><option value="h">Lật ngang</option><option value="v">Lật dọc</option><option value="hv">Lật cả hai</option></select></div>
 <div class="group-label">HÒA TRỘN & ĐỘ MỜ</div>
 <div class="two-col"><div><label for="dub-img-blend">Chế độ hòa trộn</label><select id="dub-img-blend"><option value="normal">Mặc định</option><option value="darken">Làm tối</option><option value="multiply">Nhân</option><option value="burn">Cháy màu</option><option value="lighten">Làm sáng</option><option value="screen">Màn hình (sáng)</option><option value="dodge">Né màu</option><option value="addition">Cộng sáng</option><option value="overlay">Lớp phủ</option><option value="softlight">Ánh sáng dịu · tán xạ</option><option value="hardlight">Ánh sáng mạnh</option><option value="difference">Khác biệt</option><option value="exclusion">Loại trừ</option></select></div><div><label for="dub-img-op">Độ đục <output id="dub-img-op-value"></output></label><input id="dub-img-op" type="range" min="0" max="100" step="0.1" value="100"></div></div>
 <div class="two-col"><div><label for="dub-img-layer">Thứ tự lớp</label><select id="dub-img-layer"><option value="below">Dưới overlay video</option><option value="above">Trên overlay video</option></select></div><div><label>&nbsp;</label><button type="button" id="dub-img-reset" class="outline-action small-action">Đặt lại lớp ảnh</button></div></div>`)}
${section('translate','🗣','Nhận diện & dịch',`<div class="two-col"><div><label for="dub-style">Văn phong</label><select id="dub-style"></select></div><div><label for="dub-pronoun">Xưng hô</label><select id="dub-pronoun"></select></div></div><div class="two-col"><div><label for="dub-energy">Độ hào hứng</label><select id="dub-energy"><option value="low">Nhẹ nhàng</option><option value="mid" selected>Vừa phải</option><option value="high">Hào hứng</option></select></div><div></div></div>
 <label for="dub-mode">Cách dịch &amp; tạo giọng</label><select id="dub-mode"><option value="paragraph">Đoạn văn liền · 1 file giọng ai33 (khuyên dùng)</option><option value="lines">Theo timestamp (SRT) · app dịch từng dòng, 1 file giọng, câu đặt đúng mốc</option><option value="ai33">ai33 lồng tiếng theo timestamp · ai33 tự nhận diện, dịch và đọc theo SRT</option></select><p class="helper" id="dub-mode-note"></p>
 <label for="dub-rate">Tốc độ nói mục tiêu <output id="dub-rate-value"></output></label><input id="dub-rate" type="range" min="3" max="6" step="0.1">
 <div class="two-col"><div><label for="dub-language">Ngôn ngữ nói</label><select id="dub-language"><option value="zh">Tiếng Trung</option><option value="en">Tiếng Anh</option><option value="auto">Tự nhận diện</option></select></div><div><label for="dub-model-pick">Model dịch OpenAI</label><select id="dub-model-pick"></select><input id="dub-model" type="text" spellcheck="false" placeholder="tên model, ví dụ gpt-4.1-mini" hidden></div></div>
 <p class="helper dub-model-note" id="dub-model-note"></p>
 <label for="dub-notes">Ghi chú văn phong (tùy chọn)</label><textarea id="dub-notes" rows="2" maxlength="2000" placeholder="Ví dụ: giọng vui vẻ, gọi sản phẩm là “máy hút bụi mini”"></textarea>
 <p class="dub-rule">🔒 Luôn áp dụng: không nhắc giá, thương hiệu, khối lượng, kích thước, thể tích chính xác — chỉ dùng từ ngữ chung chung.</p><input id="dub-no-price" type="checkbox" checked hidden>
 <p class="helper dub-template">Mẫu câu lệnh: <b id="dub-template">Mẫu mặc định</b> · lưu cùng "Lưu mẫu" ở trên · <a href="#" id="dub-template-edit">Sửa mẫu ›</a></p>
 <label class="check-row"><input id="dub-review" type="checkbox"> Dừng sau bước dịch để tự duyệt (mặc định tắt: chạy tự động một lần)</label>
 <label class="check-row"><input id="dub-vision" type="checkbox" checked> 👁 Cho AI xem 3 khung hình của video <small>(nhận đúng sản phẩm cho tiêu đề, nội dung, tên file · thêm rất ít phí, vẫn 1 lần gọi)</small></label>
 <label class="check-row"><input id="dub-reuse" type="checkbox" checked> ♻ Dùng lại kết quả cũ khi chạy lại cùng video <small>(lời gốc, bản dịch, giọng đọc · chỉ đổi giao diện thì không tốn API)</small></label>`)}
${section('captions','💬','Phụ đề chữ chạy',`<label class="check-row"><input id="dub-cap" type="checkbox"> Phụ đề hiện trên video, từ đang đọc sáng lên <small>(như CapCut · theo lời đọc tiếng Việt)</small></label>
 <div class="group-label">MẪU NHANH · KIỂU + PHÔNG + MÀU</div><div class="dub-cap-presets" id="dub-cap-presets"></div><div class="group-label">KIỂU HIỆU ỨNG</div><div class="dub-btns dub-cap-styles" id="dub-cap-styles"><button type="button" data-v="classic">Viền đen</button><button type="button" data-v="box">Nền hộp</button><button type="button" data-v="pop">Phóng to từ</button><button type="button" data-v="neon">Phát sáng</button><button type="button" data-v="karaoke">Karaoke tô dần</button><button type="button" data-v="marker">Nền màu từ</button><button type="button" data-v="shadow">Bóng đổ</button><button type="button" data-v="reveal">Hiện dần</button><button type="button" data-v="single">Từng chữ</button></div><input id="dub-cap-style" type="hidden" value="classic">
 <div class="two-col"><div><label for="dub-cap-font">Phông chữ</label><select id="dub-cap-font"></select></div><div><label for="dub-cap-words">Số chữ mỗi lần <output id="dub-cap-words-value"></output></label><input id="dub-cap-words" type="range" min="1" max="8" step="1" value="5"></div></div>
 <div class="two-col"><div><label for="dub-cap-size">Cỡ chữ <output id="dub-cap-size-value"></output></label><input id="dub-cap-size" type="range" min="24" max="160" step="1" value="68"></div><div><label for="dub-cap-y">Vị trí dọc <output id="dub-cap-y-value"></output></label><input id="dub-cap-y" type="range" min="5" max="95" step="1" value="70"></div></div>
 <div class="two-col"><div><label for="dub-cap-color">Màu chữ</label><input id="dub-cap-color" type="color" value="#ffffff"></div><div><label for="dub-cap-hi">Màu từ đang đọc</label><input id="dub-cap-hi" type="color" value="#ffe14d"></div></div>
 <label class="check-row"><input id="dub-cap-upper" type="checkbox"> VIẾT HOA TOÀN BỘ</label>
 <p class="helper">Kéo chữ mẫu trên khung xem trước để đổi vị trí dọc. Không cần bật "Phụ đề tiếng Việt" ở mục Xuất (đó là file .srt riêng).</p>`)}
${section('music','🎶','Nhạc nền',`<label class="check-row"><input id="dub-music" type="checkbox"> Thêm nhạc nền vào mỗi video <small>(chọn theo văn phong của video)</small></label>
 <div class="result-actions"><label class="outline-action small-action dub-file-btn">⬆ Thêm nhạc<input id="dub-music-file" type="file" accept="audio/*,.mp3,.wav,.m4a,.aac,.flac,.ogg" multiple hidden></label><small class="helper" id="dub-music-note"></small></div>
 <div id="dub-music-list" class="dub-music-list"></div>
 <div class="two-col"><div><label for="dub-music-vol">Âm lượng nhạc <output id="dub-music-vol-value"></output></label><input id="dub-music-vol" type="range" min="0" max="100" step="1" value="18"></div><div><label>&nbsp;</label><label class="check-row"><input id="dub-music-duck" type="checkbox" checked> Tự giảm nhạc khi có giọng đọc</label></div></div>
 <p class="helper">Mỗi bài có thể gắn văn phong hợp với nó. Khi chạy, app chọn ngẫu nhiên 1 bài gắn đúng văn phong của video (không có thì lấy bài chưa gắn, rồi bất kỳ bài nào); bài dài bắt đầu ở đoạn ngẫu nhiên, bài ngắn tự lặp, có lên/xuống nhỏ dần ở đầu và cuối. Tick ô "Dùng" để giới hạn những bài được chọn.</p>`)}
${section('audio','🎵','Âm thanh gốc',`<div class="dub-radios" id="dub-background"></div>
 <div class="dub-demucs" id="dub-demucs" hidden><p class="helper" id="dub-demucs-note">Tách giọng AI cần Demucs (miễn phí, chạy trên máy này). Bấm cài một lần, ứng dụng tự tải khoảng 1–3 GB (PyTorch + mô hình), không cần gõ lệnh.</p><div class="result-actions"><button type="button" id="dub-demucs-install" class="primary-action small-action">⬇ Cài Demucs tự động</button><button type="button" id="dub-demucs-check" class="outline-action small-action">↻ Kiểm tra lại</button></div><pre id="dub-demucs-log" class="dub-demucs-log" hidden></pre></div>
 <div class="two-col"><div><label for="dub-duck">Tiếng gốc khi có lời <output id="dub-duck-value"></output></label><input id="dub-duck" type="range" min="0" max="50" step="0.1"></div><div><label for="dub-bg-volume">Âm lượng nền <output id="dub-bg-value"></output></label><input id="dub-bg-volume" type="range" min="0" max="200" step="0.1"></div></div>`)}
${section('voice','🎙','Giọng đọc ai33',`<label for="dub-voice">Giọng đọc</label><div class="folder-row"><input id="dub-voice" type="text" spellcheck="false" placeholder="edge_vi-VN-HoaiMyNeural"><button type="button" id="dub-voice-browse" class="primary-action small-action">🎙 Chọn giọng ai33</button></div><p class="helper" id="dub-voice-note"><a href="#" id="dub-voice-pick">Dùng giọng đang chọn ở trang Âm thanh</a></p>
 <div class="dub-sample"><input id="dub-sample-text" type="text" maxlength="300" placeholder="Câu nghe thử (để trống = câu mẫu có sẵn)" aria-label="Câu nghe thử"><button type="button" id="dub-sample" class="outline-action small-action" title="Đọc câu này bằng giọng, tốc độ và từ điển đang chọn (tốn vài chục ký tự credit ai33; nghe lại không tốn thêm)">▶ Nghe thử</button></div><p class="helper" id="dub-sample-note"></p>
 <div id="dub-voices" class="dub-voices" hidden><div class="dub-voice-filter"><select id="dub-voice-provider" aria-label="Nhà cung cấp giọng"><option value="edge">Edge · miễn phí</option><option value="elevenlabs">ElevenLabs</option><option value="minimax">MiniMax</option><option value="vbee">Vbee</option><option value="fishaudio">Fish Audio</option><option value="kokoro">Kokoro</option><option value="clone">Giọng clone của tôi</option></select><input id="dub-voice-search" type="search" placeholder="Tìm giọng…" maxlength="100"><select id="dub-voice-gender" aria-label="Giới tính"><option value="">Nam + nữ</option><option value="Female">Nữ</option><option value="Male">Nam</option></select></div><div id="dub-voice-list" class="dub-voice-list"></div><div class="result-actions"><button type="button" id="dub-voice-more" class="outline-action small-action" hidden>Xem thêm</button><button type="button" id="dub-voice-close" class="text-button">Đóng</button></div><audio id="dub-voice-audio" preload="none"></audio></div>
 <label for="dub-align">Khớp thời lượng giọng ↔ video</label><select id="dub-align"><option value="auto">Tự động · chia tốc độ cho cả giọng và video</option><option value="voice">MP3 khớp video · co giãn giọng cho bằng video</option><option value="video">Video khớp MP3 · tua nhanh/làm chậm video</option></select><p class="helper" id="dub-align-note"></p>
 <div class="two-col"><div><label for="dub-speed">Tốc độ giọng ai33 <output id="dub-speed-value"></output></label><input id="dub-speed" type="range" min="0.7" max="1.3" step="0.05"></div><div></div></div>
 <div class="dub-limits"><div class="group-label">GIỚI HẠN TỰ KHỚP · QUÁ GIỚI HẠN THÌ CẮT THEO ĐỘ DÀI VIDEO</div>
 <div class="dub-limit-row"><span>Tốc độ giọng</span><input id="dub-tempo-min" type="number" min="0.5" max="1" step="0.01" aria-label="Tốc độ giọng thấp nhất"><i>–</i><input id="dub-tempo" type="number" min="1" max="1.6" step="0.01" aria-label="Tốc độ giọng cao nhất"><small>×</small></div>
 <div class="dub-limit-row"><span>Tốc độ video</span><input id="dub-vspeed-min" type="number" min="0.25" max="1" step="0.01" aria-label="Tốc độ video thấp nhất"><i>–</i><input id="dub-vspeed-max" type="number" min="1" max="4" step="0.01" aria-label="Tốc độ video cao nhất"><small>×</small></div>
 <label class="check-row"><input id="dub-end-voice" type="checkbox" checked> Video vẫn dài hơn giọng thì cắt video theo giọng (kết thúc sau câu cuối ~0.4s)</label></div>
 <div class="two-col"><div><label for="dub-voice-volume">Âm lượng giọng <output id="dub-voice-value"></output></label><input id="dub-voice-volume" type="range" min="50" max="200" step="0.1"></div><div><label for="dub-dict-pick">Từ điển phát âm</label><div class="folder-row"><select id="dub-dict-pick"><option value="">Không dùng</option></select><button type="button" id="dub-dict-load" class="outline-action small-action" title="Tải danh sách từ điển của tài khoản ai33 (tạo/sửa ở tab Âm thanh ai33)">↻</button></div><input id="dub-dict" type="number" min="1" hidden></div></div>`)}
${section('export','📤','Xuất & chạy hàng loạt',`<label class="check-row" title="Khi bấm ⟳ Xuất lại, file cũ của video đó trong thư mục xuất được thay bằng file mới cùng tên (không sinh thêm -2, -3…)"><input id="dub-overwrite" type="checkbox"> Ghi đè file cũ khi xuất lại</label><div class="two-col"><div><label for="dub-subs" title="Phụ đề dạng file, không in lên hình. Muốn chữ hiện trên video: bật 💬 Phụ đề chữ chạy">File phụ đề .srt (không in lên hình)</label><select id="dub-subs"><option value="file">File .srt đi kèm</option><option value="soft">Kênh phụ đề trong MP4 + .srt</option><option value="none">Không</option></select></div><div><label for="dub-parallel">Số video chạy cùng lúc</label><select id="dub-parallel"><option value="1">1 video (máy yếu)</option><option value="2">2 video</option><option value="3">3 video</option><option value="4">4 video (máy mạnh)</option></select></div></div>
 <select id="dub-loud" aria-label="Âm lượng tổng" hidden><option value="tiktok">Chuẩn hóa −14 LUFS (TikTok)</option><option value="off">Giữ nguyên</option></select>
 <div class="two-col"><div><label for="dub-demucs-n">Tách giọng AI (Demucs) cùng lúc</label><select id="dub-demucs-n"><option value="1">1 video (an toàn)</option><option value="2">2 video</option><option value="3">3 video</option><option value="4">4 video (RAM/VRAM lớn)</option></select></div><div></div></div>
 <label class="check-row"><input id="dub-resume" type="checkbox" checked> Mở lại ứng dụng thì tự chạy tiếp các video đang chờ/đang chạy dở</label>
 <div class="dub-out-summary"><span id="dub-out-text"></span><button type="button" id="dub-out-edit" class="outline-action small-action">Thông số xuất ›</button></div>
 <p class="helper" id="dub-run-note"></p>
 <p class="helper" id="dub-export-note">Video lưu vào thư mục xuất với tên AI đặt theo sản phẩm (sửa được trong hàng đợi); trùng tên thì dùng tên dự phòng rồi mới thêm -2.</p>`)}
</section>
<div class="panel dub-jobs"><div class="dub-queue-head"><div class="dq-top"><h2>Hàng đợi</h2><div class="dq-tools"><button type="button" id="dub-retry" class="outline-action small-action" title="Chạy lại các video bị lỗi (video chờ duyệt vẫn chờ bạn duyệt)">↻ Chạy lại lỗi</button><button type="button" id="dub-stop-all" class="outline-action small-action">■ Dừng tất cả</button>
 <details class="dq-menu"><summary class="outline-action small-action" title="Dọn dẹp, thông báo">⋯</summary><div class="dq-menu-list"><button type="button" id="dub-sweep" class="dq-item" title="Xóa file tạm (nhạc nền, giọng đã trộn, file đồ họa) của video đã xong. Giữ giọng đọc, bản dịch và video xuất.">💾 Dọn file tạm</button><button type="button" id="dub-clean" class="dq-item">🧹 Xóa video đã xong</button><button type="button" id="dub-clean-err" class="dq-item">🧹 Xóa video lỗi</button><button type="button" id="dub-clean-all" class="dq-item danger" title="Xóa mọi tác vụ không đang chạy">🗑 Xóa tất cả (trừ đang chạy)</button><label class="dq-item"><input type="checkbox" id="dq-notify"> 🔔 Báo khi cả lô xong</label></div></details></div></div>
 <div id="dq-overview" class="dq-overview" hidden><div class="dq-bar"><i id="dq-bar-done"></i><i id="dq-bar-err"></i></div><div id="dq-stats" class="dq-stats"></div></div>
 <div class="dq-filterbar"><div class="dub-filters" id="dub-filters"></div><input type="search" id="dq-search" placeholder="🔍 Tìm theo tên video…" aria-label="Tìm video trong hàng đợi"><select id="dq-step" aria-label="Lọc theo bước"><option value="">Mọi bước</option><option value="asr">Kẹt ở Nhận diện</option><option value="translate">Kẹt ở Dịch / viết chữ</option><option value="separate">Kẹt ở Tách âm</option><option value="tts">Kẹt ở Giọng ai33</option><option value="export">Kẹt ở Xuất</option></select></div>
 <div id="dq-errors" class="dq-errors" hidden></div>
 <div id="dq-select" class="dq-selectbar"><label class="dq-all"><input type="checkbox" id="dq-all"> <span id="dq-count">Chọn nhiều</span></label><span id="dq-sel-actions" class="dq-sel-actions" hidden><button type="button" data-a="run" class="primary-action small-action">▶ Chạy</button><button type="button" data-a="cancel" class="outline-action small-action">■ Dừng</button><button type="button" data-a="top" class="outline-action small-action" title="Đưa lên đầu hàng chờ">⤒ Ưu tiên</button><button type="button" data-a="bottom" class="outline-action small-action" title="Đưa xuống cuối hàng chờ">⤓ Xuống cuối</button><button type="button" data-a="edit" class="primary-action small-action" title="Mở video đầu tiên trong số đã chọn để chỉnh trực quan, rồi xuất lại tất cả với cùng thông số (giữ giọng và chữ)">✎ Sửa &amp; xuất lại</button><button type="button" data-a="delete" class="outline-action small-action danger-action">🗑 Xóa</button><button type="button" data-a="clear" class="icon-button" title="Bỏ chọn">✕</button></span></div></div>
  <div id="dub-trial-bar" class="dub-review-bar dub-trial-bar" hidden></div>
  <div id="dub-review-bar" class="dub-review-bar" hidden><span id="dub-review-count"></span><button type="button" id="dub-review-open" class="primary-action small-action">✎ Mở bảng duyệt chữ</button></div>
  <div class="dq-scroll" id="dq-scroll"><div id="dub-queue" class="dub-queue"></div><div id="dub-detail" class="dub-detail" hidden></div></div><div id="dq-pager" class="dq-pager" hidden></div></div>
<dialog id="dub-rules" class="dub-dialog wide"><div class="dub-review-head"><h2>Mẫu câu lệnh</h2><small class="helper">quy tắc nội dung &amp; văn phong gửi OpenAI cho mọi video</small></div>
 <div class="ai-rules-bar"><select id="dub-rules-list" aria-label="Mẫu câu lệnh đã lưu"></select><button id="dub-rules-save" type="button" class="chip-button">Lưu thành mẫu…</button><button id="dub-rules-delete" type="button" class="chip-button">Xóa mẫu</button><button id="dub-rules-reset" type="button" class="chip-button">Khôi phục mặc định</button></div>
 <textarea id="dub-rules-text" spellcheck="false" rows="14" aria-label="Quy tắc viết gửi cho AI"></textarea><div class="ai-rules-foot"><span id="dub-rules-count" class="helper"></span><span class="helper">Sửa là áp dụng ngay cho lần chạy sau</span></div>
 <details class="ai-fixed"><summary>Phần luôn được thêm (không sửa được)</summary><pre id="dub-rules-fixed"></pre><p class="helper">Ứng dụng tự thêm vai trò (dịch / viết chữ), giới hạn ký tự, kiểu tiêu đề, 3 tiêu đề + 2 nội dung, tên file, gợi ý sản phẩm và khung hình. Phần hook, kịch bản hay định dạng kết quả trong mẫu cũ được bỏ qua khi gửi.</p></details>
 <div class="dub-actions"><button type="button" id="dub-rules-close" class="primary-action small-action">Xong</button></div></dialog>
<dialog id="dub-check" class="dub-dialog"><h2>Kiểm tra trước khi chạy</h2><div id="dub-check-body"></div><div class="dub-actions"><button type="button" id="dub-check-back" class="outline-action small-action">Quay lại</button><button type="button" id="dub-check-go" class="primary-action small-action">▶ Chạy</button></div></dialog>
<dialog id="dub-treview" class="dub-dialog wide"><div class="dub-review-head"><h2>Duyệt chữ AI</h2><small id="dub-review-info" class="helper"></small><div class="dub-actions"><button type="button" id="dub-review-close" class="outline-action small-action">Đóng</button><button type="button" id="dub-review-go" class="primary-action small-action">▶ Xuất tất cả</button></div></div><div id="dub-review-body" class="dub-review-body"></div></dialog>
<aside class="dub-side"><div class="panel dub-preview" id="dub-preview"><div class="panel-heading dub-pv-head"><h2>Xem trước</h2><div class="dub-pv-tools"><label class="check-row" title="Vùng bị giao diện TikTok che (tên, mô tả, nút bên phải)"><input id="dub-safe" type="checkbox"> Vùng an toàn TikTok</label><button type="button" id="dub-pv-mute" class="icon-button" title="Bật/tắt tiếng xem trước">🔊</button></div></div><small id="dub-preview-info" class="helper dub-pv-info"></small><div id="dub-edit-bar" class="dub-edit-bar" hidden></div><div id="dub-layers" class="dub-layers" aria-label="Thứ tự lớp"></div><input id="dub-layer-order" type="hidden" value="">
 <div class="dub-frame-wrap"><div class="dub-frame" id="dub-frame"><video id="dub-bgv" class="dub-bgv" muted playsinline preload="metadata"></video><video id="dub-preview-video" class="dub-fgv" playsinline preload="metadata"></video><video id="dub-ovv" class="dub-ovv" muted loop playsinline preload="metadata"></video><img id="dub-ovi" class="dub-ovv" alt=""><div id="dub-ovbox" class="dub-ovbox" hidden title="Kéo để di chuyển overlay"><span class="dub-img-handle" title="Kéo để đổi cỡ overlay"></span></div><div id="dub-imgbox" class="dub-imgbox" hidden><img id="dub-imgl" alt=""><span class="dub-img-handle" title="Kéo để đổi kích thước"></span></div><div id="dub-capbox" class="dub-capbox" hidden></div><div id="dub-safezone" class="dub-safezone" hidden><i class="sz-top">Thanh trên</i><i class="sz-right">Nút tương tác</i><i class="sz-bottom">Tên · mô tả · nhạc</i></div><div class="dub-frame-empty" id="dub-frame-empty">Chọn video ở mục 🎬 để xem trước khung hình và overlay</div></div></div>
 <div class="dub-transport"><button type="button" id="dub-pv-play" class="fm-play" aria-label="Phát/dừng">▶</button><input id="dub-pv-seek" type="range" min="0" max="1" step="0.01" value="0" aria-label="Vị trí"><output id="dub-pv-time">0:00.0</output></div>
 <p class="helper" id="dub-preview-note"></p></div></aside></div>`;

const BG=[['duck','Giảm tiếng gốc khi có lời','Giữ nhạc nền chỗ không nói'],['center','Lọc giọng giữa (thử nghiệm)','Cần âm thanh stereo'],['demucs','Tách giọng AI (Demucs)','Tốt nhất · giữ nhạc nền, bỏ giọng Trung · chạy trên máy'],['keep','Giữ nguyên tiếng gốc','Chỉ thêm giọng Việt lên trên'],['remove','Xóa toàn bộ tiếng gốc','Chỉ còn giọng Việt']];
$('dub-background').replaceChildren(...BG.map(([v,t,h])=>el('label',{className:'dub-radio'},el('input',{type:'radio',name:'dub-bg',value:v}),el('span',{},el('strong',{textContent:t}),el('small',{textContent:h})))));
// one section open at a time keeps the column short
for(const d of view.querySelectorAll('.dub-sec'))d.addEventListener('toggle',()=>{if(d.open)for(const o of view.querySelectorAll('.dub-sec'))if(o!==d)o.open=false});

// ---- settings (no keys) remembered per browser and in saved configurations
let dictList=[];   // ai33 pronunciation dictionaries (loaded when the voice section opens)
const S={out_resolution:'resolution',out_fps:'fps',out_quality:'quality',language:'dub-language',model:'dub-model',pronoun:'dub-pronoun',energy:'dub-energy',rate:'dub-rate',notes:'dub-notes',no_price:'dub-no-price',review:'dub-review',duck_level:'dub-duck',background_volume:'dub-bg-volume',voice_id:'dub-voice',voice_speed:'dub-speed',max_tempo:'dub-tempo',min_tempo:'dub-tempo-min',video_speed_min:'dub-vspeed-min',video_speed_max:'dub-vspeed-max',voice_volume:'dub-voice-volume',dictionary_id:'dub-dict',subtitles:'dub-subs',loudness:'dub-loud',mode:'dub-mode',align:'dub-align',style:'dub-style',
 trim_start:'dub-trim-start',trim_end:'dub-trim-end',edge_trim:'dub-edge',frame_canvas:'dub-canvas',frame_fit:'dub-fit',frame_zoom:'dub-zoom',frame_x:'dub-x',frame_y:'dub-y',frame_rotate:'dub-rotate',frame_flip:'dub-flip',overlay:'dub-overlay',overlay_count:'dub-ov-count',overlay_blend:'dub-ov-blend',overlay_opacity:'dub-ov-opacity',overlay_timing:'dub-ov-timing',overlay_scale:'dub-ov-scale',overlay_x:'dub-ov-x',overlay_y:'dub-ov-y',overlay_rotate:'dub-ov-rot',overlay_flip:'dub-ov-flip',overlay_fit:'dub-ov-fit',end_with_voice:'dub-end-voice',image:'dub-img',image_id:'dub-img-pick',image_x:'dub-img-x',image_y:'dub-img-y',image_w:'dub-img-w',image_h:'dub-img-h',image_rotate:'dub-img-rot',image_flip:'dub-img-flip',image_blend:'dub-img-blend',image_opacity:'dub-img-op',image_layer:'dub-img-layer',layer_order:'dub-layer-order',captions:'dub-cap',caption_style:'dub-cap-style',caption_font:'dub-cap-font',caption_size:'dub-cap-size',caption_y:'dub-cap-y',caption_words:'dub-cap-words',caption_color:'dub-cap-color',caption_hi:'dub-cap-hi',caption_upper:'dub-cap-upper',music:'dub-music',overwrite_export:'dub-overwrite',music_volume:'dub-music-vol',music_duck:'dub-music-duck',image_keep:'dub-img-keep',adjust:'dub-adj-on',adjust_brightness:'dub-adj-bright',adjust_contrast:'dub-adj-contrast',adjust_saturation:'dub-adj-sat',adjust_sharpen:'dub-adj-sharp',vision:'dub-vision',reuse:'dub-reuse',meta:'meta-on',meta_strip:'meta-strip',meta_author:'meta-author',meta_url:'meta-url',meta_publisher:'meta-publisher',meta_copyright:'meta-copyright',meta_rating:'meta-rating',meta_back_min:'meta-back-min',meta_back_max:'meta-back-max'};
const NUM=new Set(['overlay_scale','overlay_x','overlay_y','overlay_rotate','caption_size','caption_y','caption_words','music_volume','edge_trim','meta_rating','meta_back_min','meta_back_max','rate','duck_level','background_volume','voice_speed','max_tempo','min_tempo','video_speed_min','video_speed_max','voice_volume','dictionary_id','trim_start','trim_end','image_x','image_y','image_w','image_h','image_rotate','image_opacity','frame_zoom','frame_x','frame_y','frame_rotate','overlay_count','overlay_opacity','adjust_brightness','adjust_contrast','adjust_saturation','adjust_sharpen']);
let ovUse=new Set(),ovAll=true,musUse=new Set(),music=[];
function settings(){const o={};for(const[k,id]of Object.entries(S)){const e=$(id);o[k]=e.type==='checkbox'?e.checked:NUM.has(k)?(e.value===''?null:Number(e.value)):e.value.trim()}
 o.background=view.querySelector('[name=dub-bg]:checked')?.value||'duck';o.instructions=template();o.overlay_ids=ovAll?[]:[...ovUse].filter(id=>overlays.some(x=>x.id===id));o.music_ids=[...musUse].filter(id=>!music.length||music.some(x=>x.id===id));
 for(const k of ['trim_start','trim_end'])o[k]=Math.max(0,Math.min(120,o[k]||0));if(o.image_keep)o.image_h=0;const enc=$('encoder')?.value;o.encoder=enc==='auto'?(window.hardwareEncoder||'cpu'):(enc||'cpu');window.dubProfile?.extend?.(o);return o}
function apply(o){if(o.subtitles==='burn')o={...o,subtitles:'file'};if(o.rules_saved&&typeof o.instructions==='string')setRules(o.instructions,o.rules_name||'');if(o.image_h===0)o={...o,image_h:null,image_keep:true};for(const[k,id]of Object.entries(S)){if(o[k]==null||(k==='mode'&&o[k]==='design'))continue;const e=$(id);if(e.type==='checkbox')e.checked=!!o[k];else e.value=o[k]}const r=view.querySelector(`[name=dub-bg][value="${o.background}"]`);if(r)r.checked=true;
 if(Array.isArray(o.overlay_ids)){ovAll=!o.overlay_ids.length;ovUse=new Set(o.overlay_ids);drawOverlays()}if(Array.isArray(o.music_ids)){musUse=new Set(o.music_ids);drawMusic()}capStyleButtons();window.dubProfile?.apply?.(o);window.exportMetaRefresh?.();if($('dub-dict-pick'))dictOptions(dictList);labels();preview();if($('dub-out-text'))runNote()}
function remember(){try{localStorage.setItem(storeKey(),JSON.stringify({...settings(),instructions:undefined,_v:4}))}catch{}labels()}
const pct=v=>(v>0?'+':'')+v+'%';
// X/Y of the video, the image layer and the video overlay are typed in pixels of the exported video (the range keeps
// the stored value: frame_x/y = % of half the frame, image/overlay = % of the frame). ↑/↓ in the box = 1 px.
const PX={'dub-x':['w',200],'dub-y':['h',200],'dub-img-x':['w',100],'dub-img-y':['h',100],'dub-ov-x':['w',100],'dub-ov-y':['h',100]};
const even=v=>Math.max(2,Math.round(v/2)*2);
function outWH(){try{return exportWH()}catch{return[1080,1920]}}   // before the preview is set up
function exportWH(){const res={720:720,1080:1080,'2k':1440,'4k':2160}[$('resolution')?.value]||1080,base=designOn()?[1080,1920]:CANVAS[$('dub-canvas')?.value];
 if(base)return[even(base[0]*res/1080),even(base[1]*res/1080)];const w=fg?.videoWidth||1080,h=fg?.videoHeight||1920,f=res/Math.min(w,h);return[even(w*f),even(h*f)]}
const pxPer=id=>{const[a,d]=PX[id],[W,H]=outWH();return(a==='w'?W:H)/d};   // px for 1 unit of the range
const toPx=range=>Math.round(+range.value*pxPer(range.id));
const pxLabel=id=>{const v=toPx($(id));return(v>0?'+':'')+v+' px'};
function showBox(range,box){box.value=PX[range.id]?toPx(range):range.value}
for(const range of view.querySelectorAll('input[type=range]:not(#dub-pv-seek)')){const px=!!PX[range.id],box=el('input',{type:'number',className:'dub-numbox'+(px?' dub-pxbox':''),step:px?1:range.step==='any'?0.1:range.step||1,title:px?'Nhập số px (theo video xuất) · ↑/↓ = 1 px, Shift = 10 px':'Nhập số chính xác'});
 if(!px){box.min=range.min;box.max=range.max}showBox(range,box);box.setAttribute('aria-label',(range.labels?.[0]?.textContent||'Giá trị').trim()+(px?' (px)':''));
 const row=el('div',{className:'dub-range'+(px?' dub-pxrow numeric-shell':'')});range.replaceWith(row);row.append(range,box);if(px)row.append(el('span',{className:'unit',textContent:'px'}));range.addEventListener('input',()=>{if(document.activeElement!==box)showBox(range,box)});
 const commit=(keep)=>{const v=Number(box.value);if(box.value===''||!Number.isFinite(v)){if(!keep)showBox(range,box);return}range.value=Math.min(+range.max,Math.max(+range.min,px?v/pxPer(range.id):v));if(!keep)showBox(range,box);range.dispatchEvent(new Event('input',{bubbles:true}));range.dispatchEvent(new Event('change',{bubbles:true}))};
 box.addEventListener('change',()=>commit());box.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();commit()}
  else if(px&&(e.key==='ArrowUp'||e.key==='ArrowDown')){e.preventDefault();box.value=(Number(box.value)||0)+(e.key==='ArrowUp'?1:-1)*(e.shiftKey?10:1);commit(true)}});
 if(px)box.addEventListener('input',()=>{if(box.value!==''&&box.value!=='-')commit(true)})}
function syncNumbers(){for(const box of view.querySelectorAll('.dub-numbox'))if(document.activeElement!==box)showBox(box.previousElementSibling,box)}
function labels(){setTimeout(()=>window.dubProfile?.labels?.());syncNumbers();capLabels(settings());const o=settings(),t=(id,v)=>{$(id).textContent=v};t('dub-rate-value',o.rate+' tiếng/giây');t('dub-duck-value',o.duck_level+'%');t('dub-bg-value',o.background_volume+'%');t('dub-speed-value',o.voice_speed+'×');t('dub-voice-value',o.voice_volume+'%');
 t('dub-zoom-value',o.frame_zoom+'%');t('dub-x-value',pxLabel('dub-x'));t('dub-y-value',pxLabel('dub-y'));t('dub-rotate-value',o.frame_rotate+'°');t('dub-img-w-value',$('dub-img-w').value+'%');t('dub-img-h-value',$('dub-img-h').value+'%'+(o.image_keep?' · theo tỷ lệ':''));t('dub-img-x-value',pxLabel('dub-img-x'));t('dub-img-y-value',pxLabel('dub-img-y'));t('dub-img-rot-value',o.image_rotate+'°');t('dub-img-op-value',o.image_opacity+'%');t('sum-image',o.image?(imgMeta()?`${imgMeta().name} · ${o.image_w}% · ${$('dub-img-blend').selectedOptions[0]?.text.toLowerCase()} ${o.image_opacity}%`:'bật · chưa chọn ảnh'):'tắt · không bắt buộc');t('dub-ov-opacity-value',o.overlay_opacity+'%');t('dub-ov-scale-value',o.overlay_scale+'%');t('dub-ov-x-value',pxLabel('dub-ov-x'));t('dub-ov-y-value',pxLabel('dub-ov-y'));t('dub-ov-rot-value',o.overlay_rotate+'°');for(const b of $('dub-ov-fitbtns').querySelectorAll('button'))b.classList.toggle('on',b.dataset.f===o.overlay_fit);
 $('dub-duck').disabled=o.background!=='duck';$('dub-bg-volume').disabled=o.background==='remove';
 // one-line summaries on the section headers
 const n=files.length,styles=$('dub-style').selectedOptions[0]?.textContent||'',bg=BG.find(b=>b[0]===o.background)?.[1]||'';
 t('sum-input',editing?`✎ sửa ${editing.items.length} video`:n?`${n} video${files.some(f=>f.srt)?' · có SRT':''}`:'chưa chọn');
 t('sum-frame',[o.trim_start||o.trim_end?`cắt ${o.trim_start}s đầu · ${o.trim_end}s cuối`:'',o.frame_canvas==='source'?'khung gốc':o.frame_canvas,o.frame_zoom!==100?`zoom ${o.frame_zoom}%`:'',o.frame_rotate?`xoay ${o.frame_rotate}°`:'',o.frame_flip!=='none'?'lật':''].filter(Boolean).join(' · '));
 t('sum-overlay',o.overlay?`${({sequence:'1 overlay + ghép',loop:'1 overlay lặp',random:'1 đoạn'})[o.overlay_timing]||'1 overlay'} · ${({screen:'sáng',normal:'thường',key:'tách nền xanh'})[o.overlay_blend]} ${o.overlay_opacity}% · ${ovAll?'tất cả '+overlays.length:ovUse.size+' đã chọn'}`:'tắt · không bắt buộc');
 t('sum-translate',`${styles} · ${o.mode==='paragraph'?'đoạn văn, 1 file':'từng câu'} · ${o.rate} tiếng/s`);
 t('sum-voice',`${$('dub-voice-note').dataset.name||o.voice_id||'chưa chọn giọng'} · ${({auto:'giữ tốc độ',voice:'MP3 khớp video',video:'video khớp MP3'})[o.align]}`);
 {const a=[['sáng',o.adjust_brightness],['tương phản',o.adjust_contrast],['bão hòa',o.adjust_saturation],['sắc nét',o.adjust_sharpen]].filter(([,v])=>v);t('sum-adjust',!o.adjust?'tắt':a.length?a.map(([n,v])=>`${n} ${v>0?'+':''}${v}`).join(' · '):'bật · chưa chỉnh')}
 t('sum-audio',o.background==='duck'?`${bg} · ${o.duck_level}%`:bg);t('sum-export',({file:'SRT kèm file',soft:'kênh phụ đề',none:'không phụ đề'})[o.subtitles]+(o.loudness==='tiktok'?' · −14 LUFS':''));
 keyState();startLabel()}
view.addEventListener('input',e=>{if(e.target.closest('.dub-setup')&&!['dub-openai','dub-ai33'].includes(e.target.id)){remember();preview()}});view.addEventListener('change',e=>{if(e.target.closest('.dub-setup')){remember();preview();alignNote()}});
function keyState(){const build=profile()==='design',o=$('dub-openai').value||caps.openai||(!build&&$('dub-mode').value==='ai33'),a=build||$('dub-ai33').value||$('tts-key')?.value||caps.ai33;const money=bal.spend?` · đã dùng $${bal.spend.usd.toFixed(2)}`:'',credit=typeof bal.ai33==='number'?` · còn ◆ ${Math.round(bal.ai33).toLocaleString('vi-VN')}`:'';
 $('dub-key-state').textContent=`OpenAI ${o?'✓':'✗'}${money}  |  ai33 ${a?'✓':'✗'}${credit}`;
 $('dub-key-state').title=[bal.spend?`OpenAI: app ước tính đã dùng ~$${bal.spend.usd.toFixed(2)} trong tháng ${bal.spend.month.split('-').reverse().join('/')} (${bal.spend.calls} lần gọi). OpenAI không cho xem số dư qua API key, xem số dư thật ở platform.openai.com → Billing.`:'',typeof bal.ai33==='number'?`ai33.pro: còn ${Math.round(bal.ai33).toLocaleString('vi-VN')} credit.`:'','Bấm để quản lý key · số dư tự cập nhật mỗi phút và sau mỗi video xong.'].filter(Boolean).join('\n');$('dub-key-state').classList.toggle('bad',!(o&&a));$('sum-keys').textContent=o&&a?'đã sẵn sàng':'cần nhập key'}
$('dub-key-state').onclick=()=>{window.openKeys?.();loadBalance()};
// money left / used: ai33 credits from ai33.pro, OpenAI = what this app's own calls cost this month (no balance API)
async function loadBalance(){if(balBusy)return;balBusy=true;try{bal.spend=await request('/dub/spend')}catch{}
 const key=$('dub-ai33').value||$('tts-key')?.value;if(key||caps.ai33){try{bal.ai33=Number((await request('/audio/credits',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(key?{api_key:key}:{})})).credits)}catch{bal.ai33=null}}
 balBusy=false;keyState()}
setInterval(()=>{if(!document.hidden&&!view.hidden)loadBalance()},60000);
for(const id of ['dub-openai','dub-ai33'])$(id).addEventListener('input',keyState);$('dub-mode').addEventListener('change',keyState);
document.addEventListener('keys-changed',()=>request('/dub/capabilities').then(d=>{caps=d;keyState();loadBalance()}).catch(()=>{}));
request('/dub/capabilities').then(d=>{caps=d;setTimeout(loadBalance,500);$('dub-style').replaceChildren(...Object.entries(d.styles).map(([k,v])=>new Option(v,k)));$('dub-pronoun').replaceChildren(...Object.entries(d.pronouns).map(([k,v])=>new Option(v[0].toUpperCase()+v.slice(1),k)));let saved={};try{saved=JSON.parse(localStorage.getItem(storeKey())||'null')||mergedOld()}catch{}
 // 0.16: one-click automatic run by default — older saved settings had the review pause switched on
 if(!(saved._v>=2)){delete saved.review;delete saved.align;saved._v=2}
 // 0.17.7: speed limits 0.98–1.1× voice / 0.85–1.2× video replace the old 1.3× maximum
 if(!(saved._v>=3)){delete saved.max_tempo;saved._v=3}if(!(saved._v>=4)){if(saved.overlay_timing==='loop')saved.overlay_timing='sequence';saved.overlay_count=1;saved._v=4}apply({...d.defaults,...saved});
 demucsState({available:d.demucs,state:'idle'});models=d.models||[];drawModels();if(!$('dub-voice').value)pickVoice(true);labels();alignNote()}).catch(e=>say(e.message));
// 0.22: "Dựng video" and "Lồng tiếng" became one tab; their saved settings are merged once
function mergedOld(){const read=k=>{try{return JSON.parse(localStorage.getItem(k)||'{}')||{}}catch{return {}}},dub=read(STORE0),build=read(STORE0+'-design'),out={...dub};
 if(build.design&&!dub.design)for(const k of ['design','title_source','body_source','review_texts'])if(build[k]!=null)out[k]=build[k];
 out.design_bg=out.design_title=out.design_body=!!dub.design;return out}
// Demucs: shown as available only when found; otherwise a one-click install (pip, in the app's own environment)
function demucsState(d){caps.demucs=d.available;const dm=view.querySelector('[name=dub-bg][value=demucs]');dm.disabled=!d.available;dm.closest('label').classList.toggle('disabled',!d.available);if(!d.available&&dm.checked)view.querySelector('[name=dub-bg][value=duck]').checked=true;
 const running=d.state==='running';$('dub-demucs').hidden=d.available&&d.state!=='done';$('dub-demucs-install').disabled=running;$('dub-demucs-check').disabled=running;$('dub-demucs-install').textContent=running?'Đang cài Demucs…':d.state==='error'?'⬇ Cài lại Demucs':'⬇ Cài Demucs tự động';
 $('dub-demucs-note').textContent=d.available?'✓ Demucs đã sẵn sàng. Chọn "Tách giọng AI (Demucs)" ở trên.':running?'Đang tải và cài Demucs (vài phút, tùy mạng). Có thể dùng các mục khác trong lúc chờ.':d.error||'Tách giọng AI cần Demucs (miễn phí, chạy trên máy này). Bấm cài một lần, ứng dụng tự tải khoảng 1–3 GB (PyTorch + mô hình), không cần gõ lệnh.';
 $('dub-demucs-log').hidden=!d.log||d.available;$('dub-demucs-log').textContent=d.log||'';if(running)setTimeout(()=>request('/dub/demucs').then(demucsState).catch(()=>{}),2000);if(d.available&&d.state==='done'&&dm.checked===false&&!dm.dataset.offered){dm.dataset.offered=1;dm.checked=true;remember()}labels()}
$('dub-demucs-install').onclick=async()=>{if(!confirm('Cài Demucs trên máy này?\n\nỨng dụng sẽ tải khoảng 1–3 GB (PyTorch và mô hình tách giọng) vào thư mục .local của ứng dụng. Cần mạng ổn định.'))return;try{demucsState(await json('/dub/demucs/install',{}))}catch(e){say(e.message)}};
$('dub-demucs-check').onclick=async()=>{$('dub-demucs-check').disabled=true;try{const d=await request('/dub/demucs?refresh=1');demucsState(d);say(d.available?'Đã tìm thấy Demucs.':'Chưa tìm thấy Demucs trên máy này.')}catch(e){say(e.message)}finally{$('dub-demucs-check').disabled=false}};
function pickVoice(quiet){try{const a=JSON.parse(localStorage.getItem('review-audio-v7')||'{}');if(a.voice?.voice_id){$('dub-voice').value=a.voice.voice_id;setVoiceName(a.voice.name||a.voice.voice_id);remember();return}}catch{}if(!quiet)$('dub-voice-note').textContent='Chưa chọn giọng ở trang Âm thanh. Bấm 🎙 Chọn giọng ai33.'}
function setVoiceName(name){$('dub-voice-note').textContent='Giọng: '+name;$('dub-voice-note').dataset.name=name;labels()}
$('dub-voice-pick').onclick=e=>{e.preventDefault();pickVoice(false)};
// pronunciation dictionaries of the ai33 account, picked by name (the id is what the job keeps)
function dictOptions(list){dictList=list||[];const pick=$('dub-dict-pick'),id=$('dub-dict').value;pick.replaceChildren(new Option('Không dùng',''),...(list||[]).map(d=>new Option(`${d.name||'Từ điển'} · ${d.rules?.length||0} từ`,String(d.id))));
 if(id&&![...pick.options].some(o=>o.value===id))pick.append(new Option('Từ điển ID '+id,id));pick.value=id}
async function loadDicts(quiet){try{const d=await json('/audio/dictionaries',{api_key:ai33Key()});dictOptions(d.dictionaries);if(!quiet)say(`Đã tải ${d.dictionaries.length} từ điển phát âm.`)}catch(e){dictOptions([]);if(!quiet)say(e.message)}}
$('dub-dict-load').onclick=()=>loadDicts(false);
$('dub-dict-pick').onchange=()=>{$('dub-dict').value=$('dub-dict-pick').value;$('dub-dict').dispatchEvent(new Event('input',{bubbles:true}));remember();preview()};
let dictsLoaded=false;document.addEventListener('toggle',e=>{if(e.target.id==='sec-voice'&&e.target.open&&!dictsLoaded){dictsLoaded=true;loadDicts(true)}},true);
// nghe thử: one sentence read by the chosen voice + speed + dictionary; the server keeps it, listening again is free
const sampleAudio=new Audio();
$('dub-sample').onclick=async()=>{const b=$('dub-sample'),o=settings();if(!sampleAudio.paused){sampleAudio.pause();b.textContent='▶ Nghe thử';return}
 if(!o.voice_id){say('Chọn giọng đọc trước khi nghe thử.');return}
 b.disabled=true;$('dub-sample-note').textContent='Đang tạo câu nghe thử bằng ai33…';
 try{const d=await json('/dub/sample',{voice_id:o.voice_id,voice_speed:o.voice_speed,dictionary_id:o.dictionary_id,text:$('dub-sample-text').value.trim(),...keys()});
  sampleAudio.src=`/dub/sample/${d.id}.mp3`;await sampleAudio.play().catch(()=>{});b.textContent='❚❚ Dừng';
  $('dub-sample-note').textContent=`${d.cached?'Đã nghe trước đó · không tốn credit':'Đã tạo câu nghe thử'} · giọng ${$('dub-voice-note').dataset.name||o.voice_id} · tốc độ ${o.voice_speed}×`}
 catch(e){$('dub-sample-note').textContent=e.message}finally{b.disabled=false}};
sampleAudio.onended=sampleAudio.onpause=()=>{$('dub-sample').textContent='▶ Nghe thử'};

// ---- voice picker straight from ai33 (/v3/voices)
let vPage=1,vTicket=0;
const ai33Key=()=>($('dub-ai33').value||$('tts-key')?.value||'').trim(),keys=()=>({openai_key:$('dub-openai').value.trim(),ai33_key:ai33Key()});
async function voices(fresh){const t=++vTicket;if(fresh){vPage=1;$('dub-voice-list').replaceChildren(el('p',{className:'helper',textContent:'Đang tải danh sách giọng…'}))}
 try{const d=await json('/audio/voices',{api_key:ai33Key(),provider:$('dub-voice-provider').value,search:$('dub-voice-search').value.trim(),gender:$('dub-voice-gender').value,language:$('dub-voice-provider').value==='clone'?'':'Vietnamese',page:vPage,page_size:30});if(t!==vTicket)return;
  const rows=d.voices.map(v=>{const play=el('button',{type:'button',className:'fm-play',textContent:'▶',title:'Nghe thử',disabled:!v.preview_url});play.onclick=()=>{const a=$('dub-voice-audio');if(a.dataset.id===v.voice_id&&!a.paused){a.pause();play.textContent='▶';return}for(const b of $('dub-voice-list').querySelectorAll('.fm-play'))b.textContent='▶';a.src=v.preview_url;a.dataset.id=v.voice_id;a.play().catch(()=>{});play.textContent='❚❚'};
   const pick=el('button',{type:'button',className:'outline-action small-action',textContent:$('dub-voice').value===v.voice_id?'✓ Đang dùng':'Chọn'});pick.onclick=()=>{$('dub-voice').value=v.voice_id;setVoiceName(v.name+(v.gender?' · '+(v.gender==='Female'?'nữ':v.gender==='Male'?'nam':v.gender):''));remember();$('dub-voice-audio').pause();for(const b of $('dub-voice-list').querySelectorAll('.dub-voice-row .outline-action'))b.textContent='Chọn';pick.textContent='✓ Đang dùng'};
   return el('div',{className:'dub-voice-row'+($('dub-voice').value===v.voice_id?' current':'')},play,el('div',{className:'fm-info'},el('strong',{textContent:v.name}),el('small',{textContent:[v.gender==='Female'?'Nữ':v.gender==='Male'?'Nam':v.gender,v.language,...(v.tags||[]).slice(0,2)].filter(Boolean).join(' · ')})),pick)});
  if(fresh)$('dub-voice-list').replaceChildren();$('dub-voice-list').append(...rows);if(fresh&&!rows.length)$('dub-voice-list').append(el('p',{className:'helper',textContent:'Không có giọng phù hợp. Đổi nhà cung cấp hoặc từ khóa.'}));$('dub-voice-more').hidden=!d.has_more}
 catch(e){if(t===vTicket)$('dub-voice-list').replaceChildren(el('p',{className:'helper',textContent:e.message+(ai33Key()||caps.ai33?'':' · Nhập hoặc lưu ai33 key ở mục Kết nối API.')}))}}
$('dub-voice-browse').onclick=()=>{const box=$('dub-voices');box.hidden=!box.hidden;if(!box.hidden)voices(true)};$('dub-voice-close').onclick=()=>{$('dub-voices').hidden=true;$('dub-voice-audio').pause()};
$('dub-voice-provider').onchange=()=>voices(true);$('dub-voice-gender').onchange=()=>voices(true);$('dub-voice-more').onclick=()=>{vPage++;voices(false)};
let vTimer;$('dub-voice-search').oninput=()=>{clearTimeout(vTimer);vTimer=setTimeout(()=>voices(true),350)};
document.addEventListener('view-change',e=>{if(e.detail==='dub'){if(!$('dub-ai33').value&&$('tts-key')?.value)$('dub-ai33').value=$('tts-key').value;keyState();showTemplate();loadOverlays();refresh()}else{$('dub-preview-video').pause();$('dub-bgv').pause()}});
const MODE_NOTE={paragraph:'App dịch thành một đoạn văn liền, ai33 đọc thành 1 file; áp dụng đủ quy tắc không nhắc giá/thương hiệu/thông số.',
 lines:'App dịch từng dòng giữ nguyên mốc thời gian (Whisper hoặc SRT bạn đính kèm), ai33 đọc tất cả thành 1 file giọng; app cắt file đó tại các chỗ ngắt giữa câu và đặt mỗi câu đúng mốc, tự đọc nhanh trong giới hạn. Áp dụng đủ quy tắc.',
 ai33:'Dùng API lồng tiếng của ai33 (/v1/task/dubbing): gửi âm thanh gốc, ai33 tự nhận diện, dịch sang tiếng Việt, tạo SRT có timestamp rồi đọc lại bằng giọng đã chọn (chỉ giọng, nền gốc do app tách). Không cần OpenAI key; tính credit ai33 theo thời lượng (+25% khi dùng giọng thay thế). Lưu ý: ai33 tự dịch nên quy tắc không nhắc giá/thương hiệu và văn phong của app KHÔNG áp dụng; giọng Kokoro không dùng được.'};
function alignNote(){const o=settings();$('dub-mode-note')&&($('dub-mode-note').textContent=MODE_NOTE[o.mode]||'');$('dub-align-note').textContent=o.mode==='ai33'?'ai33 tự căn giọng theo timestamp của lời gốc; giới hạn tốc độ bên dưới không áp dụng.':o.mode!=='paragraph'?'Chế độ từng câu: mỗi câu tự đọc nhanh (tối đa mức bên dưới) cho vừa chỗ trống.':{auto:`Giọng và video cùng đổi tốc độ một chút (giọng ${o.min_tempo}–${o.max_tempo}×, video ${o.video_speed_min}–${o.video_speed_max}×) thay vì một bên đổi nhiều. Vẫn không khớp: video dài hơn thì cắt bớt video, giọng dài hơn thì cắt bớt giọng (mờ dần cuối). Không lặp video hay MP3. MP3 giữ nguyên tần số gốc.`,voice:`Giọng co giãn ${o.min_tempo}–${o.max_tempo}× để kết thúc cùng video; dư thì cắt theo video.`,video:`Video tua ${o.video_speed_min}–${o.video_speed_max}× để kết thúc cùng giọng (nhạc nền đổi theo); giọng dư thì cắt theo video.`}[o.align]}

// ---- Mẫu câu lệnh: the writing rules sent with every OpenAI call ('' = the default), several can be kept by name;
// "Lưu mẫu" also stores the rules in use, so each template brings its own (8)
const RULES='review-ai-rules',RULES_NAME='review-ai-rules-name',RULES_LIST='review-ai-prompts';let ruleDefaults='',ruleMax=20000;
const store=(k,v)=>{try{v==null?localStorage.removeItem(k):localStorage.setItem(k,v)}catch{}},read=k=>{try{return localStorage.getItem(k)||''}catch{return ''}};
function savedRules(){try{return JSON.parse(read(RULES_LIST)||'{}')||{}}catch{return {}}}
function template(){return read(RULES).trim()}
function setRules(text,name){text=String(text||'').trim();store(RULES,text&&text!==ruleDefaults.trim()?text:'');store(RULES_NAME,name||'');showTemplate()}
function showTemplate(){const n=read(RULES_NAME);$('dub-template').textContent=template()?(n?'Mẫu: '+n:'Đã tùy chỉnh'):'Mẫu mặc định'}
function drawRules(){const list=savedRules(),n=read(RULES_NAME);$('dub-rules-list').replaceChildren(new Option('— Mẫu đã lưu —',''),...Object.keys(list).sort().map(k=>new Option(k,k)));$('dub-rules-list').value=list[n]!=null?n:'';
 $('dub-rules-count').textContent=`${$('dub-rules-text').value.length.toLocaleString('vi-VN')} / ${ruleMax.toLocaleString('vi-VN')} ký tự · ${template()?'đã tùy chỉnh':'mẫu mặc định'}`;$('dub-rules-delete').disabled=!$('dub-rules-list').value}
request('/dub/template-defaults').then(d=>{ruleDefaults=d.rules;ruleMax=d.max||ruleMax;$('dub-rules-text').maxLength=ruleMax;$('dub-rules-fixed').textContent=d.fixed;showTemplate()}).catch(()=>{});
$('dub-rules-text').addEventListener('input',()=>{const n=read(RULES_NAME);setRules($('dub-rules-text').value,savedRules()[n]===$('dub-rules-text').value?n:'');drawRules()});
$('dub-rules-list').onchange=()=>{const k=$('dub-rules-list').value,list=savedRules();if(k&&list[k]!=null){$('dub-rules-text').value=list[k];setRules(list[k],k);drawRules()}};
$('dub-rules-save').onclick=()=>{const name=prompt('Tên mẫu câu lệnh:',read(RULES_NAME)||'Mẫu của tôi');if(!name?.trim())return;const k=name.trim().slice(0,60),list=savedRules();list[k]=$('dub-rules-text').value;store(RULES_LIST,JSON.stringify(list));setRules($('dub-rules-text').value,k);drawRules()};
$('dub-rules-delete').onclick=()=>{const k=$('dub-rules-list').value,list=savedRules();if(!k||!confirm(`Xóa mẫu câu lệnh "${k}"?`))return;delete list[k];store(RULES_LIST,JSON.stringify(list));store(RULES_NAME,'');showTemplate();drawRules()};
$('dub-rules-reset').onclick=()=>{if(template()&&!confirm('Khôi phục câu lệnh mặc định? Nội dung đang sửa sẽ mất nếu chưa lưu thành mẫu.'))return;$('dub-rules-text').value=ruleDefaults;setRules('','');drawRules()};
$('dub-rules-close').onclick=()=>$('dub-rules').close();
$('dub-template-edit').onclick=e=>{e.preventDefault();$('dub-rules-text').value=template()||ruleDefaults;drawRules();$('dub-rules').showModal()};

// ---- saved configurations (all settings on the left, for running batches the same way)
let presets=[];
async function loadPresets(){try{presets=(await request('/library/'+presetKind())).items;const keep=$('dub-preset').value;$('dub-preset').replaceChildren(new Option('Mẫu: '+(presets.length?'— chọn để áp dụng —':'chưa lưu mẫu nào'),''),...presets.map(p=>new Option(p.name,p.id)));$('dub-preset').value=presets.some(p=>p.id===keep)?keep:''}catch{}}
$('dub-preset').onchange=async()=>{const id=$('dub-preset').value;if(!id)return;try{const r=await request('/library/'+presetKind()+'/'+id);apply(r.data.settings||{});remember();say(`Đã áp dụng mẫu "${r.name}".`)}catch(e){say(e.message)}};
$('dub-preset-save').onclick=async()=>{const name=prompt('Tên mẫu (lưu mọi thông số bên trái: giọng, nền & khung, chữ, video, xuất):',$('dub-preset').selectedOptions[0]?.value?$('dub-preset').selectedOptions[0].textContent:'Mẫu '+new Date().toLocaleDateString('vi-VN'));if(!name?.trim())return;const o=settings();o.rules_saved=true;o.rules_name=read(RULES_NAME);const old=presets.find(p=>p.name===name.trim());
 try{const r=await json('/library/'+presetKind()+'/save',{id:old?.id,name:name.trim().slice(0,120),data:{settings:o}});await loadPresets();$('dub-preset').value=r.id;say(`Đã lưu mẫu "${r.name}".`)}catch(e){say(e.message)}};
$('dub-preset-delete').onclick=async()=>{const p=presets.find(x=>x.id===$('dub-preset').value);if(!p){say('Chọn mẫu cần xóa.');return}if(!confirm(`Xóa mẫu "${p.name}"?`))return;try{await request(`/library/${presetKind()}/${p.id}/delete`,{method:'POST'});await loadPresets()}catch(e){say(e.message)}};
loadPresets();

// ---- input files: picked files, a folder (with matching .srt) or videos already in the media bin
const isAudio=f=>/\.(mp3|wav|m4a|aac|flac|ogg)$/i.test(f.name),isVideo=f=>!isAudio(f)&&(f.type.startsWith('video/')||/\.(mp4|mov|m4v|mkv|webm)$/i.test(f.name)),stem=n=>n.replace(/^.*[\\/]/,'').replace(/\.[^.]+$/,'').toLowerCase();
// new input while "✎ Sửa & xuất lại" is open: leave the edit first (its settings go back), so the new videos are seen and run
function leaveEditFor(){if(!editing)return;exitEdit();say('Đã thoát chế độ sửa & xuất lại để thêm video mới (thông số trước đó đã được trả lại).')}
async function add(list){leaveEditFor();const items=[...list],subs=items.filter(f=>/\.srt$/i.test(f.name));for(const f of items.filter(isVideo)){if(files.some(x=>x.file&&x.file.name===f.name&&x.file.size===f.size))continue;const srt=subs.find(s=>stem(s.name)===stem(f.name));leaveEditFor();files.push({file:f,name:f.name,srt:srt?await srt.text():'',srtName:srt?.name||''})}
 if(subs.length&&!items.some(isVideo)&&files.length===1){files[0].srt=await subs[0].text();files[0].srtName=subs[0].name}draw();if(!items.some(isVideo)&&!subs.length)say('Không thấy file video trong mục đã chọn.')}
$('dub-files').onchange=()=>{add($('dub-files').files);$('dub-files').value=''};$('dub-folder').onchange=()=>{add($('dub-folder').files);$('dub-folder').value=''};
$('dub-clear').onclick=()=>{if(files.length>20&&!confirm(`Bỏ ${files.length} video khỏi danh sách? (File gốc trên máy không bị xóa.)`))return;files=[];sel=0;draw();say('Đã bỏ tất cả video khỏi danh sách.')};
$('dub-clear-err').onclick=()=>{const n=files.filter(f=>f.error).length;files=files.filter(f=>!f.error);sel=0;draw();say(n?`Đã bỏ ${n} video lỗi.`:'Không có video lỗi.')};
const drop=$('dub-drop');drop.addEventListener('dragover',e=>{e.preventDefault();e.stopPropagation();drop.classList.add('over')});drop.addEventListener('dragleave',()=>drop.classList.remove('over'));
async function walkDrop(e){const out=[];const walk=async entry=>{if(entry.isFile)out.push(await new Promise(r=>entry.file(r)));else if(entry.isDirectory){const reader=entry.createReader();let batch;do{batch=await new Promise(r=>reader.readEntries(r));for(const x of batch)await walk(x)}while(batch.length)}};
 const entries=[...e.dataTransfer.items].map(i=>i.webkitGetAsEntry?.()).filter(Boolean);if(entries.length)for(const x of entries)await walk(x);else out.push(...e.dataTransfer.files);return out}
// While this page is open, files dropped on the window are dub inputs; dropped on the overlay section they become overlays.
addEventListener('drop',async e=>{if(view.hidden||![...(e.dataTransfer?.types||[])].includes('Files'))return;e.preventDefault();e.stopImmediatePropagation();drop.classList.remove('over');const onOverlay=!!e.target.closest?.('#sec-overlay');const list=await walkDrop(e);onOverlay?addOverlays(list):add(list)},true);
drop.onclick=()=>$('dub-files').click();
$('dub-from-bin').onclick=async()=>{const box=$('dub-bin');if(!box.hidden){box.hidden=true;return}try{const d=await request('/media/videos');box.replaceChildren(...(d.videos.length?d.videos.map(v=>{const b=el('button',{type:'button',className:'dub-bin-item'},el('img',{src:v.thumb,alt:'',loading:'lazy'}),el('span',{textContent:v.name}),el('small',{textContent:time(v.duration)}));b.onclick=()=>{if(!files.some(x=>x.id===v.id))leaveEditFor();files.push({id:v.id,name:v.name,srt:'',srtName:''});draw()};return b}):[el('p',{className:'helper',textContent:'Kho Media chưa có video.'})]));box.hidden=false}catch(e){say(e.message)}};
const LIST_MAX=150;
// gợi ý chung (10): one product hint for the whole batch; a video's own hint (💡 on its row) wins
let batchHint=(()=>{try{return localStorage.getItem('review-dub-hint')||''}catch{return ''}})();
const hintOf=f=>(f.hint||'').trim()||batchHint.trim();
function batchHintBox(){const i=el('input',{type:'text',id:'dub-batch-hint',className:'dub-hint',maxLength:300,value:batchHint,placeholder:'💡 Gợi ý chung cho cả lô (khi cùng một sản phẩm), ví dụ: kệ gia vị nhà bếp · video có gợi ý riêng thì dùng gợi ý riêng'});
 i.oninput=()=>{batchHint=i.value.slice(0,300);try{localStorage.setItem('review-dub-hint',batchHint)}catch{}for(const f of files)f.row?.querySelector('.dub-hint-chip')&&(f.row.querySelector('.dub-hint-chip').title=hintOf(f)?'Gợi ý: '+hintOf(f):'Thêm gợi ý sản phẩm cho AI (không bắt buộc)')};return i}
function draw(){if(editing){$('dub-list').replaceChildren(...editList());return}$('dub-list').replaceChildren(...(files.length?[el('div',{className:'dub-list-head'},el('span',{textContent:`${files.length} video sẽ ${profile()==='design'?'dựng':'lồng tiếng'}`}),el('small',{textContent:files.filter(f=>f.file).reduce((t,f)=>t+f.file.size,0)/1048576>0?(files.filter(f=>f.file).reduce((t,f)=>t+f.file.size,0)/1048576).toFixed(0)+' MB cần tải lên':''})),batchHintBox()]:[]),...files.slice(0,LIST_MAX).map((f,i)=>{const srt=el('label',{className:'chip-button file-button',title:'Đính kèm SRT lời gốc có sẵn (bỏ qua bước nhận diện, giữ đúng timestamp)',textContent:f.srtName?'SRT ✓':'+ SRT'},el('input',{type:'file',accept:'.srt',hidden:true}));srt.querySelector('input').onchange=async e=>{const s=e.target.files[0];if(s){f.srt=await s.text();f.srtName=s.name;draw()}};
  const x=el('button',{type:'button',className:'icon-button',textContent:'✕',title:'Bỏ video này'});x.onclick=e=>{e.stopPropagation();files.splice(i,1);if(i<sel)sel--;draw()};
  // gợi ý sản phẩm (optional): the AI uses it to name the product right in the title, body and file name
  const hintBox=el('input',{type:'text',className:'dub-hint',maxLength:300,value:f.hint||'',placeholder:'Gợi ý sản phẩm cho AI, ví dụ: váy maxi hoa nhí · có thể dán caption Douyin gốc',hidden:!f.hintOpen});
  const hintBtn=el('button',{type:'button',className:'chip-button dub-hint-chip'+(f.hint?' on':''),textContent:f.hint?'💡 ✓':'💡',title:f.hint?'Gợi ý: '+f.hint:'Thêm gợi ý sản phẩm cho AI (không bắt buộc)'});
  hintBtn.onclick=e=>{e.stopPropagation();f.hintOpen=!f.hintOpen;hintBox.hidden=!f.hintOpen;if(f.hintOpen)hintBox.focus()};
  hintBox.oninput=()=>{f.hint=hintBox.value.slice(0,300);hintBtn.textContent=f.hint.trim()?'💡 ✓':'💡';hintBtn.classList.toggle('on',!!f.hint.trim());hintBtn.title=f.hint.trim()?'Gợi ý: '+f.hint:'Thêm gợi ý sản phẩm cho AI (không bắt buộc)'};
  hintBox.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();f.hintOpen=false;hintBox.hidden=true}};hintBox.onclick=e=>e.stopPropagation();
  const row=el('div',{className:'dub-file'+(i===sel?' first':'')},el('span',{className:'dub-file-name',textContent:(i===sel?'👁 ':'')+f.name,title:i===sel?'Video đang xem trước':'Bấm để xem trước video này'}),el('small',{textContent:(f.error?'lỗi: '+f.error.slice(0,60):f.progress!=null?`tải ${f.progress}%`:f.file?(f.file.size/1048576).toFixed(1)+' MB':f.path?(f.size/1048576).toFixed(1)+' MB · trên máy':'trong kho'),title:f.error||f.path||''}),hintBtn,srt,x);
  row.onclick=e=>{if(e.target.closest('button,label,input'))return;sel=i;window.dubProfile?.previewJob?.(null);draw()};const wrap=el('div',{className:'dub-file-wrap'},row,hintBox);f.row=wrap;return wrap}),...(files.length>LIST_MAX?[el('p',{className:'helper',textContent:`… và ${files.length-LIST_MAX} video khác (danh sách chỉ hiện ${LIST_MAX} video đầu cho nhẹ máy; tất cả vẫn được lồng tiếng).`})]:[]));labels();preview()}
function rowProgress(f){const t=f.row?.querySelector('small');if(t&&f.row.isConnected)t.textContent=f.progress!=null?`tải ${f.progress}%`:'đã tải'}
// bulk actions for a large overlay library
$('dub-ov-bulk').onclick=async e=>{const b=e.target.closest('button');if(!b)return;const act=b.dataset.b;
 if(act==='all'){ovAll=true;ovUse=new Set();remember();drawOverlays();labels();preview();return}
 if(act==='none'){ovAll=false;ovUse=new Set();remember();drawOverlays();labels();preview();return}
 const ids=act==='wipe'?null:overlays.filter(o=>ovAll||ovUse.has(o.id)).map(o=>o.id);const n=act==='wipe'?overlays.length:ids.length;
 if(!n){say('Chưa chọn overlay nào.');return}if(!confirm(act==='wipe'?`Xóa TOÀN BỘ ${n} overlay khỏi thư viện?`:`Xóa ${n} overlay đang chọn khỏi thư viện?`))return;
 try{const r=await json('/overlays/delete-many',act==='wipe'?{all:true}:{ids});overlays=r.overlays;ovUse=new Set([...ovUse].filter(id=>overlays.some(o=>o.id===id)));if(!overlays.length)ovAll=true;remember();drawOverlays();labels();preview();say(`Đã xóa ${r.deleted} overlay.`)}catch(err){say(err.message)}};
// ---- folders on this computer: the app reads the files where they are (hard link or disk copy), nothing is uploaded
async function pickLocal(kind){const r=await json('/local/pick-folder',{kind});if(r.cancelled)return null;say('Đang đọc thư mục '+r.folder+'…');return (await json('/local/scan',{folder:r.folder,kind})).files}
async function localImport(f){const d=await json('/local/import',{path:f.path});f.id=d.id;if(d.srt&&!f.srt){f.srt=d.srt;f.srtName=d.srt_name}return d}
$('dub-local').onclick=async()=>{const b=$('dub-local');b.disabled=true;try{const list=await pickLocal('video');if(!list)return;const vids=list.filter(x=>!/\.(srt|mp3|wav|m4a|aac|flac|ogg|opus)$/i.test(x.name)),srts=new Set(list.filter(x=>/\.srt$/i.test(x.name)).map(x=>stem(x.name).toLowerCase()));
  let added=0;for(const v of vids){if(files.some(x=>x.path===v.path))continue;leaveEditFor();files.push({path:v.path,name:v.name,size:v.size,srtName:srts.has(stem(v.name).toLowerCase())?'SRT ✓ (cùng tên)':''});added++}
  const shown=files[sel]||files[0];if(shown?.path&&!shown.id)await localImport(shown).catch(e=>{shown.error=e.message});
  draw();say(added?`Đã thêm ${added} video từ máy (không tải lên). ${profile()==='design'?'MP3 cùng tên tự ghép làm giọng đọc.':'File SRT cùng tên được dùng tự động.'}`:'Không có video mới trong thư mục này.')}catch(e){say(e.message)}finally{b.disabled=false}};
$('dub-ov-local').onclick=async()=>{const b=$('dub-ov-local');b.disabled=true;try{const list=await pickLocal('overlay');if(!list)return;
  const have=new Set(overlays.map(o=>o.name+'|'+o.size)),todo=list.filter(x=>!have.has(x.name+'|'+x.size)),errors=[];let ok=0,alpha=false;
  for(const[i,x]of todo.entries()){$('dub-ov-note').textContent=`Đang đọc overlay ${i+1}/${todo.length} từ máy: ${x.name}…`;try{const item=await json('/overlays/import-local',{path:x.path});ok++;alpha=alpha||!!item.alpha}catch(e){errors.push(x.name+': '+e.message)}if(i%25===24)await loadOverlays()}
  if(alpha&&+$('dub-ov-opacity').value===60){$('dub-ov-opacity').value=100;$('dub-ov-opacity').dispatchEvent(new Event('input',{bubbles:true}))}
  await loadOverlays();if(ok&&!$('dub-overlay').checked){$('dub-overlay').checked=true;$('dub-overlay').dispatchEvent(new Event('change',{bubbles:true}));remember()}labels();preview();
  say(`Đã thêm ${ok} overlay từ máy (không tải lên).`+(list.length-todo.length?` Bỏ qua ${list.length-todo.length} file đã có.`:'')+(errors.length?` ${errors.length} file lỗi.`:''));if(errors.length)$('dub-ov-note').textContent=`${errors.length} file lỗi: `+errors.slice(0,5).join(' · ')}catch(e){say(e.message)}finally{b.disabled=false}};
function startLabel(){if(editing){$('dub-trial').hidden=true;$('dub-start').textContent=`⟳ Xuất lại ${editing.items.length} video`;return}const n=files.length,build=profile()==='design';$('dub-trial').hidden=n<2&&!(trial&&n);$('dub-start').textContent=build?(n>1?`▶ Xuất ${n} video`:'▶ Bắt đầu dựng video'):n>1?`▶ Lồng tiếng ${n} video`:'▶ Bắt đầu lồng tiếng'}

// ---- overlay library
async function loadOverlays(){try{overlays=(await request('/overlays')).overlays;drawOverlays();preview()}catch{}}
function drawOverlays(){$('dub-ov-list').replaceChildren(...overlays.map(o=>{const use=el('input',{type:'checkbox',checked:ovAll||ovUse.has(o.id),title:'Dùng overlay này khi chọn ngẫu nhiên'});use.onchange=()=>{if(ovAll){ovAll=false;ovUse=new Set(overlays.map(x=>x.id))}use.checked?ovUse.add(o.id):ovUse.delete(o.id);if(ovUse.size===overlays.length)ovAll=true;remember();labels();preview()};
  const del=el('button',{type:'button',className:'icon-button',textContent:'✕',title:'Xóa khỏi thư viện overlay'});del.onclick=async e=>{e.preventDefault();if(!confirm(`Xóa overlay "${o.name}"?`))return;try{overlays=(await request(`/overlays/${o.id}/delete`,{method:'POST'})).overlays;ovUse.delete(o.id);drawOverlays();labels();preview()}catch(err){say(err.message)}};
  return el('label',{className:'dub-ov'+(ovAll||ovUse.has(o.id)?' on':'')},use,el('img',{src:`/overlays/${o.id}/thumb${o.alpha?'?alpha=1':''}`,alt:'',loading:'lazy'}),el('span',{textContent:o.name}),el('small',{textContent:(o.still?'ảnh':time(o.duration))+(o.alpha?' · trong suốt':'')}),del)}));
 $('dub-ov-note').textContent=overlays.length?`${overlays.length} overlay trong thư viện · mỗi video lấy ngẫu nhiên từ các overlay được tích. Overlay dài hơn video tự cắt bằng video; ngắn hơn thì lặp hoặc ghép nối tùy mục Thời gian.`:'Chưa có overlay. Thêm video hiệu ứng (ánh sáng, bụi, khung động…), GIF hoặc PNG; có thể kéo thả cả thư mục vào mục này.'}
async function addOverlays(list){const media=[...list].filter(f=>/^(video|image)\//.test(f.type)||/\.(mp4|mov|webm|mkv|m4v|gif|png|webp|jpe?g)$/i.test(f.name));if(!media.length){say('Không có file overlay hợp lệ (video, GIF, PNG, JPG).');return}
 // files already in the library (same name and size) are skipped; errors are listed once at the end
 const have=new Set(overlays.map(o=>o.name+'|'+o.size)),todo=media.filter(f=>!have.has(f.name+'|'+f.size)),skipped=media.length-todo.length,errors=[];
 let ok=0,alpha=false;for(const[i,f]of todo.entries()){$('dub-ov-note').textContent=`Đang thêm overlay ${i+1}/${todo.length}: ${f.name}…`;try{const item=await request('/overlays/upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(f.name)},body:f});ok++;alpha=alpha||!!item.alpha}catch(e){errors.push(f.name+': '+e.message)}
  if(i%20===19){await loadOverlays()}}

 // transparent overlays (live comments, frames, stickers) are meant to show fully, like in CapCut
 if(alpha&&+$('dub-ov-opacity').value===60){$('dub-ov-opacity').value=100;$('dub-ov-opacity').dispatchEvent(new Event('input',{bubbles:true}))}
 await loadOverlays();if(ok&&!$('dub-overlay').checked){$('dub-overlay').checked=true;$('dub-overlay').dispatchEvent(new Event('change',{bubbles:true}));remember()}labels();preview();say((ok?`Đã thêm ${ok} overlay và bật chèn overlay vào video (tắt công tắc ở tiêu đề Overlay nếu không muốn dùng).`:'Chưa thêm overlay mới nào.')+(skipped?` Bỏ qua ${skipped} file đã có trong thư viện.`:'')+(errors.length?` ${errors.length} file lỗi (xem dưới danh sách overlay).`:''));if(errors.length)$('dub-ov-note').textContent=`${errors.length} file lỗi: `+errors.slice(0,5).join(' · ')+(errors.length>5?' …':'')}
$('dub-ov-files').onchange=()=>{addOverlays($('dub-ov-files').files);$('dub-ov-files').value=''};$('dub-ov-folder').onchange=()=>{addOverlays($('dub-ov-folder').files);$('dub-ov-folder').value=''};

// ---- frame quick tools
{const tools=$('dub-frame-tools'),set=v=>{for(const[k,val]of Object.entries(v))$(S[k]).value=val;remember();preview()},btn=(t,title,fn)=>{const b=el('button',{type:'button',textContent:t,title});b.onclick=fn;tools.append(b)};
 btn('⊕ Giữa','Đặt video vào giữa khung',()=>set({frame_x:0,frame_y:0}));btn('↺ 90°','Xoay trái 90°',()=>set({frame_rotate:((Number($('dub-rotate').value)-90+540)%360)-180}));btn('↻ 90°','Xoay phải 90°',()=>set({frame_rotate:((Number($('dub-rotate').value)+90+540)%360)-180}));
 const flip=(a)=>{const f=$('dub-flip').value,has=f.includes(a),other=a==='h'?'v':'h',keep=f.includes(other);set({frame_flip:(has?'':a)===''?(keep?other:'none'):(keep?'hv':a)})};btn('⇋ Lật ngang','Lật ngang (soi gương)',()=>flip('h'));btn('⇵ Lật dọc','Lật dọc',()=>flip('v'));
 btn('Zoom 110%','Phóng nhẹ để đổi khung hình',()=>set({frame_zoom:110}));btn('Đặt lại','Bỏ zoom, xoay, lật, dịch chuyển',()=>set({frame_zoom:100,frame_x:0,frame_y:0,frame_rotate:0,frame_flip:'none'}))}

// ---- live preview: same order as the export (fit into a canvas×zoom box, rotate, offset; overlay; subtitle)
const CANVAS={'9:16':[1080,1920],'4:5':[1080,1350],'1:1':[1080,1080],'16:9':[1920,1080]};
let previewUrl='',previewKey='';
const fg=$('dub-preview-video'),bgv=$('dub-bgv');
// "Điều chỉnh màu" on the preview: CSS filters on the source video only, on the scale of the export (eq + unsharp)
function adjustPreview(o){const on=!!o.adjust,b=on?o.adjust_brightness||0:0,c=on?o.adjust_contrast||0:0,s=on?o.adjust_saturation||0:0,k=on?(o.adjust_sharpen||0)/100*.6:0;
 const m=$('dub-sharp-matrix');if(m)m.setAttribute('kernelMatrix',`0 ${-k} 0 ${-k} ${1+4*k} ${-k} 0 ${-k} 0`);
 const filter=[b?`brightness(${(1+b/100*.35).toFixed(3)})`:'',c?`contrast(${(1+c/100*.5).toFixed(3)})`:'',s?`saturate(${(1+s/100).toFixed(3)})`:'',k?'url(#dub-sharp)':''].filter(Boolean).join(' ');
 for(const v of [fg,bgv,$('video')])if(v)v.style.filter=filter}
document.body.insertAdjacentHTML('beforeend','<svg width="0" height="0" style="position:absolute" aria-hidden="true"><filter id="dub-sharp"><feConvolveMatrix id="dub-sharp-matrix" order="3" kernelMatrix="0 0 0 0 1 0 0 0 0" preserveAlpha="true"/></filter></svg>');
for(const id of ['dub-adj-bright','dub-adj-contrast','dub-adj-sat','dub-adj-sharp'])$(id).addEventListener('input',e=>{if(e.target.value!=='0'&&!$('dub-adj-on').checked){$('dub-adj-on').checked=true;$('dub-adj-on').dispatchEvent(new Event('change',{bubbles:true}))}},true);
$('dub-adj-reset').onclick=()=>{for(const id of ['dub-adj-bright','dub-adj-contrast','dub-adj-sat','dub-adj-sharp']){$(id).value=0;$(id).dispatchEvent(new Event('input',{bubbles:true}))}};
// overlay: the first overlay of the pool (the real one is picked at random per video); the design stage shows it too
// "Căn chỉnh overlay" (same as the export): box = frame × Thu phóng, Lấp đầy/Vừa khung inside it, centre + X/Y % of the
// frame, rotation and flip. Used by the plain preview and the design stage (window.dubOverlayStyle).
function ovStyle(o){const fx=o.overlay_flip.includes('h')?-1:1,fy=o.overlay_flip.includes('v')?-1:1;
 return{inset:'auto',width:o.overlay_scale+'%',height:o.overlay_scale+'%',left:(50+o.overlay_x)+'%',top:(50+o.overlay_y)+'%',objectFit:o.overlay_fit,
  transform:`translate(-50%,-50%) rotate(${o.overlay_rotate}deg) scale(${fx},${fy})`}}
window.dubOverlayStyle=()=>ovStyle(settings());
// the handle for dragging the overlay shows while its section is open (like selecting the overlay layer in CapCut)
function ovHandle(o,ov){const h=$('dub-ovbox');if(!h)return;h.hidden=!ov||!$('sec-overlay').open;if(h.hidden)return;
 Object.assign(h.style,{width:o.overlay_scale+'%',height:o.overlay_scale+'%',left:(50+o.overlay_x)+'%',top:(50+o.overlay_y)+'%',transform:`translate(-50%,-50%) rotate(${o.overlay_rotate}deg)`})}
function pickOverlay(o){const pool=overlays.filter(x=>ovAll||ovUse.has(x.id)),ov=o.overlay?pool[0]:null,ovv=$('dub-ovv'),ovi=$('dub-ovi');ovv.hidden=!ov||ov.still;ovi.hidden=!ov||!ov.still;
 if(ov){const src=`/overlays/${ov.id}/${ov.still?'file':'preview'}`,target=ov.still?ovi:ovv;if(target.dataset.src!==src){target.src=src;target.dataset.src=src;if(!ov.still)ovv.onloadedmetadata=syncOverlay}Object.assign(target.style,{opacity:o.overlay_opacity/100,mixBlendMode:o.overlay_blend==='screen'&&!ov.alpha?'screen':'normal',...ovStyle(o)})}else ovv.pause();ovHandle(o,ov);return ov}
// ---- the preview fits the window: the frame gets the height left by the panel's other rows (measured, not guessed)
// and the column's width, so 9:16, 16:9 and 1:1 all stay whole on a laptop as on a big monitor
function fitFrame(ratio){const pv=$('dub-preview');if(!pv)return;const design=!$('dt-stage-host')?.hidden,box=design?$('stage'):$('dub-frame');if(!box)return;
 // the layout's own place on the page (the panel itself is sticky, so its place moves while scrolling)
 const wrap=design?box.parentElement:$('dub-frame').closest('.dub-frame-wrap'),lay=pv.closest('.dub-layout')||pv,top=lay.getBoundingClientRect().top+window.scrollY,
  other=pv.offsetHeight-box.offsetHeight,room=Math.max(200,Math.min(900,innerHeight-top-other-14)),
  colW=Math.max(140,(wrap?.clientWidth||pv.clientWidth)-24),r=design?9/16:ratio||9/16;
 let h=room,w=h*r;if(document.fullscreenElement&&document.fullscreenElement.contains(box)){h=innerHeight-40;w=h*r;if(w>innerWidth-40){w=innerWidth-40;h=w/r}}else if(w>colW){w=colW;h=w/r}
 if(design){const want=Math.round(w)+'px';if(box.style.width!==want)box.style.width=want}
 else{const ww=Math.round(w)+'px',hh=Math.round(h)+'px';if(box.style.width!==ww||box.style.height!==hh)Object.assign(box.style,{width:ww,height:hh})}}
addEventListener('resize',()=>{clearTimeout(fitFrame.t);fitFrame.t=setTimeout(()=>preview(),120)});
// CapCut-like player bar: seek on top; time · play · "Tỷ lệ ▾" + full screen below. One bar for the plain frame and one for
// the design stage, both built here; the ratio menu sets "Khung xuất" (the design stage is 9:16 only)
const RATIOS=[['9:16','9:16 · TikTok, Reels'],['16:9','16:9 · YouTube'],['1:1','1:1 · vuông'],['4:5','4:5 · bài đăng'],['source','Gốc · theo video']];
function playerTools(wrapOf){const t=el('span',{className:'cc-tools'}),btn=el('button',{type:'button',className:'cc-ratio',title:'Tỷ lệ khung xuất'}),menu=el('div',{className:'cc-ratio-menu',hidden:true});
 menu.append(...RATIOS.map(([v,label])=>{const b=el('button',{type:'button',textContent:label});b.dataset.c=v;b.onclick=e=>{e.stopPropagation();menu.hidden=true;if(b.disabled)return;const c=$('dub-canvas');c.value=v;c.dispatchEvent(new Event('change',{bubbles:true}));c.dispatchEvent(new Event('input',{bubbles:true}));window.appHistory?.checkpoint?.()};return b}));
 btn.onclick=e=>{e.stopPropagation();menu.hidden=!menu.hidden};document.addEventListener('click',()=>{menu.hidden=true});
 const full=el('button',{type:'button',className:'cc-full',textContent:'⛶',title:'Xem toàn màn hình (Esc để thoát)'});full.onclick=()=>{const w=wrapOf();if(document.fullscreenElement)document.exitFullscreen();else w?.requestFullscreen?.().catch(()=>{})};
 t.append(btn,menu,full);return t}
function canvasChips(o){const design=designOn(),now=design?'9:16':o.frame_canvas;
 for(const b of document.querySelectorAll('.cc-ratio'))b.textContent='Tỷ lệ · '+(now==='source'?'Gốc':now)+' ▾';
 for(const b of document.querySelectorAll('.cc-ratio-menu button')){b.setAttribute('aria-pressed',String(b.dataset.c===now));b.disabled=design&&b.dataset.c!=='9:16';
  b.title=design&&b.dataset.c!=='9:16'?'Mẫu thiết kế (nền, khung, tiêu đề, nội dung) chỉ có khung 9:16. Tắt các nhóm đó để dùng khung khác.':''}}
$('dub-pv-play').closest('.dub-transport').append(playerTools(()=>$('dub-frame').closest('.dub-frame-wrap')));
document.addEventListener('fullscreenchange',()=>preview());
// what the preview shows: the video of the job being edited again (✎ Sửa), else the selected input
const cur=()=>{if(!editing)return files[sel];const it=editing.items[editing.at]||editing.items[0];return it&&{id:it.video_id,name:it.name}};
function preview(){sel=Math.max(0,Math.min(sel,files.length-1));const ov=pickOverlay(settings());adjustPreview(settings());drawLayers();layerZ();if(window.dubProfile?.preview?.(cur())){layerZ();fitFrame();canvasChips(settings());return}const f=cur();$('dub-frame-empty').hidden=!!f;for(const v of [fg,bgv])v.hidden=!f;
 if(!f&&previewKey){previewKey='';if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl='';for(const v of [fg,bgv]){v.pause();v.removeAttribute('src');v.load()}}
 if(f?.path&&!f.id){if(!f.importing){f.importing=true;localImport(f).then(()=>preview()).catch(e=>{f.error=e.message;draw()})}}
 else if(f){const key=f.id||f.name+f.file?.size;if(key!==previewKey){previewKey=key;if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=f.file?URL.createObjectURL(f.file):'';const src=previewUrl||'/media/video/'+f.id;fg.src=src;bgv.src=src}}
 const o=settings(),frame=$('dub-frame'),[W,H]=CANVAS[o.frame_canvas]||[fg.videoWidth||9,fg.videoHeight||16];frame.style.aspectRatio=`${W}/${H}`;fitFrame(W/H);canvasChips(o);
 const box=frame.getBoundingClientRect(),fx=o.frame_flip.includes('h')?-1:1,fy=o.frame_flip.includes('v')?-1:1;
 let z=o.frame_zoom/100;const dx=o.frame_x*box.width/200,dy=o.frame_y*box.height/200,e=o.edge_trim||0,fit=o.frame_fit!=='cover'&&window.nearFit(fg.videoWidth-2*e,fg.videoHeight-2*e,W,H)?'cover':o.frame_fit;if(fit==='cover'&&z>=1&&box.width&&o.frame_rotate)z*=window.coverScale(box.width,box.height,box.width*z,box.height*z,box.width/2,box.height/2,o.frame_rotate,Math.max(box.width/540,(z-1)/2*Math.min(box.width,box.height)));
 Object.assign(fg.style,{width:z*100+'%',height:z*100+'%',objectFit:fit==='cover'?'cover':'contain',transform:`translate(-50%,-50%) translate(${o.frame_x*box.width/200}px,${o.frame_y*box.height/200}px) rotate(${o.frame_rotate}deg) scale(${fx},${fy})`});
 bgv.hidden=!f||fit!=='blur';
 drawImage(o,box,W,H);drawCaption(o,frame,box.width);$('dub-safezone').hidden=!$('dub-safe').checked;
 const level=o.background==='remove'?0:Math.min(1,(o.background_volume||0)/100*(o.background==='duck'?Math.max(.05,(o.duck_level||0)/100):1));fg.volume=level;fg.muted=level===0||fg.dataset.mute==='1';
 if(f&&fg.duration)$('dub-preview-info').textContent=`${f.name} · ${fg.videoWidth}×${fg.videoHeight} → ${W}×${H} · ${time(Math.max(0,fg.duration-o.trim_start-o.trim_end))} sau khi cắt`;
 $('dub-preview-note').textContent=!f?'':[`Âm nền như sau khi xử lý (${BG.find(b=>b[0]===o.background)[1].toLowerCase()})`,o.overlay?(ov?`overlay mẫu: ${ov.name}${ov.alpha?' · nền trong suốt, phủ full khung':''} (mỗi video chọn ngẫu nhiên${o.overlay_blend==='key'&&!ov.alpha?'; tách nền xanh chỉ thấy khi xuất':''})`:'overlay bật nhưng thư viện trống'):overlays.length?'overlay đang TẮT (tick "Thêm overlay" ở mục ✨ để chèn)':''].filter(Boolean).join(' · ')+'.';
 if(o.trim_start&&fg.currentTime<o.trim_start&&fg.paused)fg.currentTime=o.trim_start}
fg.onloadedmetadata=()=>{preview();$('dub-pv-seek').max=fg.duration||1};new ResizeObserver(()=>preview()).observe($('dub-frame'));
// custom transport (the overlay layers cover the native controls); playback stays inside the trimmed range
$('dub-pv-play').onclick=()=>{if(fg.paused){const o=settings();if(fg.currentTime<o.trim_start||fg.currentTime>fg.duration-o.trim_end-.05)fg.currentTime=o.trim_start;fg.play().catch(()=>{});bgv.play().catch(()=>{})}else{fg.pause();bgv.pause()}};
// the overlay plays with the video like in the export: same start (after the cut), looped, paused and seeked together
function syncOverlay(){const ovv=$('dub-ovv');if(ovv.hidden||!ovv.duration||!isFinite(ovv.duration))return;const o=settings(),at=Math.max(0,fg.currentTime-o.trim_start)%ovv.duration;
 const d=Math.abs(ovv.currentTime-at);if(Math.min(d,ovv.duration-d)>.25)ovv.currentTime=at;if(fg.paused){if(!ovv.paused)ovv.pause()}else if(ovv.paused)ovv.play().catch(()=>{})}
fg.onplay=()=>{$('dub-pv-play').textContent='❚❚';syncOverlay()};fg.onpause=()=>{$('dub-pv-play').textContent='▶';syncOverlay()};fg.onseeked=syncOverlay;$('dub-ovv').loop=true;
fg.ontimeupdate=()=>{syncOverlay();const o=settings();$('dub-pv-seek').value=fg.currentTime;$('dub-pv-time').textContent=time(Math.max(0,fg.currentTime-o.trim_start));if(Math.abs(bgv.currentTime-fg.currentTime)>.3)bgv.currentTime=fg.currentTime;if(!fg.paused&&fg.duration&&fg.currentTime>=fg.duration-o.trim_end){fg.pause();bgv.pause()}};
$('dub-pv-seek').oninput=()=>{fg.currentTime=Number($('dub-pv-seek').value);bgv.currentTime=fg.currentTime;syncOverlay()};

// ---- start
function upload(f){return new Promise((resolve,reject)=>{const x=new XMLHttpRequest();x.open('POST','/upload');x.setRequestHeader('X-Filename',encodeURIComponent(f.name));x.upload.onprogress=e=>{if(e.lengthComputable){const p=Math.round(e.loaded/e.total*100);if(p!==f.progress){f.progress=p;rowProgress(f)}}};x.onload=()=>{let d={};try{d=JSON.parse(x.responseText)}catch{}x.status<300?resolve(d):reject(Error(f.name+': '+(d.error||'tải lên thất bại')))};x.onerror=()=>reject(Error('Mất kết nối khi tải video.'));x.send(f.file)})}
$('dub-start').onclick=async()=>{if(editing){reexportEditing();return}if(!files.length){say('Chọn ít nhất một video ở mục 🎬.');$('sec-input').open=true;return}const o=settings();if(o.mode!=='design'&&!o.voice_id){say('Chọn giọng đọc ở mục 🎙.');$('sec-voice').open=true;$('dub-voice').focus();return}
 if(!await precheck(o))return;run(o)};
// ---- check before a run: duration, estimated cost, keys and what is missing (estimate only, nothing is sent to AI)
async function precheck(o){const dlg=$('dub-check'),body=$('dub-check-body'),build=o.mode==='design',n=files.length;
 const aiTexts=!!o.design&&[o.title_source,o.body_source].includes('ai'),openai=!!($('dub-openai').value||caps.openai),ai33=!!($('dub-ai33').value||$('tts-key')?.value||caps.ai33);
 const row=(k,v,cls='')=>[el('span',{textContent:k}),el('span',{className:cls,textContent:v})];
 body.replaceChildren(el('p',{className:'helper',textContent:'Đang đo thời lượng video…'}));$('dub-check-go').textContent=`▶ ${build?'Xuất':'Lồng tiếng'} ${n} video`;$('dub-check-go').disabled=true;dlg.showModal();
 // the server measures each video, finds older runs it can reuse and counts the real prompt (with frames) per video
 let durations={},videos={};const ref=f=>f.id||f.path;
 try{const d=await json('/dub/estimate',{ids:files.filter(f=>f.id).map(f=>f.id),paths:files.filter(f=>!f.id&&f.path).map(f=>f.path),options:o,hints:Object.fromEntries(files.filter(hintOf).map(f=>[ref(f),hintOf(f)]))});durations=d.durations||{};videos=d.videos||{}}catch{}
 const secs=files.map(f=>durations[ref(f)]),known=secs.filter(v=>v>0),total=known.reduce((a,b)=>a+b,0),avg=known.length?total/known.length:0,est=total+avg*(n-known.length),min=est/60;
 const vnd=v=>Math.round(v*USD_VND).toLocaleString('vi-VN'),costs=files.map(f=>videos[ref(f)]?.cost).filter(Boolean),scale=costs.length?n/costs.length:1;
 const sum=k=>costs.reduce((a,c)=>a+(c[k]||0),0)*scale,usd=sum('usd'),chars=Math.round(sum('ai33_chars')),minutes=sum('ai33_minutes');
 const uses=[...new Set(costs.flatMap(c=>c.uses))],openaiUse=uses.length?uses.join(' · '):'không dùng';
 const reused=files.map(f=>videos[ref(f)]?.reuse).filter(Boolean),LV={voice:'bản dịch + giọng',trans:'bản dịch',texts:'chữ AI',asr:'lời gốc'};
 const reuseText=reused.length?`${reused.length}/${n} video dùng lại kết quả cũ (${Object.entries(reused.reduce((m,l)=>(m[l]=(m[l]||0)+1,m),{})).map(([l,c])=>`${LV[l]}: ${c}`).join(', ')}) · không tốn lại API phần đó`:'';
 const withMp3=0,useMp3=0,warn=[];
 if(usd&&!openai)warn.push('Chưa có OpenAI key: '+(build?'tiêu đề lấy theo tên file.':'không chạy được.'));
 if(!build&&!ai33)warn.push('Chưa có ai33 key: không tạo được giọng đọc.');
 if(o.overlay&&!overlays.some(x=>ovAll||ovUse.has(x.id)))warn.push('Bật overlay nhưng chưa chọn overlay nào: video xuất không có overlay.');
 if(o.image&&!o.image_id)warn.push('Bật lớp ảnh nhưng chưa chọn ảnh: video xuất không có lớp ảnh.');
 // checks that used to show only after the export
 if(o.captions&&caps.ass===false)warn.push('Bật phụ đề chữ chạy nhưng bản FFmpeg trên máy thiếu libass: video xuất sẽ không có phụ đề. Xóa thư mục bin rồi mở lại app để tự tải bản FFmpeg đầy đủ.');
 if(o.music&&!music.length)warn.push('Bật nhạc nền nhưng kho nhạc trống: video xuất không có nhạc nền.');
 if(o.captions){const cy=o.caption_y/100*1280,half=o.caption_size*720/1080*.8,d=o.design||{},box=(k)=>{const y=+d[k+'_y'],h=+(d[k+'_height']||(d[k+'_size']||0)*1.4);return Number.isFinite(y)&&h>0?[y,y+h]:null};
  for(const[k,label,on]of [['title','tiêu đề',o.design_title],['body','nội dung',o.design_body]]){const b=on!==false&&o.design?box(k):null;if(b&&cy+half>b[0]&&cy-half<b[1])warn.push(`Phụ đề chữ chạy (vị trí dọc ${o.caption_y}%) đè lên ${label}: kéo chữ mẫu trên khung xem trước lên/xuống.`)}
  if(o.caption_y>80)warn.push(`Phụ đề chữ chạy ở ${o.caption_y}% chiều cao: TikTok che phần này (tên kênh, mô tả). Nên để 55–75%.`);
  if(o.caption_y<12)warn.push(`Phụ đề chữ chạy ở ${o.caption_y}% chiều cao: sát thanh trên của TikTok.`)}
 const bad=files.filter(f=>f.error).length;if(bad)warn.push(`${bad} video đang báo lỗi ở danh sách.`);
 if(known.length<n)warn.push(`${n-known.length} video chưa đo được thời lượng (ước theo trung bình).`);
 const voice=build?'0 credit · không có giọng đọc':(o.mode==='ai33'?`tính theo thời lượng ≈ ${minutes.toFixed(1)} phút (+25% khi dùng giọng thay thế)`:`≈ ${chars.toLocaleString('vi-VN')} ký tự giọng đọc (credit tính theo ký tự)`);
 body.replaceChildren(el('div',{className:'dub-check-grid'},...row('Số video',`${n} video`),...row('Tổng thời lượng',`${time(est)}${known.length<n?' (ước tính)':''}`),
  ...row('OpenAI',usd?`≈ $${usd.toFixed(3)} · ~${vnd(usd)} đ · ${openaiUse}`:'0 đ · '+openaiUse),...row('ai33',voice),
  ...row('Key',`OpenAI ${openai?'✓':'✗'} · ai33 ${build?'không cần':ai33?'✓':'✗'}`,(usd&&!openai)||(!build&&!ai33)?'bad':'ok'),
  ...(reuseText?row('Dùng lại',reuseText,'ok'):[]),...(o.vision&&usd?row('AI xem hình','3 khung hình mỗi video (đã tính vào giá)'):[]),
  ...row('Chạy',`${$('dub-parallel').value} video cùng lúc · ${$('encoder')?.selectedOptions[0]?.textContent||'CPU'}`),
  ...(o.review_texts&&aiTexts?row('Duyệt chữ','dừng lại để duyệt tiêu đề/nội dung trước khi xuất'):[])),
  ...(warn.length?[el('div',{className:'group-label',textContent:'CẢNH BÁO'}),el('ul',{className:'dub-check-warn'},...warn.map(w=>el('li',{textContent:w})))]:[el('p',{className:'dub-check-ok',textContent:'✓ Không có cảnh báo.'})]),
  el('p',{className:'helper',textContent:'Giá là ước tính theo bảng giá OpenAI và độ dài câu lệnh thật, có thể chênh. Lỗi mạng tạm thời được tự thử lại 3 lần. Video lỗi không chặn các video khác.'}));
 $('dub-check-go').disabled=false;
 return new Promise(resolve=>{const done=v=>{dlg.close();resolve(v)};$('dub-check-go').onclick=()=>done(true);$('dub-check-back').onclick=()=>done(false);dlg.oncancel=()=>resolve(false)})}
async function run(o,only=null){
 if(o.overlay&&!overlays.some(x=>ovAll||ovUse.has(x.id))){o.overlay=false;say('Chưa chọn overlay nào nên video xuất không có overlay (overlay không bắt buộc).')}
 // each video is uploaded and queued on its own: processing starts with the first one, and a bad file does not stop the rest
 $('dub-start').disabled=$('dub-trial').disabled=true;const list=only?[only]:[...files],total=list.length,failed=[];let queued=0,first='';
 try{for(const f of list){say(`Đang tải và xếp hàng ${queued+failed.length+1}/${total}: ${f.name}…`);
   try{if(!f.id){const d=f.path?await localImport(f):await upload(f);f.id=d.id;f.progress=null}
    const r=await json('/dub/start',{video_ids:[f.id],srt:f.srt?{[f.id]:f.srt}:{},hints:hintOf(f)?{[f.id]:hintOf(f)}:{},options:o,...keys()});first=first||r.jobs[0];queued++;files.splice(files.indexOf(f),1);f.row?.remove()}
   catch(e){f.error=e.message;f.progress=null;failed.push(f);if(f.row){const t=f.row.querySelector('small');t.textContent='lỗi: '+e.message.slice(0,60);t.title=e.message}}
   if(queued%10===1)refresh()}
  say(`Đã thêm ${queued}/${total} video vào hàng đợi; ứng dụng chạy ${$('dub-parallel').value==='1'?'lần lượt từng video':$('dub-parallel').value+' video cùng lúc'}.`+(failed.length?` ${failed.length} video lỗi vẫn nằm trong danh sách (di chuột vào chữ "lỗi" để xem lý do).`:''));
  sel=0;draw();if(first)current=first;filter='all';if(only){trial=first?{id:first?.id||first,left:files.length}:null;if(!first)say('🧪 Không chạy thử được video đầu tiên: '+(failed[0]?.error||'lỗi khi tải video')+'. Sửa rồi bấm Chạy thử lại.')}trialBar();refresh()}finally{$('dub-start').disabled=$('dub-trial').disabled=false;startLabel()}}
// ---- ✎ "Sửa & xuất lại": the job's own settings go to the left panel and its source video to the preview; change the
// look and export again. Recognised speech, translation, title/body and voice are kept (server: KEEP_ON_REEXPORT).
let beforeEdit=null;
// one job, or many (ticked rows, "✎ Sửa hàng loạt"): the first one's settings and video are shown; the export goes to all
// the videos being edited take the place of the input list (click one to preview it); "Bắt đầu" becomes "Xuất lại N video"
const editItem=j=>({id:j.id,video_id:j.video_id,name:shown(j),src:j.name,state:j.state});
async function editJob(job,ids=[job.id]){try{const full=await request('/dub/'+job.id);if(!editing)beforeEdit=settings();apply({...full.options,design:full.options.design});
  const items=[...new Set([job.id,...ids])].map(id=>jobMap.get(id)||(id===job.id?job:null)).filter(j=>j&&j.video_id).map(editItem);
  editing={id:job.id,get ids(){return this.items.map(x=>x.id)},items,at:0,name:shown(job)};current=job.id;editBar();draw();startLabel();labels();$('sec-input').open=true;preview();refresh();
  say(editing.ids.length>1?`Đang sửa ${editing.ids.length} video (xem trước video đầu “${shown(job)}”): chỉnh thông số bên trái rồi bấm ⟳ Xuất lại ${editing.ids.length} video.`:`Đang sửa “${shown(job)}”: chỉnh thông số bên trái, xem trước ngay, rồi bấm ⟳ Xuất lại video này.`)}catch(e){say(e.message)}}
function exitEdit(){editing=null;if(beforeEdit)apply(beforeEdit);beforeEdit=null;editBar();draw();startLabel();labels();preview();refresh()}
async function reexportEditing(){if(!editing?.items.length)return;const b=$('dub-start');b.disabled=true;try{await batch('reexport',editing.ids,{options:settings()})}finally{b.disabled=false}}
function editList(){const n=editing.items.length;
 return [el('div',{className:'dub-list-head dub-edit-head'},el('span',{textContent:`✎ Sửa & xuất lại ${n} video từ hàng đợi`}),(()=>{const b=el('button',{type:'button',className:'chip-button',textContent:'✕ Thoát sửa'});b.onclick=exitEdit;return b})()),
  el('p',{className:'helper',textContent:'Bấm một video để xem trước. Cùng thông số bên trái áp dụng cho cả danh sách; lời dịch, chữ AI và giọng đọc giữ nguyên.'}),
  ...editing.items.map((it,i)=>{const x=el('button',{type:'button',className:'icon-button',textContent:'✕',title:'Bỏ khỏi lần sửa này'});x.onclick=e=>{e.stopPropagation();editing.items.splice(i,1);if(!editing.items.length){exitEdit();return}editing.at=Math.min(editing.at,editing.items.length-1);editBar();draw();startLabel();preview()};
   const row=el('div',{className:'dub-file dub-edit-item'+(i===editing.at?' current':'')},el('span',{className:'dub-edit-mark',textContent:'✎'}),el('div',{className:'dub-row-name'},el('strong',{textContent:it.name}),el('small',{textContent:(it.src&&it.src!==it.name?it.src+' · ':'')+({done:'đã xong',error:'lỗi',paused:'tạm dừng'})[it.state]+' · dùng lại giọng & chữ'})),x);
   row.onclick=()=>{editing.at=i;draw();editBar();preview()};return row})]}
function editBar(){const bar=$('dub-edit-bar');if(!editing){bar.hidden=true;return}bar.hidden=false;
 const n=editing.ids.length,go=el('button',{type:'button',className:'primary-action small-action',textContent:n>1?`⟳ Xuất lại ${n} video`:'⟳ Xuất lại video này'});go.onclick=async()=>{go.disabled=true;await reexportEditing();go.disabled=false};
 const all=el('button',{type:'button',className:'outline-action small-action',textContent:'＋ Thêm video đã tick',title:'Đưa các video đang tick ở hàng đợi vào lần sửa này (cùng thông số)'});
 all.onclick=()=>{const ids=[...selected].filter(id=>!editing.ids.includes(id));if(!ids.length){say('Tick thêm video ở hàng đợi (ô vuông đầu dòng) rồi bấm lại để đưa vào lần sửa này.');return}editing.items.push(...ids.map(id=>jobMap.get(id)).filter(j=>j&&j.video_id&&['done','error','paused'].includes(j.state)).map(editItem));editBar();draw();startLabel();say(`Đã thêm ${ids.length} video vào lần sửa · tổng ${editing.ids.length} video.`)};
 const exit=el('button',{type:'button',className:'icon-button',textContent:'✕',title:'Thoát sửa và trả lại thông số trước đó'});exit.onclick=exitEdit;
 const write=noAiTexts.filter(id=>editing.ids.includes(id));let ai=null;if(write.length){ai=el('button',{type:'button',className:'outline-action small-action',textContent:`✍ Viết chữ AI (${write.length} video)`,title:'Mỗi video 1 lần gọi OpenAI để viết tiêu đề / nội dung, rồi xuất lại'});const busy=write.some(id=>['queued','running'].includes(jobMap.get(id)?.state));if(busy){ai.disabled=true;ai.textContent+=' · chờ xuất xong'}
  ai.onclick=async()=>{if(!confirm(`Viết chữ AI cho ${write.length} video? Mỗi video 1 lần gọi OpenAI, giọng đọc giữ nguyên.`))return;ai.disabled=true;let ok=0;for(const id of write){try{await json(`/dub/${id}/continue`,{from:'texts',...keys()});ok++}catch(e){say(e.message)}}noAiTexts=noAiTexts.filter(id=>!write.includes(id));say(`Đang viết chữ AI cho ${ok} video rồi xuất lại.`);editBar();refresh()}}
 bar.replaceChildren(el('div',{},el('strong',{textContent:n>1?`✎ Đang sửa ${n} video · xem trước: ${(editing.items[editing.at]||{}).name}`:'✎ Đang sửa: '+(editing.items[0]||{}).name}),el('small',{className:'helper',textContent:'Chỉ đổi phần hình và tiếng nền (khung, màu, nền, chữ, phụ đề, lớp, nhạc, thông số xuất). Lời dịch, chữ AI và giọng đọc giữ nguyên, không gọi lại API.'})),el('div',{className:'dub-actions'},go,...(ai?[ai]:[]),all,exit))}
// ---- 🧪 "Chạy thử 1 video\": the first video runs alone; when it is done the bar offers the rest of the list
$('dub-trial').onclick=()=>{if(!files.length)return;const o=settings();if(o.mode!=='design'&&!o.voice_id){say('Chọn giọng đọc ở mục 🎙.');$('sec-voice').open=true;return}say('Chạy thử video đầu tiên; xong sẽ hiện nút chạy phần còn lại.');run(o,files[0])};
function trialBar(){const bar=$('dub-trial-bar');if(!trial){bar.hidden=true;return}const j=jobMap.get(trial.id),n=files.length;bar.hidden=false;
 const close=el('button',{type:'button',className:'icon-button',textContent:'✕',title:'Ẩn'});close.onclick=()=>{trial=null;trialBar()};
 if(!j||['queued','running'].includes(j.state)){bar.replaceChildren(el('span',{textContent:`🧪 Đang chạy thử “${j?shown(j):'video đầu tiên'}”${j?` · ${j.progress||0}%`:''}… ${n} video còn lại chờ bạn duyệt kết quả.`}),close);return}
 const look=el('button',{type:'button',className:'outline-action small-action',textContent:j.state==='done'?'▶ Xem video thử':'Xem chi tiết'});look.onclick=()=>{current=j.id;if(j.state==='done')playNext=j.id;window.dubProfile?.previewJob?.(j);refresh()};
 const rest=el('button',{type:'button',className:'primary-action small-action',textContent:`▶ Ưng rồi · chạy ${n} video còn lại`,disabled:!n});rest.onclick=async()=>{const o=settings();if(!await precheck(o))return;trial=null;trialBar();run(o)};
 bar.replaceChildren(el('span',{textContent:j.state==='done'?`🧪 Video thử đã xong. Ưng giọng, chữ, khung thì chạy phần còn lại; chưa ưng thì sửa thông số bên trái rồi bấm Chạy thử lại.`:j.state==='review'?'🧪 Video thử đang chờ duyệt chữ AI.':`🧪 Video thử ${STATE[j.state]?.toLowerCase()}: ${j.message||''}`}),look,rest,close)}

// ---- queue: compact rows, filters and bulk actions
// ---- translation model: price per video and what each model is good for (estimate only)
const USD_VND=26000;let models=[];
function modelNote(){const id=$('dub-model').value.trim(),m=models.find(x=>x.id===id),o=settings();if(!m){$('dub-model-note').textContent=id?'Model tự nhập: giá theo bảng giá OpenAI của model đó.':'';return}
 // one minute of speech ≈ 3,000 input tokens (rules + template + transcript) and ~700 output (+1,500 hidden reasoning)
 const usd=(3000*m.price[0]+(700+(m.think?1500:0))*m.price[1])/1e6,asr=caps.whisper_per_minute||.006,vnd=v=>Math.max(1,Math.round(v*USD_VND));
 $('dub-model-note').textContent=`${m.use}. Ước tính mỗi phút video: dịch ≈ $${usd.toFixed(4)} (~${vnd(usd)}đ) + nhận diện Whisper $${asr} (~${vnd(asr)}đ). Giá ${m.price[0]}$/${m.price[1]}$ mỗi 1 triệu token vào/ra, tham khảo, có thể đổi theo OpenAI.`}
function drawModels(){const pick=$('dub-model-pick'),id=$('dub-model').value.trim()||'gpt-4.1-mini';pick.replaceChildren(...models.map(m=>new Option(`${m.id} · ${m.use.split(' · ')[0]}`,m.id)),new Option('Khác… (tự nhập tên model)','__custom'));
 const known=models.some(m=>m.id===id);pick.value=known?id:'__custom';$('dub-model').hidden=known;modelNote()}
$('dub-model-pick').onchange=()=>{const v=$('dub-model-pick').value;$('dub-model').hidden=v!=='__custom';if(v!=='__custom')$('dub-model').value=v;else $('dub-model').focus();remember();modelNote()};
$('dub-model').addEventListener('input',modelNote);
// the queue shows the file name the AI gave (quan-ao-nu-hottrend); the source file name stays below it
const shown=j=>j.file_name||j.name;
const STATE={queued:'Đang chờ',running:'Đang chạy',review:'Chờ duyệt',paused:'Tạm dừng',error:'Lỗi',done:'Hoàn tất'};
const GROUP={all:['Tất cả',()=>true],active:['Đang chạy',j=>['queued','running'].includes(j.state)],todo:['Cần xử lý',j=>['error','paused','review'].includes(j.state)],done:['Xong',j=>j.state==='done']};
function stepDots(job){return el('div',{className:'dub-dots'},...STEPS.map(([k,n,t])=>{const s=k==='tts'?(job.steps.tts==='done'&&job.steps.mix!=='done'?'running':job.steps.tts):job.steps[k];return el('span',{className:'dub-dot '+s,title:`${n} ${t} · ${({pending:'chưa chạy',running:'đang chạy',done:'xong',skipped:'bỏ qua',error:'lỗi'})[s]}`},n)}))}
function actionsFor(job,compact=false){const actions=el('div',{className:'dub-actions'});const btn=(t,fn,cls='outline-action',title='')=>{const b=el('button',{type:'button',className:cls+' small-action',textContent:t,title});b.onclick=async e=>{e.stopPropagation();b.disabled=true;try{await fn()}catch(err){say(err.message)}finally{b.disabled=false;refresh()}};actions.append(b);return b};
 if(['queued','running'].includes(job.state))btn('■ Dừng',()=>json(`/dub/${job.id}/cancel`));
 if(['review','paused','error'].includes(job.state))btn('▶ Tiếp tục',()=>json(`/dub/${job.id}/continue`,{...keys(),options:compact?undefined:settings()}),'primary-action',compact?'Chạy tiếp với thông số của tác vụ':'Chạy tiếp với thông số đang chọn bên trái');
 if(['done','error','paused'].includes(job.state)&&job.video_id)btn(editing?.id===job.id?'✎ Đang sửa':'✎ Sửa',()=>editJob(job),'outline-action','Mở lại video gốc với thông số của video này để chỉnh khung, lớp, phụ đề, nhạc… rồi xuất lại (không gọi lại API dịch hay tạo giọng)');
 if(job.state==='done'){if(compact)btn('▶ Xem',async()=>{current=job.id;playNext=job.id},'outline-action','Xem video đã lồng tiếng ngay tại đây');const a=el('a',{className:'primary-action small-action',href:job.outputs.video+'?download=1',textContent:'⬇ MP4'});a.onclick=e=>e.stopPropagation();actions.append(a)}
 if(compact)return actions;
 if(job.mode==='paragraph'&&['error','paused','review'].includes(job.state)&&job.steps.tts!=='done'&&job.lines){btn('⬆ Dùng MP3 đã tạo',()=>new Promise((resolve,reject)=>{const input=el('input',{type:'file',accept:'audio/*,.mp3,.wav,.m4a'});input.onchange=async()=>{const f=input.files[0];if(!f)return resolve();say('Đang tải file giọng '+f.name+'…');try{await request(`/dub/${job.id}/voice`,{method:'POST',headers:{'X-Filename':encodeURIComponent(f.name)},body:f});say('Đã nhận file giọng, đang xuất video…');resolve()}catch(e){reject(e)}};input.click()}),'outline-action','Tải MP3 ai33 đã tạo để ứng dụng căn giọng và xuất video luôn')}
 if(job.lines){const open=openDetail===job.id;btn(open?'✕ Đóng bản dịch':'✎ Bản dịch',async()=>{openDetail=open?'':job.id;current=job.id;dirty=false})}
 if(job.state==='done'){if(job.outputs.srt){const s=el('a',{className:'outline-action small-action',href:job.outputs.srt,textContent:'SRT Việt'});s.onclick=e=>e.stopPropagation();actions.append(s)}if(job.outputs.saved_path)btn('📁 Mở thư mục',()=>json('/settings/open-folder'));}
 if(!['queued','running'].includes(job.state))btn('Xóa',async()=>{if(confirm(`Xóa tác vụ lồng tiếng "${job.name}"? Video gốc trong kho vẫn giữ.`)){await json(`/dub/${job.id}/delete`);if(current===job.id){current='';detail=null}}},'outline-action danger-action');
 return actions}
// finished rows open with the dubbed video playing inline; the player is kept across queue refreshes
const players=new Map();let playNext='';
function player(job){const src=job.outputs.video,key=job.id+'|'+src;let v=players.get(job.id);if(!v||v.dataset.key!==key){v=el('video',{className:'dub-player dub-inline-player',src:src+(src.includes('?')?'&':'?')+'t='+(job.updated||Date.now()),controls:true,playsInline:true,preload:'metadata'});v.dataset.key=key;v.onclick=e=>e.stopPropagation();players.set(job.id,v)}
 if(playNext===job.id){playNext='';setTimeout(()=>v.play().catch(()=>{}),50)}return v}
// title/body of a design job: edit and export again, or let the AI write them again (one call)
const textDrafts=new Map();
// the AI writes 3 titles / 2 bodies (short → long); the app picked the best one, a click takes another
const FLAG={'dài':'vượt giới hạn','ngắn':'ngắn hơn tối thiểu','giá/thông số':'có giá hoặc thông số','cụt':'kết thúc bằng từ nối','trống':'trống'};
function optionChips(job,k,pick){const list=(job.text_options||{})[k]||[];if(list.length<2)return null;
 return el('div',{className:'dub-opts'},el('small',{textContent:'Phương án AI:'}),...list.map((t,n)=>{const b=el('button',{type:'button',className:'chip-button',textContent:`${n+1} · ${t.length}`,title:t});b.onclick=e=>{e.stopPropagation();pick(t)};return b}))}
function flagNote(job,k){const f=((job.text_flags||{})[k]||[]).filter(x=>FLAG[x]);return f.length?el('small',{className:'dub-flag',textContent:'⚠ '+f.map(x=>FLAG[x]).join(', ')}):null}
function textEditor(job){const d=textDrafts.get(job.id)||{...job.texts};const busy=['queued','running'].includes(job.state);
 const field=(k,label,max)=>{const i=el(k==='body'?'textarea':'input',{value:d[k]||'',maxLength:max,disabled:busy,rows:2});i.oninput=()=>{d[k]=i.value;textDrafts.set(job.id,d)};i.onclick=e=>e.stopPropagation();const lab=el('label',{textContent:`${label} · ${i.value.trim().length} ký tự`});i.addEventListener('input',()=>{lab.textContent=`${label} · ${i.value.trim().length} ký tự`});
  const chips=busy?null:optionChips(job,k,t=>{i.value=t;i.dispatchEvent(new Event('input'))});return el('div',{},lab,i,...[chips,flagNote(job,k)].filter(Boolean))};
 const save=el('button',{type:'button',className:'primary-action small-action',textContent:'Lưu chữ & xuất lại',disabled:busy});save.onclick=async e=>{e.stopPropagation();try{await json(`/dub/${job.id}/texts`,d);textDrafts.delete(job.id);await json(`/dub/${job.id}/continue`,keys());say('Đã lưu chữ, đang xuất lại video.');refresh()}catch(err){say(err.message)}};
 const again=el('button',{type:'button',className:'outline-action small-action',textContent:'Viết lại chữ AI',disabled:busy});again.onclick=async e=>{e.stopPropagation();try{textDrafts.delete(job.id);await json(`/dub/${job.id}/continue`,{from:'texts',...keys()});say('Đang viết lại tiêu đề và nội dung (giữ nguyên giọng đã có)…');refresh()}catch(err){say(err.message)}};
 return el('div',{className:'dub-texts'},el('div',{className:'two-col'},field('title','Tiêu đề',160),field('body','Nội dung',600)),el('div',{className:'dub-actions'},save,again))}
// tên file typed by hand: same rules as the AI's name (no accents, lower case, '-', at most 45 characters)
const slug=t=>{let x=String(t||'').replace(/đ/g,'d').replace(/Đ/g,'D').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');if(x.length>45){const c=x.slice(0,46).lastIndexOf('-');x=c>=30?x.slice(0,c):x.slice(0,45);const p=x.split('-'),links=new Set(['cho','va','cua','voi','de','la','thi','ma','nhung','hay','hoac','cac','mot','khi','tu','trong','o','tai','ve','theo','den','rat','cung','nen','vi','do','duoc','bi','se','da','dang']);while(p.length>3&&links.has(p[p.length-1]))p.pop();x=p.join('-')}return x.replace(/-+$/,'')};
function nameEditor(job){const i=el('input',{type:'text',maxLength:120,value:job.file_name||'',placeholder:'ten-file-theo-san-pham',spellcheck:false}),out=el('small',{className:'helper'}),b=el('button',{type:'button',className:'outline-action small-action',textContent:'Đổi tên'});
 const show=()=>{const n=slug(i.value);out.textContent=n.length>=3?`→ ${n}.mp4${job.outputs?.saved_path?' · đổi luôn file đã lưu':''}`:'cần ít nhất 3 chữ/số';b.disabled=n.length<3||n===job.file_name};
 i.oninput=show;i.onclick=e=>e.stopPropagation();i.onkeydown=e=>{if(e.key==='Enter')b.click()};
 b.onclick=async e=>{e.stopPropagation();b.disabled=true;try{const r=await json(`/dub/${job.id}/name`,{file_name:i.value});say(r.message&&r.outputs?.saved_path?r.message:`Tên file: ${r.file_name}.mp4`);refresh()}catch(err){say(err.message);b.disabled=false}};show();
 const info=[job.video_title&&'Tiêu đề file: '+job.video_title,job.tags?.length&&'Tags: '+job.tags.join('; ')].filter(Boolean);
 return el('div',{className:'dub-name-edit'},el('label',{textContent:'Tên file'}),el('div',{className:'dub-name-row'},i,b),out,...info.map(t=>el('small',{className:'helper',textContent:t})))}
function card(job){const open=job.id===current;if(job.state!=='done')players.delete(job.id);
 const tick=el('input',{type:'checkbox',className:'dq-tick',checked:selected.has(job.id),title:'Chọn để thao tác hàng loạt'});tick.onclick=e=>{e.stopPropagation();tick.checked?selected.add(job.id):selected.delete(job.id);selectBar()};
 const pos=job.state==='queued'?waiting.indexOf(job.id):-1;
 const box=el('div',{className:'dub-job '+job.state+(open?' current':'')+(selected.has(job.id)?' picked':'')},el('div',{className:'dub-row-main'},el('span',{className:'dq-lead'},tick,el('span',{className:'dub-state-dot '+job.state,title:STATE[job.state]})),el('div',{className:'dub-row-name'},el('strong',{textContent:shown(job),title:job.file_name?`Tên do AI đặt theo sản phẩm · file gốc: ${job.name}`:job.name}),el('small',{textContent:(job.file_name?job.name+' · ':'')+time(job.duration)+(job.lines?` · ${job.lines} câu`:'')+(job.reused?' · ♻ dùng lại':'')+(job.hint?' · 💡':''),title:[job.hint&&'Gợi ý: '+job.hint,job.file_name_alt&&'Tên dự phòng: '+job.file_name_alt,job.reused&&'Dùng lại kết quả của lần chạy trước'].filter(Boolean).join('\n')})),stepDots(job),
  el('div',{className:'dub-row-progress'},el('div',{className:'export-bar'},el('i',{style:`width:${job.progress||0}%`})),el('small',{textContent:(job.progress||0)+'%'})),el('span',{className:'badge '+(job.state==='done'?'done':job.state==='error'?'error':'doing'),textContent:pos>=0?`Chờ · #${pos+1}`:job.state==='running'&&STEP_NAME[job.step]?STEP_NAME[job.step]:STATE[job.state]||job.state,title:pos>=0?`Thứ ${pos+1} trong hàng chờ · chọn rồi bấm ⤒ Ưu tiên để chạy trước`:''}),open?el('span'):actionsFor(job,true)),
  el('small',{className:'dub-msg',textContent:job.message||''}));
 if(open)box.append(nameEditor(job));
 if(open&&job.texts)box.append(textEditor(job));
 if(open&&job.state==='done'&&job.outputs?.video&&openDetail!==job.id)box.append(player(job));
 if(open)box.append(...(job.warnings||[]).slice(0,4).map(w=>el('small',{className:'dub-warn',textContent:'⚠ '+w})),actionsFor(job));
 box.onclick=e=>{if(e.target.closest('button,a,video'))return;if(open)players.get(job.id)?.pause();current=open?'':job.id;if(!open&&job.state==='done')playNext=job.id;window.dubProfile?.previewJob?.(open?null:job);refresh()};return box}
// ---- review table: AI title/body of every job waiting before the export, edited in one place
const waitingTexts=()=>jobs.filter(j=>j.state==='review'&&j.step==='export'&&j.texts);
const words=t=>(String(t||'').trim().match(/\S+/g)||[]).length;
let reviewDraft=new Map(),reviewMax=200;
function reviewBar(){const n=waitingTexts().length,bar=$('dub-review-bar');bar.hidden=!n;if(n)$('dub-review-count').textContent=`${n} video chờ duyệt chữ AI trước khi xuất`}
function openReview(){reviewDraft=new Map();reviewMax=200;drawReview();$('dub-treview').showModal()}
function drawReview(){const list=waitingTexts(),limits={title:+($('dt-title-chars')?.value||30),min:+($('dt-body-min')?.value||50),max:+($('dt-body-max')?.value||100)};
 $('dub-review-info').textContent=list.length?`${list.length} video · sửa trực tiếp trong bảng, ô đỏ là vượt giới hạn ký tự (tiêu đề ≤ ${limits.title}, nội dung ${limits.min}–${limits.max}).`:'Không còn video nào chờ duyệt.';$('dub-review-go').textContent=`▶ Xuất tất cả (${list.length})`;$('dub-review-go').disabled=!list.length;
 const rows=list.slice(0,reviewMax).map((j,i)=>{const d=reviewDraft.get(j.id)||{title:j.texts.title||'',body:j.texts.body||''};
  const count=(c,k,v)=>{const n=String(v||'').trim().length,over=k==='title'?n>limits.title:n<limits.min||n>limits.max;c.className='dub-review-n'+(over?' over':'');c.textContent=`${n} ký tự`};
  const cell=(k,tag,max)=>{const box=el(tag,{value:d[k],maxLength:max,rows:2}),c=el('small');count(c,k,d[k]);box.oninput=()=>{d[k]=box.value;reviewDraft.set(j.id,d);count(c,k,box.value)};
   const flag=reviewDraft.has(j.id)?null:flagNote(j,k);return el('div',{className:'dub-review-cell'+(flag?' flagged':'')},box,c,...[optionChips(j,k,t=>{box.value=t;box.dispatchEvent(new Event('input'))}),flag].filter(Boolean))};
  const again=el('button',{type:'button',className:'outline-action small-action',textContent:'↻ AI viết lại',title:'Viết lại chữ cho video này (1 lần gọi OpenAI), rồi duyệt lại'});again.onclick=async()=>{again.disabled=true;try{reviewDraft.delete(j.id);await json(`/dub/${j.id}/continue`,{from:'texts',...keys()});say(`Đang viết lại chữ cho "${j.name}"…`);await refresh();drawReview()}catch(e){say(e.message);again.disabled=false}};
  return el('div',{className:'dub-review-row'},(()=>{const box=el('input',{type:'text',className:'dub-review-file',maxLength:120,value:d.file_name??(j.file_name||''),placeholder:'tên file',spellcheck:false,title:'Tên file xuất (không dấu, nối bằng -)'}),hint=el('small',{textContent:time(j.duration)+(j.file_name_alt?' · dự phòng: '+j.file_name_alt:'')});
   box.oninput=()=>{d.file_name=box.value;reviewDraft.set(j.id,d);const n=slug(box.value);hint.textContent=n.length>=3?`→ ${n}.mp4`:'cần ít nhất 3 chữ/số'};
   return el('div',{className:'dub-review-name'},el('strong',{textContent:(i+1)+'.'}),box,hint)})(),cell('title','input',160),cell('body','textarea',600),again)});
 $('dub-review-body').replaceChildren(el('div',{className:'dub-review-row head'},el('span',{textContent:'Video'}),el('span',{textContent:'Tiêu đề'}),el('span',{textContent:'Nội dung'}),el('span')),...rows,...(list.length>reviewMax?[(()=>{const b=el('button',{type:'button',className:'outline-action small-action',textContent:`Hiện thêm (còn ${list.length-reviewMax})`});b.onclick=()=>{reviewMax+=200;drawReview()};return b})()]:[]))}
$('dub-review-close').onclick=()=>$('dub-treview').close();
$('dub-review-go').onclick=async()=>{const list=waitingTexts(),b=$('dub-review-go');b.disabled=true;try{const items=list.map(j=>({id:j.id,...(reviewDraft.get(j.id)||{})}));const r=await json('/dub/review',{items,...keys()});
  say(`Đã duyệt ${r.done} video, đang xuất.`+(r.errors.length?` ${r.errors.length} video lỗi: ${r.errors[0].error}`:''));$('dub-treview').close();refresh()}catch(e){say(e.message)}finally{b.disabled=false}};
// ---- queue overview, filters, error groups, ticked rows
let waiting=[],parallel=1,selected=new Set(),search='',stepFilter='';
const STEP_NAME=Object.fromEntries(STEPS.map(([k,,t])=>[k,t]));
const clock=sec=>{sec=Math.max(0,Math.round(sec));const h=Math.floor(sec/3600),m=Math.floor(sec%3600/60);return h?`${h} giờ ${m} phút`:m?`${m} phút`:`${sec} giây`};
function overview(){const n=k=>jobs.filter(j=>j.state===k).length,total=jobs.length,done=n('done'),err=n('error'),run=n('running'),wait=n('queued'),review=n('review'),paused=n('paused');
 $('dq-overview').hidden=!total;if(!total)return;
 $('dq-bar-done').style.width=(done/total*100)+'%';$('dq-bar-err').style.width=(err/total*100)+'%';
 const spent=jobs.filter(j=>j.state==='done'&&j.spent>0).map(j=>j.spent),avg=spent.length?spent.reduce((a,b)=>a+b,0)/spent.length:0;
 const left=run+wait,eta=avg&&left?avg*left/Math.max(1,Math.min(parallel,left)):0;
 const part=(t,c,title='')=>el('span',{className:'dq-stat '+c,textContent:t,title});
 $('dq-stats').replaceChildren(part(`${done}/${total} xong`,'ok'),...(run?[part(`${run} đang chạy`,'run')]:[]),...(wait?[part(`${wait} đang chờ`,'wait')]:[]),...(review?[part(`${review} chờ duyệt`,'review')]:[]),...(paused?[part(`${paused} tạm dừng`,'wait')]:[]),...(err?[part(`${err} lỗi`,'err')]:[]),
  ...(eta?[part(`còn ~${clock(eta)}`,'eta',`Tính theo thời gian trung bình ${clock(avg)}/video × ${left} video còn lại ÷ ${Math.min(parallel,left)} luồng`)]:[]),...(avg?[part(`TB ${clock(avg)}/video`,'muted')]:[]),
  ...(bal.spend?[part(`OpenAI tháng này $${bal.spend.usd.toFixed(2)}`,'muted','Ước tính của app (OpenAI không cho xem số dư qua API key)')]:[]),...(typeof bal.ai33==='number'?[part(`ai33 còn ◆ ${Math.round(bal.ai33).toLocaleString('vi-VN')}`,'muted')]:[]))}
// errors grouped by cause, with what to do and one button for the whole group
const FIX=[[/credit|số dư/i,'Nạp thêm credit ai33.pro rồi bấm Chạy lại nhóm.'],[/quota|hạn mức|billing/i,'Nạp thêm tiền OpenAI (platform.openai.com → Billing) rồi chạy lại.'],[/key|401|403/i,'Kiểm tra API key ở nút 🔑 trên cùng.'],
 [/kết nối|mạng|thời gian chờ|timeout/i,'Kiểm tra mạng rồi chạy lại.'],[/đã bị xóa khỏi kho|nguồn/i,'Video gốc không còn: xóa tác vụ và thêm lại video.'],[/quá nhiều yêu cầu|429/i,'Giảm số video chạy song song rồi chạy lại.']];
function errorGroups(){const groups=new Map();for(const j of jobs.filter(j=>j.state==='error')){const key=String(j.message||'Lỗi không rõ').split(/(?<=[.!?])\s/)[0].slice(0,160);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(j)}
 const box=$('dq-errors');box.hidden=!groups.size;if(!groups.size)return;
 box.replaceChildren(...[...groups].sort((a,b)=>b[1].length-a[1].length).slice(0,4).map(([msg,list])=>{const fix=FIX.find(([r])=>r.test(msg))?.[1]||'Xem chi tiết từng video rồi chạy lại.';
  const run=el('button',{type:'button',className:'outline-action small-action',textContent:`↻ Chạy lại nhóm (${list.length})`});run.onclick=()=>batch('retry',list.map(j=>j.id));
  const pick=el('button',{type:'button',className:'chip-button',textContent:'Chọn nhóm'});pick.onclick=()=>{for(const j of list)selected.add(j.id);refresh()};
  return el('div',{className:'dq-error'},el('strong',{textContent:`⚠ ${list.length} video: `}),el('span',{textContent:msg}),el('small',{className:'helper',textContent:' → '+fix}),el('span',{className:'dq-error-actions'},pick,run))}))}
function visible(){const q=search.trim().toLowerCase();return jobs.filter(GROUP[filter][1]).filter(j=>!q||String(shown(j)+' '+j.name).toLowerCase().includes(q)).filter(j=>!stepFilter||(j.state!=='done'&&j.step===stepFilter))}
function selectBar(){for(const id of [...selected])if(!jobMap.has(id))selected.delete(id);const list=visible(),n=selected.size,sel=jobs.filter(j=>selected.has(j.id)),has=st=>sel.some(j=>st.includes(j.state));
 $('dq-count').textContent=n?`Đã chọn ${n}`:'Chọn nhiều';$('dq-all').checked=!!list.length&&list.every(j=>selected.has(j.id));$('dq-all').indeterminate=n>0&&!$('dq-all').checked;$('dq-sel-actions').hidden=!n;
 const btn=a=>$('dq-sel-actions').querySelector(`[data-a="${a}"]`);btn('run').disabled=!has(['error','paused']);btn('cancel').disabled=!has(['queued','running']);btn('top').disabled=btn('bottom').disabled=!has(['queued']);btn('edit').disabled=!has(['done','error','paused']);btn('delete').disabled=!has(['error','paused','review','done'])}
function filters(){reviewBar();overview();errorGroups();
 $('dub-filters').replaceChildren(...Object.entries(GROUP).map(([k,[t,f]])=>{const n=jobs.filter(f).length,b=el('button',{type:'button',className:'chip-button',textContent:`${t} ${n}`});b.setAttribute('aria-pressed',String(filter===k));b.onclick=()=>{filter=k;page=1;refresh()};return b}));
 const any=st=>jobs.some(j=>st.includes(j.state));
 $('dub-retry').disabled=!any(['error']);$('dub-stop-all').disabled=!any(['queued','running']);$('dub-clean').disabled=!any(['done']);$('dub-clean-err').disabled=!any(['error']);$('dub-clean-all').disabled=!any(['error','paused','review','done']);
 $('dub-retry').textContent=`↻ Chạy lại lỗi${any(['error'])?' ('+jobs.filter(j=>j.state==='error').length+')':''}`;selectBar()}
// one request for many jobs (server: Store.batch)
async function batch(action,ids,extra={}){if(!ids.length){say('Không có tác vụ phù hợp.');return}
 try{const r=await json('/dub/batch',{action,ids,...keys(),...extra});const names={retry:'chạy lại',resume:'chạy tiếp',cancel:'dừng',delete:'xóa',top:'đưa lên đầu',bottom:'đưa xuống cuối',reexport:'xuất lại'};
  say(`Đã ${names[action]} ${r.done} tác vụ`+(r.skipped?` · bỏ qua ${r.skipped} (không đúng trạng thái)`:'')+(r.errors.length?` · ${r.errors.reduce((a,e)=>a+e.ids.length,0)} lỗi: ${r.errors[0].error}`:'')+'.');
  noAiTexts=r.no_ai_texts||[];if(noAiTexts.length)say(`${noAiTexts.length} video chọn “AI viết” nhưng chưa có chữ AI nên đang dùng tên file. Bấm “✍ Viết chữ AI” ở thanh Đang sửa (mỗi video 1 lần gọi OpenAI), hoặc chọn nguồn chữ Cố định / Tên file.`);if(editing)editBar();
  if(action==='delete'&&ids.includes(current)){current='';detail=null}if(action==='delete')for(const id of ids)selected.delete(id)}catch(e){say(e.message)}refresh()}
// pages: 10 / 20 / 50 / 100 rows per page (remembered), ‹ 1 … 4 5 6 … 12 › under the list; the list scrolls inside
// the panel so a long queue never runs past the window. A new filter, search or step starts again at page 1.
let page=1,pageSize=20;try{pageSize=[10,20,50,100].includes(+localStorage.getItem('dq-size'))?+localStorage.getItem('dq-size'):20}catch{}
function goPage(n){page=n;refresh();$('dq-scroll').scrollTop=0}
// the panel ends at the window's bottom edge wherever it starts (under the page title, or stuck at the top)
function fitQueue(){const box=document.querySelector('.dub-jobs');if(!box||view.hidden)return;if(innerWidth<=900){box.style.maxHeight='';return}
 const room=innerHeight-Math.max(10,box.getBoundingClientRect().top)-10;box.style.maxHeight=(room<innerHeight*.55?innerHeight-20:room)+'px'}   // low on the page: full height once scrolled to
addEventListener('scroll',fitQueue,{passive:true});addEventListener('resize',fitQueue);
function pager(total){const box=$('dq-pager'),pages=Math.max(1,Math.ceil(total/pageSize));box.hidden=!total;if(!total)return;
 const btn=(t,n,title,on)=>{const b=el('button',{type:'button',className:'dq-page'+(on?' on':''),textContent:t,title:title||'Trang '+n,disabled:n<1||n>pages||on});b.onclick=()=>goPage(n);return b};
 const nums=[];const add=n=>{if(!nums.includes(n)&&n>=1&&n<=pages)nums.push(n)};add(1);for(let n=page-1;n<=page+1;n++)add(n);add(pages);nums.sort((a,b)=>a-b);
 const list=[];nums.forEach((n,i)=>{if(i&&n-nums[i-1]>1)list.push(el('span',{className:'dq-gap',textContent:'…'}));list.push(btn(String(n),n,'',n===page))});
 const size=el('select',{className:'dq-size',title:'Số video mỗi trang'},...[10,20,50,100].map(v=>new Option(v+' / trang',v,false,v===pageSize)));
 size.onchange=()=>{const first=(page-1)*pageSize;pageSize=+size.value;try{localStorage.setItem('dq-size',pageSize)}catch{}goPage(Math.floor(first/pageSize)+1)};
 const from=(page-1)*pageSize+1,to=Math.min(total,page*pageSize);
 box.replaceChildren(el('div',{className:'dq-pages'},btn('‹',page-1,'Trang trước'),...list,btn('›',page+1,'Trang sau')),el('div',{className:'dq-pageinfo'},el('span',{textContent:`${from}–${to} / ${total}`}),size))}
// the server sends only what changed since the last answer (+ running jobs); the full order comes as ids
const jobMap=new Map();let jobStamp=0;
async function refresh(){clearTimeout(poll);try{const d=await request('/dub/jobs?since='+jobStamp);if(d.full)jobMap.clear();if(!d.full&&d.jobs.some(j=>j.state==='done'&&jobMap.get(j.id)?.state!=='done'))loadBalance();for(const j of d.jobs)jobMap.set(j.id,j);
  const keep=new Set(d.ids);for(const id of [...jobMap.keys()])if(!keep.has(id))jobMap.delete(id);jobStamp=d.ids.every(id=>jobMap.has(id))?d.stamp||0:0;jobs=d.ids.map(id=>jobMap.get(id)).filter(Boolean);waiting=d.waiting||[];parallel=d.parallel||1;filters();batchDone();trialBar();if(editing&&noAiTexts.length)editBar();const shown=visible();
  page=Math.min(Math.max(1,page),Math.max(1,Math.ceil(shown.length/pageSize)));pager(shown.length);fitQueue();$('dub-queue').replaceChildren(...(shown.length?shown.slice((page-1)*pageSize,page*pageSize).map(card):[el('div',{className:'note-empty'},el('div',{textContent:'🎙'}),el('strong',{textContent:jobs.length?'Không có tác vụ phù hợp':'Chưa có video nào'}),el('p',{className:'helper',textContent:jobs.length?'Đổi nhóm, bước hoặc từ khóa tìm ở trên.':'Chọn video ở mục 🎬 rồi bấm Bắt đầu lồng tiếng.'}))]));
  if(current&&openDetail===current)await showDetail();else $('dub-detail').hidden=true}catch(e){say(e.message)}
 if(jobs.some(j=>['queued','running'].includes(j.state))&&!view.hidden)poll=setTimeout(refresh,1500)}
$('dub-review-open').onclick=()=>openReview();
$('dub-retry').onclick=()=>batch('retry',jobs.filter(j=>j.state==='error').map(j=>j.id));
$('dub-stop-all').onclick=()=>batch('cancel',jobs.filter(GROUP.active[1]).map(j=>j.id));
function cleanJobs(list,label){if(!list.length){say('Không có tác vụ nào để xóa.');return}if(!confirm(`Xóa ${list.length} tác vụ ${label} khỏi hàng đợi? Video đã lưu ra thư mục xuất vẫn giữ.`))return;batch('delete',list.map(j=>j.id))}
$('dub-clean-err').onclick=()=>cleanJobs(jobs.filter(j=>j.state==='error'),'lỗi');
$('dub-clean-all').onclick=()=>cleanJobs(jobs.filter(j=>!['queued','running'].includes(j.state)),'(trừ đang chạy)');
$('dub-clean').onclick=()=>cleanJobs(jobs.filter(GROUP.done[1]),'đã xong');
for(const b of document.querySelectorAll('.dq-menu-list button'))b.addEventListener('click',()=>b.closest('details').open=false);
$('dq-search').oninput=()=>{search=$('dq-search').value;page=1;refresh()};$('dq-step').onchange=()=>{stepFilter=$('dq-step').value;page=1;refresh()};
$('dq-all').onchange=()=>{const list=visible();if($('dq-all').checked)list.forEach(j=>selected.add(j.id));else selected.clear();refresh()};
$('dq-sel-actions').onclick=e=>{const a=e.target.closest('button')?.dataset.a;if(!a)return;const ids=[...selected],sel=jobs.filter(j=>selected.has(j.id));
 if(a==='clear'){selected.clear();refresh();return}
 if(a==='run'){batch('retry',sel.filter(j=>j.state==='error').map(j=>j.id)).then(()=>batch('resume',sel.filter(j=>j.state==='paused').map(j=>j.id)));return}
 if(a==='delete'){cleanJobs(sel.filter(j=>!['queued','running'].includes(j.state)),'đã chọn');return}
 if(a==='edit'){const ok=sel.filter(j=>['done','error','paused'].includes(j.state)&&j.video_id);if(!ok.length){say('Chọn video đã xong, lỗi hoặc tạm dừng để sửa.');return}editJob(ok[0],ok.map(j=>j.id));return}
 batch(a,ids)};
// "Báo khi cả lô xong": a short tone + a system notification when the last running job finishes
try{$('dq-notify').checked=localStorage.getItem('dub-notify')!=='0'}catch{$('dq-notify').checked=true}
$('dq-notify').onchange=()=>{try{localStorage.setItem('dub-notify',$('dq-notify').checked?'1':'0')}catch{}if($('dq-notify').checked&&window.Notification?.permission==='default')Notification.requestPermission().catch(()=>{})};
let wasBusy=false;
function batchDone(){const busy=jobs.some(j=>['queued','running'].includes(j.state));if(wasBusy&&!busy&&$('dq-notify').checked){const done=jobs.filter(j=>j.state==='done').length,err=jobs.filter(j=>j.state==='error').length;
  const text=`Xong lô: ${done} video hoàn tất`+(err?`, ${err} lỗi`:'')+'.';say(text+' Video đã lưu vào thư mục xuất.');
  try{const a=new AudioContext(),o=a.createOscillator(),g=a.createGain();o.frequency.value=880;g.gain.setValueAtTime(.15,a.currentTime);g.gain.exponentialRampToValueAtTime(.001,a.currentTime+.6);o.connect(g).connect(a.destination);o.start();o.stop(a.currentTime+.6)}catch{}
  try{if(window.Notification?.permission==='granted'&&document.hidden)new Notification('Review Studio',{body:text})}catch{}}
 wasBusy=busy}
// disk used by the queue; "Dọn file tạm" frees the temporary part of finished videos (also done by itself after 3 days)
const mb=b=>b>=1073741824?(b/1073741824).toFixed(1)+' GB':Math.round(b/1048576)+' MB';
async function storage(){try{const d=await request('/dub/storage');$('dub-sweep').textContent=`💾 Dọn file tạm · ${mb(d.temp)}`;$('dub-sweep').title=`Hàng đợi chiếm ${mb(d.total)} (${d.jobs} video), trong đó ${mb(d.temp)} là file tạm của video. Dọn file tạm của video đã xong: giữ giọng đọc, bản dịch và video xuất; xuất lại sẽ tự tạo lại.`;$('dub-sweep').disabled=!d.temp}catch{}}
$('dub-sweep').onclick=async()=>{try{const d=await json('/dub/sweep',{days:0});say(`Đã dọn file tạm của ${d.cleaned} video, giải phóng ${mb(d.freed)}. Hàng đợi còn chiếm ${mb(d.total)}.`);storage()}catch(e){say(e.message)}};
document.addEventListener('view-change',e=>{if(e.detail==='dub')storage()});storage();

// ---- translation panel (closed by default; "✎ Bản dịch" on a job opens it)
let dirty=false,openDetail='';
async function showDetail(){const job=await request('/dub/'+current).catch(()=>null);const box=$('dub-detail');if(!job){box.hidden=true;return}
 const editable=!['queued','running'].includes(job.state);if(dirty&&detail?.id===job.id&&editable)return;detail=job;box.hidden=false;
 const video=job.state==='done'?el('video',{className:'dub-player',src:job.outputs.video+'?t='+Date.now(),controls:true,playsInline:true}):el('div',{className:'dub-player empty',textContent:'Video lồng tiếng sẽ hiện ở đây khi xong.'});
 if(job.options.mode==='paragraph')return paragraphDetail(job,box,editable,video);
 const rows=job.segments.map((s,i)=>{const area=el('textarea',{rows:2,value:s.vi||'',disabled:!editable,maxLength:500});const count=el('span',{className:'dub-syl'});const upd=()=>{const n=(area.value.match(/[^\s.,!?;:…"“”()\-–—]+/g)||[]).length,lim=s.limit||Math.max(2,Math.floor((s.end-s.start)*(job.options.rate||4.2)));count.textContent=`${n}/${lim}`;count.classList.toggle('over',n>lim*1.15)};area.oninput=()=>{dirty=true;upd();$('dub-save').disabled=false};upd();area.dataset.i=i;
  const seek=el('button',{type:'button',className:'note-time',textContent:time(s.start),title:'Tua video tới câu này'});seek.onclick=()=>{const v=box.querySelector('video');if(v){v.currentTime=s.start;v.play().catch(()=>{})}};
  return el('div',{className:'dub-row'+(s.edited?' edited':'')},el('div',{className:'dub-row-time'},seek,el('small',{textContent:(s.end-s.start).toFixed(1)+'s'})),el('div',{className:'dub-zh',textContent:s.zh}),el('div',{className:'dub-vi'},area,count))});
 const tools=el('div',{className:'result-actions'});const save=el('button',{type:'button',id:'dub-save',className:'primary-action small-action',textContent:'Lưu câu dịch',disabled:true});save.onclick=async()=>{const lines=[...box.querySelectorAll('.dub-vi textarea')].map(a=>({i:Number(a.dataset.i),vi:a.value}));try{await json(`/dub/${job.id}/lines`,{lines});dirty=false;say('Đã lưu câu dịch. Bấm Tiếp tục để tạo giọng cho các câu đã sửa.');refresh()}catch(e){say(e.message)}};
 if(editable&&job.segments.length)tools.append(save);srtLinks(job,tools);
 box.replaceChildren(detailHead(job,`${job.segments.length} câu · ${time(job.duration)}`),video,el('div',{className:'dub-table-head'},el('span',{textContent:'Thời gian'}),el('span',{textContent:'Lời gốc'}),el('span',{textContent:'Tiếng Việt · số tiếng/giới hạn'})),el('div',{className:'dub-table'},...(rows.length?rows:[el('p',{className:'helper',textContent:'Chưa có câu nào — đang nhận diện…'})])),tools)}
function srtLinks(job,tools){for(const[label,url]of [['SRT lời gốc',`/dub/${job.id}/srt/zh`],['SRT tiếng Việt',`/dub/${job.id}/srt/vi`]])if(job.segments.length)tools.append(el('a',{className:'outline-action small-action',href:url,textContent:label+' ↓'}));
 if(!['queued','running'].includes(job.state)&&job.steps.translate==='done'){const again=el('button',{type:'button',className:'outline-action small-action',textContent:'Dịch lại'});again.onclick=async()=>{if(!confirm('Dịch lại? Bản đang sửa sẽ bị thay.'))return;try{await json(`/dub/${job.id}/continue`,{from:'translate',...keys(),options:settings()});dirty=false;refresh()}catch(e){say(e.message)}};tools.append(again)}}
function detailHead(job,sub){const card=jobs.find(j=>j.id===job.id)||job;return el('div',{className:'dub-detail-head sticky'},el('div',{className:'dub-detail-title'},el('strong',{textContent:shown(job)}),el('span',{className:'badge '+(job.state==='done'?'done':job.state==='error'?'error':'doing'),textContent:pos>=0?`Chờ · #${pos+1}`:job.state==='running'&&STEP_NAME[job.step]?STEP_NAME[job.step]:STATE[job.state]||job.state,title:pos>=0?`Thứ ${pos+1} trong hàng chờ · chọn rồi bấm ⤒ Ưu tiên để chạy trước`:''}),el('small',{textContent:sub})),
 stepDots(card),el('small',{className:'dub-msg',textContent:`${job.progress||0}% · ${job.message||''}`}),actionsFor(card))}
function paragraphDetail(job,box,editable,video){const area=el('textarea',{className:'dub-paragraph',value:job.paragraph||'',disabled:!editable||!job.paragraph,rows:9,maxLength:20000,placeholder:'Đoạn văn tiếng Việt sẽ hiện ở đây sau bước dịch.'});
 const count=el('span',{className:'dub-syl'}),limit=job.paragraph_limit||0;const upd=()=>{const n=(area.value.match(/[^\s.,!?;:…"“”()\-–—]+/g)||[]).length;count.textContent=limit?`${n}/${limit} tiếng`:`${n} tiếng`;count.classList.toggle('over',limit&&n>limit*1.1)};upd();
 const save=el('button',{type:'button',id:'dub-save',className:'primary-action small-action',textContent:'Lưu đoạn văn',disabled:true});area.oninput=()=>{dirty=true;upd();save.disabled=false};
 save.onclick=async()=>{try{await json(`/dub/${job.id}/lines`,{paragraph:area.value});dirty=false;say('Đã lưu đoạn văn. Bấm Tiếp tục để tạo lại một file giọng.');refresh()}catch(e){say(e.message)}};
 const zh=el('div',{className:'dub-zh-list'},...job.segments.map(s=>el('div',{},el('span',{className:'note-time',textContent:time(s.start)}),document.createTextNode(' '+s.zh))));
 const lines=(job.vi_lines||[]).map(l=>{const b=el('button',{type:'button',className:'dub-sub',title:'Tua video tới câu này'},el('span',{className:'note-time',textContent:time(l.start)}),document.createTextNode(' '+l.vi));b.onclick=()=>{const v=box.querySelector('video');if(v){v.currentTime=l.start;v.play().catch(()=>{})}};return b});
 const tools=el('div',{className:'result-actions'});if(editable&&job.paragraph)tools.append(save);srtLinks(job,tools);
 box.replaceChildren(detailHead(job,`${job.segments.length} câu gốc · ${time(job.duration)} · 1 file giọng${job.video_stretch&&job.video_stretch!==1?` · video ×${job.video_stretch}`:job.groups?.[0]?.tempo&&job.groups[0].tempo!==1?` · giọng ×${job.groups[0].tempo}`:''}`),video,el('div',{className:'dub-para'},el('div',{},el('div',{className:'group-label',textContent:'LỜI GỐC'}),zh),el('div',{},el('div',{className:'group-label',textContent:'ĐOẠN VĂN TIẾNG VIỆT · ĐỌC THÀNH 1 FILE'}),area,count,...(lines.length?[el('div',{className:'group-label',textContent:'PHỤ ĐỀ THEO GIỌNG ĐỌC'}),el('div',{className:'dub-subs'},...lines)]:[]))),tools)}

// ---- source video position: 9-point align (edges of the scaled video on the frame edges) and drag on the preview
// size on screen of a w×h box turned by deg (the align buttons put that outline against the frame's edges)
function turnedBox(w,h,deg){const r=deg*Math.PI/180,c=Math.abs(Math.cos(r)),s=Math.abs(Math.sin(r));return[w*c+h*s,w*s+h*c]}
// the video as the export draws it: "Lấp đầy" = a box of frame × zoom (cut to it), "Giữ toàn bộ"/"Nền mờ" = the
// whole picture fitted in that box; then the rotation
function videoBox(o){const[W,H]=lastWH,vw=fg.videoWidth||W,vh=fg.videoHeight||H,z=o.frame_zoom/100,e=o.edge_trim||0;
 const fit=o.frame_fit!=='cover'&&window.nearFit?.(vw-2*e,vh-2*e,W,H)?'cover':o.frame_fit;let bw=W*z,bh=H*z;
 if(fit!=='cover'){const k=Math.min(W/vw,H/vh)*z;bw=vw*k;bh=vh*k}[bw,bh]=turnedBox(bw,bh,o.frame_rotate);return[bw,bh,W,H]}
$('dub-frame-align').onclick=e=>{const b=e.target.closest('button');if(!b)return;const o=settings(),[bw,bh,W,H]=videoBox(o),a=b.dataset.a;
 if(a!=='cc'&&Math.abs(bw-W)<1&&Math.abs(bh-H)<1)say('Video đang vừa khít khung xuất nên căn mép không đổi gì: giảm/tăng Tỷ lệ hoặc chọn "Giữ toàn bộ" rồi căn.');
 setNum('dub-x',a[0]==='l'?(bw-W)/W*100:a[0]==='r'?(W-bw)/W*100:0);setNum('dub-y',a[1]==='t'?(bh-H)/H*100:a[1]==='b'?(H-bh)/H*100:0);imgChanged()};
$('dub-frame').addEventListener('pointerdown',e=>{if(!cur()||e.target.closest('#dub-imgbox,#dub-ovbox')||e.button)return;e.preventDefault();const frame=$('dub-frame'),box=frame.getBoundingClientRect(),start=settings(),x0=e.clientX,y0=e.clientY;frame.setPointerCapture(e.pointerId);frame.classList.add('moving');
 const move=ev=>{let nx=start.frame_x+(ev.clientX-x0)/box.width*200,ny=start.frame_y+(ev.clientY-y0)/box.height*200;if(Math.abs(nx)<2)nx=0;if(Math.abs(ny)<2)ny=0;setNum('dub-x',nx);setNum('dub-y',ny);syncNumbers();labels();preview()};
 const up=()=>{frame.removeEventListener('pointermove',move);frame.removeEventListener('pointerup',up);frame.classList.remove('moving');remember()};frame.addEventListener('pointermove',move);frame.addEventListener('pointerup',up)});
// ---- image layer: library, size/fit/align tools, drag & resize on the preview
let images=[],lastWH=[1080,1920];
const imgMeta=()=>images.find(x=>x.id===$('dub-img-pick').value);
const BLEND_CSS={normal:'normal',darken:'darken',multiply:'multiply',burn:'color-burn',lighten:'lighten',screen:'screen',dodge:'color-dodge',addition:'plus-lighter',overlay:'overlay',softlight:'soft-light',hardlight:'hard-light',difference:'difference',exclusion:'exclusion'};
function imgRatioH(w){const m=imgMeta(),[W,H]=lastWH;return m?w*W*m.height/(m.width*H):w}  // height % of the frame that keeps the picture's ratio
function imgRatioW(h){const m=imgMeta(),[W,H]=lastWH;return m?h*H*m.width/(m.height*W):h}
function setNum(id,v){const e=$(id),c=Math.min(+e.max,Math.max(+e.min,v));if(PX[id]){const k=pxPer(id);e.value=String(Math.round(c*k)/k);return}e.value=String(Math.round(c*10)/10)}
function imgChanged(){syncNumbers();remember();preview()}
function keepSync(from){if(!$('dub-img-keep').checked)return;if(from==='h')setNum('dub-img-w',imgRatioW(+$('dub-img-h').value));else setNum('dub-img-h',imgRatioH(+$('dub-img-w').value))}
$('dub-img-w').addEventListener('input',()=>keepSync('w'));$('dub-img-h').addEventListener('input',()=>keepSync('h'));$('dub-img-keep').addEventListener('change',()=>keepSync('w'));
function drawImage(o,box,W,H){lastWH=[W,H];const m=o.image?imgMeta():null,wrap=$('dub-imgbox'),img=$('dub-imgl');wrap.hidden=!m||!cur();if(!m)return;
 const src=`/dub/images/${m.id}/file`;if(img.dataset.src!==src){img.src=src;img.dataset.src=src}
 const h=o.image_keep||!o.image_h?imgRatioH(o.image_w):o.image_h,fx=o.image_flip.includes('h')?-1:1,fy=o.image_flip.includes('v')?-1:1;
 Object.assign(wrap.style,{width:o.image_w+'%',height:h+'%',left:(50+o.image_x)+'%',top:(50+o.image_y)+'%',transform:`translate(-50%,-50%) rotate(${o.image_rotate}deg)`,opacity:o.image_opacity/100,mixBlendMode:BLEND_CSS[o.image_blend]||'normal'});layerZ(o);
 img.style.transform=`scale(${fx},${fy})`}
// ---- Thứ tự lớp (bottom → top in layer_order, same rule as dubbing.layer_stack): shown top → bottom like CapCut,
// ‹ › move a layer up/down; the preview restacks at once. Frame and texts always stay on top.
const LAYERS=['video','background','overlay','image'],LAYER_NAME={video:'🎬 Video',background:'🎨 Nền',overlay:'✨ Video overlay',image:'🖼 Lớp ảnh'};
const designOn=()=>!!window.dubProfile?.on?.();
function layerStack(o,design=designOn()){let order=String(o.layer_order||'').split(',').filter(k=>LAYERS.includes(k));
 if(order.length!==4||new Set(order).size!==4)order=['video','background',...(o.image_layer==='above'?['overlay','image']:['image','overlay'])];
 return design?order:['video',...order.filter(k=>k==='overlay'||k==='image')]}
function setLayers(order){const full=designOn()?order:[...layerStack(settings(),true).filter(k=>!order.includes(k)||k==='video'||k==='background').filter(k=>k!=='overlay'&&k!=='image'),...order.filter(k=>k!=='video')];
 $('dub-layer-order').value=full.join(',');$('dub-img-layer').value=full.indexOf('image')>full.indexOf('overlay')?'above':'below';
 for(const id of ['dub-layer-order','dub-img-layer'])$(id).dispatchEvent(new Event('change',{bubbles:true}));drawLayers();preview();window.appHistory?.checkpoint?.()}
function drawLayers(){const o=settings(),order=layerStack(o),top=[...order].reverse(),box=$('dub-layers');if(!box)return;
 const used={video:true,background:designOn()&&$('dt-design-on')?.checked,overlay:o.overlay,image:o.image};
 const chip=(k,i)=>{const fixed=!designOn()&&k==='video',c=el('span',{className:'dub-layer'+(used[k]?'':' off')+(fixed?' fixed':''),title:fixed?'Không dùng mẫu thiết kế: video phủ cả khung nên luôn ở dưới cùng':used[k]?'':'Lớp này đang tắt'});
  const move=(d,t,label)=>{const b=el('button',{type:'button',className:'dub-layer-move',textContent:t,title:label,disabled:fixed||i+d<0||i+d>=top.length||(!designOn()&&top[i+d]==='video')});b.onclick=()=>{const n=[...top];[n[i],n[i+d]]=[n[i+d],n[i]];setLayers(n.reverse())};return b};
  c.append(move(-1,'‹','Đưa lên trên'),el('span',{textContent:LAYER_NAME[k]}),move(1,'›','Đưa xuống dưới'));return c};
 box.replaceChildren(el('small',{className:'dub-layers-label',textContent:'Thứ tự lớp (trên cùng → dưới cùng):'}),el('span',{className:'dub-layer fixed',textContent:'🔒 Khung & chữ',title:'Khung trang trí, tiêu đề, nội dung luôn nằm trên cùng'}),...top.map(chip),
  (()=>{const b=el('button',{type:'button',className:'chip-button dub-layer-reset',textContent:'↺',title:'Thứ tự mặc định: Lớp ảnh dưới overlay, Nền trên video'});b.onclick=()=>setLayers(['video','background','image','overlay']);return b})())}
// z-index of the preview layers: the plain frame (video / overlay / image) and the design stage (all four)
function layerZ(o=settings()){const design=designOn(),order=layerStack(o,design),z=k=>1+order.indexOf(k);
 const set=(e,v)=>{if(e)e.style.zIndex=String(v)};
 set($('dub-preview-video'),1);for(const id of ['dub-ovv','dub-ovi'])set($(id),z('overlay'));set($('dub-imgbox'),z('image'));
 if(design){set($('video-transform'),z('video'));set($('overlay'),z('background'));for(const id of ['dt-ovv','dt-ovi'])set($(id),z('overlay'))}}
window.dubLayers={draw:drawLayers,z:layerZ};window.dubPlayerTools=playerTools;
// ---- "Phụ đề chữ chạy": style chips, sample on the preview (word lights up in turn, drag to move it up/down)
const CAP_SAMPLE='Chào cả nhà hôm nay mình giới thiệu món đồ rất hay';
// quick looks: style + font + colours (+ size, capitals) in one click
const CAP_PRESETS=[['TikTok vàng','classic','bvp-black','#ffffff','#ffe14d',68,false],['Hộp đen','box','montserrat','#ffffff','#ffd23f',62,false],['Pop xanh','pop','baloo','#ffffff','#3ef0b0',70,false],
 ['Neon hồng','neon','lexend','#ffffff','#ff4fd8',64,false],['Karaoke','karaoke','nunito','#ffffff','#ffd23f',66,false],['Marker đỏ','marker','oswald','#ffffff','#ff3b5c',72,true],
 ['Bóng đổ','shadow','anton','#ffffff','#ffe14d',74,true],['Hiện dần','reveal','fira','#ffffff','#7cc4ff',64,false],['Từng chữ','single','bungee','#ffffff','#ffe14d',90,true],
 ['Viết tay','classic','sriracha','#ffffff','#ffb86b',72,false],['Truyện tranh','pop','bangers','#ffffff','#ff5b5b',80,true],['Dễ thương','karaoke','mali','#fff6fb','#ff8ac4',66,false]];
function capPresets(){const box=$('dub-cap-presets');if(!box||box.childElementCount)return;
 box.replaceChildren(...CAP_PRESETS.map(([name,style,font,color,hi,size,upper])=>{const fam=FONT_FAMILY(font),b=el('button',{type:'button',className:'dub-cap-preset cap-'+style,title:`${name} · ${font}`});
  b.append(el('span',{textContent:upper?'ABC ':'Abc '}),el('span',{className:'lit',textContent:upper?'XYZ':'xyz'}));Object.assign(b.style,{fontFamily:fam,color});b.style.setProperty('--hi',hi);b.style.setProperty('--cap-out','2px');
  b.append(el('small',{textContent:name}));b.onclick=()=>{$('dub-cap-style').value=style;$('dub-cap-font').value=font;$('dub-cap-color').value=color;$('dub-cap-hi').value=hi;setNum('dub-cap-size',size);$('dub-cap-upper').checked=upper;
   if(!$('dub-cap').checked){$('dub-cap').checked=true;$('dub-cap').dispatchEvent(new Event('change',{bubbles:true}))}capStyleButtons();remember();labels();preview();window.appHistory?.checkpoint?.()};return b}))}
const FONT_FAMILY=key=>(window.FONT_LIST||[]).find(f=>f[0]===key)?.[1]||'';
function capStyleButtons(){for(const b of $('dub-cap-styles').querySelectorAll('button'))b.setAttribute('aria-pressed',String(b.dataset.v===$('dub-cap-style').value))}
$('dub-cap-styles').onclick=e=>{const b=e.target.closest('button');if(!b)return;$('dub-cap-style').value=b.dataset.v;capStyleButtons();remember();labels();preview()};
function capFonts(){const src=$('title_font'),pick=$('dub-cap-font'),cur=pick.value||'bvp-black';if(!src||pick.options.length)return;pick.replaceChildren(...[...src.options].map(o=>{const n=new Option(o.textContent,o.value);n.style.fontFamily=o.style.fontFamily;return n}));pick.value=[...pick.options].some(o=>o.value===cur)?cur:'bvp-black'}
let capTick=0,capWord=0,capHost=null,capW=1080,capSrc={id:'',words:[]};
function drawCaption(o,host,W){const box=$('dub-capbox');capHost=host;capW=W;if(!o.captions||!cur()){box.hidden=true;return}
 if(box.parentNode!==host)host.append(box);box.hidden=false;const k=W/1080,n=o.caption_style==='single'?1:o.caption_words;
 // the video being edited (✎ Sửa) shows its own Vietnamese text, read in chunks like the export; otherwise the sample
 const jid=editing?(editing.items[editing.at]||{}).id:'';if(jid&&capSrc.id!==jid){capSrc={id:jid,words:[]};request('/dub/'+jid).then(j=>{if(capSrc.id!==jid)return;const t=j.paragraph||(j.segments||[]).map(x=>x.vi||'').join(' ');capSrc.words=t.split(/\s+/).filter(Boolean)}).catch(()=>{})}
 const all=(jid&&capSrc.words.length?capSrc.words:CAP_SAMPLE.split(' ')).map(w=>o.caption_upper?w.toUpperCase():w),per=Math.max(1,o.caption_style==='single'?1:o.caption_words),at0=Math.floor((capWord%all.length)/per)*per,words=all.slice(at0,at0+per),i=(capWord%all.length)-at0;
 box.className='dub-capbox cap-'+o.caption_style;const fam=FONT_FAMILY(o.caption_font);
 Object.assign(box.style,{top:o.caption_y+'%',fontSize:Math.max(8,o.caption_size*k)+'px',fontFamily:fam,color:o.caption_color});box.style.setProperty('--hi',o.caption_hi);box.style.setProperty('--cap-out',Math.max(1,4*k)+'px');
 const st=o.caption_style,show=words,at=Math.min(i,words.length-1);
 box.replaceChildren(...show.flatMap((w,j)=>[el('span',{className:(j===at||(st==='karaoke'&&j<at)?'lit':'')+(st==='reveal'&&j>at?' hide':''),textContent:w}),' ']));
 if(!capTick)capTick=setInterval(()=>{if(view.hidden||$('dub-capbox').hidden||!capHost)return;capWord++;drawCaption(settings(),capHost,capW)},420)}
function capLabels(o){const st={classic:'viền đen',box:'nền hộp',pop:'phóng to từ',neon:'phát sáng',karaoke:'karaoke',marker:'nền màu từ',shadow:'bóng đổ',reveal:'hiện dần',single:'từng chữ'}[o.caption_style];$('sum-captions').textContent=o.captions?`${st} · ${o.caption_words} chữ/lần · cỡ ${o.caption_size}`:'tắt';
 $('sum-music').textContent=o.music?(music.length?`${musUse.size||music.length} bài · ${o.music_volume}%${o.music_duck?' · tự giảm khi có giọng':''}`:'bật · chưa có nhạc'):'tắt';for(const[id,v]of [['dub-cap-words-value',o.caption_words],['dub-cap-size-value',o.caption_size],['dub-cap-y-value',o.caption_y+'%'],['dub-music-vol-value',o.music_volume+'%']])if($(id))$(id).textContent=v}
// drag the sample up/down = "Vị trí dọc"
$('dub-capbox').addEventListener('pointerdown',e=>{const box=$('dub-capbox'),host=box.parentNode,r=host.getBoundingClientRect();e.preventDefault();e.stopPropagation();box.setPointerCapture(e.pointerId);
 const move=ev=>{setNum('dub-cap-y',Math.round(Math.max(5,Math.min(95,(ev.clientY-r.top)/r.height*100))));labels();preview()};
 const up=()=>{box.removeEventListener('pointermove',move);box.removeEventListener('pointerup',up);remember();window.appHistory?.checkpoint?.()};box.addEventListener('pointermove',move);box.addEventListener('pointerup',up)});
window.dubCaption=(host,W)=>drawCaption(settings(),host,W);
// ---- "Nhạc nền": library with văn phong tags, "Dùng" ticks (none ticked = every track), listen
function drawMusic(){const list=$('dub-music-list');if(!list)return;const styles=[...$('dub-style').options].map(o=>[o.value,o.textContent]);
 $('dub-music-note').textContent=music.length?`${music.length} bài · ${musUse.size?'dùng '+musUse.size+' bài đã tick':'dùng tất cả'}`:'Chưa có nhạc · thêm MP3/WAV của bạn';
 list.replaceChildren(...music.map(m=>{const use=el('input',{type:'checkbox',checked:musUse.has(m.id),title:'Chỉ dùng những bài được tick (không tick bài nào = dùng tất cả)'});use.onchange=()=>{use.checked?musUse.add(m.id):musUse.delete(m.id);remember();drawMusic();labels()};
  const play=el('button',{type:'button',className:'icon-button',textContent:'▶',title:'Nghe thử'});play.onclick=()=>{const a=$('dub-music-audio')||document.body.appendChild(el('audio',{id:'dub-music-audio'}));if(a.dataset.id===m.id&&!a.paused){a.pause();return}a.src=`/dub/music/${m.id}/file`;a.dataset.id=m.id;a.volume=.6;a.play().catch(()=>{})};
  const del=el('button',{type:'button',className:'icon-button danger-action',textContent:'✕',title:'Xóa khỏi kho nhạc'});del.onclick=async()=>{if(!confirm(`Xóa "${m.name}" khỏi kho nhạc?`))return;try{music=(await json(`/dub/music/${m.id}/delete`)).music;musUse.delete(m.id);remember();drawMusic();labels()}catch(e){say(e.message)}};
  const chip=el('button',{type:'button',className:'chip-button dub-music-chip',textContent:(m.styles||[]).length?(m.styles||[]).map(v=>styles.find(x=>x[0]===v)?.[1]||v).join(', '):'Mọi văn phong',title:'Bấm để gắn văn phong'});
  chip.onclick=()=>{const pick=prompt('Gắn văn phong cho bài này (gõ số, cách nhau bằng dấu phẩy; để trống = mọi văn phong):\n'+styles.map(([v,t],i)=>`${i+1}. ${t}`).join('\n'),(m.styles||[]).map(v=>styles.findIndex(x=>x[0]===v)+1).join(', '));if(pick===null)return;
   const chosen=[...new Set(pick.split(/[,\s]+/).map(Number).filter(n=>n>=1&&n<=styles.length).map(n=>styles[n-1][0]))];json(`/dub/music/${m.id}/styles`,{styles:chosen}).then(r=>{music=r.music;drawMusic()}).catch(e=>say(e.message))};
  return el('div',{className:'dub-music-row'},use,play,el('span',{className:'dub-music-name',textContent:m.name,title:m.name}),el('small',{textContent:time(m.duration)}),chip,del)}))}
async function loadMusic(){try{music=(await request('/dub/music')).music}catch{music=[]}drawMusic()}
$('dub-music-file').onchange=async()=>{const list=[...$('dub-music-file').files];$('dub-music-file').value='';let ok=0;for(const f of list){try{say(`Đang thêm nhạc ${f.name}…`);await request('/dub/music/upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(f.name)},body:f});ok++}catch(e){say(`${f.name}: ${e.message}`)}}
 await loadMusic();if(ok&&!$('dub-music').checked){$('dub-music').checked=true;$('dub-music').dispatchEvent(new Event('change',{bubbles:true}))}remember();labels();if(ok)say(`Đã thêm ${ok} bài nhạc. Bấm vào ô văn phong của từng bài để gắn văn phong hợp với nó.`)};
loadMusic();setTimeout(()=>{capFonts();capPresets();capStyleButtons()},300);
async function loadImages(keep){try{images=(await request('/dub/images')).images}catch{images=[]}const pick=$('dub-img-pick'),cur=keep??pick.value;
 pick.replaceChildren(new Option(images.length?'— Chọn ảnh —':'Chưa có ảnh · bấm Thêm ảnh',''),...images.map(m=>new Option(`${m.name} · ${m.width}×${m.height}`,m.id)));pick.value=images.some(m=>m.id===cur)?cur:'';labels();preview()}
$('dub-img-file').onchange=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;say('Đang thêm ảnh '+f.name+'…');
 try{const item=await request('/dub/images/upload',{method:'POST',headers:{'X-Filename':encodeURIComponent(f.name)},body:f});await loadImages(item.id);$('dub-img').checked=true;$('dub-img').dispatchEvent(new Event('change',{bubbles:true}));keepSync('w');imgChanged();say(`Đã thêm ảnh ${item.name}. Kéo ảnh trên khung xem trước để đặt vị trí, kéo góc dưới phải để đổi cỡ.`)}catch(err){say(err.message)}};
$('dub-img-del').onclick=async()=>{const m=imgMeta();if(!m){say('Chưa chọn ảnh nào để xóa.');return}if(!confirm(`Xóa ảnh "${m.name}" khỏi thư viện?`))return;try{await request(`/dub/images/${m.id}/delete`,{method:'POST'});await loadImages('');imgChanged()}catch(e){say(e.message)}};
const needImage=()=>{if(imgMeta())return true;say('Chọn ảnh ở ô “Ảnh” (hoặc bấm ⬆ Thêm ảnh) trước rồi mới chỉnh được lớp ảnh.');$('sec-image').open=true;return false};
$('dub-img-fit').onclick=e=>{const b=e.target.closest('button');if(!b||!needImage())return;const m=imgMeta();const[W,H]=lastWH,fit=b.dataset.fit;
 if(fit==='stretch'){$('dub-img-keep').checked=false;setNum('dub-img-w',100);setNum('dub-img-h',100)}
 else{$('dub-img-keep').checked=true;const k=fit==='native'?1:fit==='contain'?Math.min(W/m.width,H/m.height):Math.max(W/m.width,H/m.height);setNum('dub-img-w',m.width*k/W*100);setNum('dub-img-h',m.height*k/H*100)}
 if(fit!=='native'){setNum('dub-img-x',0);setNum('dub-img-y',0)}imgChanged()};
$('dub-img-align').onclick=e=>{const b=e.target.closest('button');if(!b||!needImage())return;const o=settings(),[W,H]=lastWH,[tw,th]=turnedBox(o.image_w*W/100,(o.image_keep?imgRatioH(o.image_w):o.image_h)*H/100,o.image_rotate),w=tw/W*100,h=th/H*100,a=b.dataset.a;
 setNum('dub-img-x',a[0]==='l'?w/2-50:a[0]==='r'?50-w/2:0);setNum('dub-img-y',a[1]==='t'?h/2-50:a[1]==='b'?50-h/2:0);imgChanged()};
// on each button: the CapCut panel moves them out of #dub-img-turn
for(const b of $('dub-img-turn').querySelectorAll('button'))b.onclick=()=>{if(!needImage())return;const d=+b.dataset.r,v=d?((+$('dub-img-rot').value+d+540)%360)-180:0;setNum('dub-img-rot',v);imgChanged()};
$('dub-img-reset').onclick=()=>{if($('dub-layer-order').value)setLayers(['video','background','image','overlay']);$('dub-img-keep').checked=true;setNum('dub-img-w',60);keepSync('w');for(const id of ['dub-img-x','dub-img-y','dub-img-rot'])setNum(id,0);setNum('dub-img-op',100);$('dub-img-flip').value='none';$('dub-img-blend').value='normal';$('dub-img-layer').value='below';imgChanged()};
// drag to move, corner handle to resize (in % of the frame, like the export)
$('dub-imgbox').addEventListener('pointerdown',e=>{e.preventDefault();e.stopPropagation();window.openDubSection?.('sec-image');const box=e.currentTarget.parentElement.getBoundingClientRect(),start=settings(),resize=e.target.classList.contains('dub-img-handle'),x0=e.clientX,y0=e.clientY,el_=e.currentTarget;el_.setPointerCapture(e.pointerId);el_.classList.add('dragging');
 const move=ev=>{const dx=(ev.clientX-x0)/box.width*100,dy=(ev.clientY-y0)/box.height*100;
  if(resize){setNum('dub-img-w',start.image_w+dx*2);if($('dub-img-keep').checked)keepSync('w');else setNum('dub-img-h',(start.image_h||imgRatioH(start.image_w))+dy*2)}
  else{let nx=start.image_x+dx,ny=start.image_y+dy;if(Math.abs(nx)<1.2)nx=0;if(Math.abs(ny)<1.2)ny=0;setNum('dub-img-x',nx);setNum('dub-img-y',ny)}
  syncNumbers();labels();preview()};
 const up=()=>{el_.removeEventListener('pointermove',move);el_.removeEventListener('pointerup',up);el_.classList.remove('dragging');remember()};el_.addEventListener('pointermove',move);el_.addEventListener('pointerup',up)});
// ---- Căn chỉnh overlay: fit, align, turn, reset, drag & resize on the preview
function ovChanged(){syncNumbers();labels();remember();preview()}
$('dub-ov-fitbtns').onclick=e=>{const b=e.target.closest('button');if(!b)return;$('dub-ov-fit').value=b.dataset.f;ovChanged()};
$('dub-ov-align').onclick=e=>{const b=e.target.closest('button');if(!b)return;const o=settings(),[W,H]=outWH(),[tw,th]=turnedBox(W*o.overlay_scale/100,H*o.overlay_scale/100,o.overlay_rotate),w=tw/W*100,h=th/H*100,a=b.dataset.a;
 setNum('dub-ov-x',a[0]==='l'?w/2-50:a[0]==='r'?50-w/2:0);setNum('dub-ov-y',a[1]==='t'?h/2-50:a[1]==='b'?50-h/2:0);ovChanged()};
for(const b of $('dub-ov-turn').querySelectorAll('button[data-r]'))b.onclick=()=>{const d=+b.dataset.r,v=d?((+$('dub-ov-rot').value+d+540)%360)-180:0;setNum('dub-ov-rot',v);ovChanged()};
$('dub-ov-reset').onclick=()=>{setNum('dub-ov-scale',100);for(const id of ['dub-ov-x','dub-ov-y','dub-ov-rot'])setNum(id,0);$('dub-ov-flip').value='none';$('dub-ov-fit').value='cover';ovChanged()};
$('sec-overlay').addEventListener('toggle',()=>preview());
$('dub-ovbox').addEventListener('pointerdown',e=>{e.preventDefault();e.stopPropagation();const box=e.currentTarget.parentElement.getBoundingClientRect(),start=settings(),resize=e.target.classList.contains('dub-img-handle'),x0=e.clientX,y0=e.clientY,el_=e.currentTarget;el_.setPointerCapture(e.pointerId);el_.classList.add('dragging');
 const move=ev=>{const dx=(ev.clientX-x0)/box.width*100,dy=(ev.clientY-y0)/box.height*100;
  if(resize)setNum('dub-ov-scale',start.overlay_scale+Math.max(dx,dy)*2);
  else{let nx=start.overlay_x+dx,ny=start.overlay_y+dy;if(Math.abs(nx)<1.2)nx=0;if(Math.abs(ny)<1.2)ny=0;setNum('dub-ov-x',nx);setNum('dub-ov-y',ny)}
  syncNumbers();labels();preview()};
 const up=()=>{el_.removeEventListener('pointermove',move);el_.removeEventListener('pointerup',up);el_.classList.remove('dragging');remember()};el_.addEventListener('pointermove',move);el_.addEventListener('pointerup',up)});
// preview tools: safe zone and mute (per viewer, remembered in this browser)
try{$('dub-safe').checked=localStorage.getItem('dub-safe')==='1'}catch{}
$('dub-safe').onchange=()=>{try{localStorage.setItem('dub-safe',$('dub-safe').checked?'1':'0')}catch{}preview()};
$('dub-pv-mute').onclick=()=>{fg.dataset.mute=fg.dataset.mute==='1'?'0':'1';$('dub-pv-mute').textContent=fg.dataset.mute==='1'?'🔇':'🔊';preview()};
// hooks for design_tab.js (Dựng video): same page, other sections and defaults
window.dubApi={drawImage:(o,W,H)=>drawImage(o,null,W,H),startLabel:()=>startLabel(),settings,apply,remember,labels,preview:()=>preview(),refresh:()=>refresh(),draw:()=>draw(),say,files:()=>files,loadPresets:()=>loadPresets(),
 load:()=>{let saved={};try{saved=JSON.parse(localStorage.getItem(storeKey())||'null')||mergedOld()}catch{}apply({...caps.defaults,...saved})},jobs:()=>jobs,localImport:f=>localImport(f)};
draw();loadOverlays();loadImages();
// how many videos run at the same time (server setting); the video settings themselves live in the export popover
// of the header (resolution, fps, quality, encoder, loudness, folder, file info): one place for every export setting
{const old=$('loudness');if(old){const cell=old.closest('.cc-items')||old.parentElement;old.hidden=true;$('dub-loud').hidden=false;cell.append($('dub-loud'))}}
function runNote(){const p=+$('dub-parallel').value,enc=$('encoder')?.value||'cpu',hw=enc!=='cpu'&&(enc!=='auto'||window.hardwareEncoder);
 $('dub-run-note').textContent=`${p===1?'Chạy lần lượt từng video.':`Chạy ${p} video cùng lúc: nhanh hơn khi máy nhiều nhân/RAM (mỗi video thêm khoảng 1–2 GB RAM).`} ${hw?'Mã hóa bằng card đồ họa: nhanh hơn, ít tốn CPU.':'Mã hóa bằng CPU: chậm hơn card đồ họa nhưng chạy mọi máy.'} Tách giọng AI (Demucs): tối đa ${$('dub-demucs-n').value} video cùng lúc, mỗi video Demucs cần khoảng 3–4 GB RAM (hoặc VRAM khi có card).`;
 const o=settings(),sel=id=>$(id)?.selectedOptions[0]?.textContent.replace(/\s*[·(].*$/,'')||'';
 $('dub-out-text').textContent=`Xuất: ${sel('resolution')} · tối đa ${o.out_fps} fps · ${o.out_quality==='high'?'chất lượng cao':'tiêu chuẩn'} · ${sel('encoder')} · ${o.loudness==='tiktok'?'−14 LUFS':'giữ âm lượng'}${o.meta?' · ghi thông tin file':''}`}
$('dub-out-edit').onclick=e=>{e.stopPropagation();$('export-badge')?.click()};
for(const id of ['resolution','fps','quality','encoder','dub-loud'])$(id)?.addEventListener('change',()=>{remember();runNote()});
// px boxes follow the export size (resolution, frame, the video's own shape)
for(const id of ['resolution','dub-canvas'])$(id)?.addEventListener('change',()=>labels());fg.addEventListener('loadedmetadata',()=>labels());
if($('encoder'))new MutationObserver(runNote).observe($('encoder'),{childList:true});
// Thông tin file lives in the export settings popover (outside this tab): changes are remembered and go into templates
for(const id of ['meta-on','meta-strip','meta-author','meta-url','meta-publisher','meta-copyright','meta-rating','meta-back-min','meta-back-max'])$(id)?.addEventListener('change',()=>{remember();runNote()});
$('dub-resume').onchange=async()=>{try{const q=await json('/dub/queue',{resume:$('dub-resume').checked});$('dub-resume').checked=q.resume}catch(e){say(e.message)}};
request('/dub/queue').then(q=>{$('dub-parallel').value=String(q.parallel);$('dub-resume').checked=q.resume!==false;$('dub-demucs-n').value=String(q.demucs||1);runNote()}).catch(()=>{});
$('dub-demucs-n').onchange=async()=>{try{const q=await json('/dub/queue',{demucs:+$('dub-demucs-n').value});$('dub-demucs-n').value=String(q.demucs);say(`Tách giọng AI tối đa ${q.demucs} video cùng lúc.`)}catch(e){say(e.message)}runNote()};
$('dub-parallel').onchange=async()=>{try{const q=await json('/dub/queue',{parallel:+$('dub-parallel').value});$('dub-parallel').value=String(q.parallel);say(`Đã đặt chạy ${q.parallel} video cùng lúc.`)}catch(e){say(e.message)}runNote()};
})();
