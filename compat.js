// Runs first, in old-style JavaScript every browser can read: checks that the browser is new enough for the app and
// shows any script error on the page (red bar), so a broken button is never silent.
(function () {
  'use strict';
  var shown = {};
  function bar(text, kind) {
    if (shown[text]) return;
    shown[text] = true;
    shown.count = (shown.count || 0) + 1;
    if (shown.count > 3 && kind !== 'old') return;   // the first errors say enough
    var box = document.getElementById('app-alert');
    if (!box) {
      box = document.createElement('div');
      box.id = 'app-alert';
      box.style.cssText = 'position:fixed;left:12px;right:12px;bottom:12px;z-index:99999;font:13px/1.45 system-ui,sans-serif;display:flex;flex-direction:column;gap:6px';
      (document.body || document.documentElement).appendChild(box);
    }
    var row = document.createElement('div');
    row.style.cssText = 'background:' + (kind === 'old' ? '#5a3b00' : '#5a1020') + ';color:#fff;border:1px solid #ffffff55;border-radius:10px;padding:10px 14px;box-shadow:0 8px 24px #0008;white-space:pre-wrap';
    row.textContent = text;
    var close = document.createElement('button');
    close.textContent = '✕';
    close.style.cssText = 'float:right;background:none;border:0;color:#fff;font-size:15px;cursor:pointer;margin-left:10px';
    close.onclick = function () { box.removeChild(row); };
    row.insertBefore(close, row.firstChild);
    box.appendChild(row);
  }
  var missing = [];
  try { new Function('var a={};return a?.b??1'); } catch (e) { missing.push('JavaScript mới (?. ??)'); }
  if (!('replaceChildren' in Element.prototype)) missing.push('replaceChildren');
  if (!window.fetch || !window.Promise) missing.push('fetch');
  if (!(window.CSS && CSS.supports && CSS.supports('aspect-ratio', '1/1'))) missing.push('CSS aspect-ratio');
  function ready(fn) { if (document.body) fn(); else document.addEventListener('DOMContentLoaded', fn); }
  if (missing.length) {
    ready(function () {
      bar('⚠ Trình duyệt này quá cũ nên nhiều chức năng của Review Studio không chạy (thiếu: ' + missing.join(', ') + ').\n' +
          'Hãy mở http://127.0.0.1:8000 bằng Google Chrome hoặc Microsoft Edge bản mới (từ bản 90 trở lên). ' +
          'Edge đời cũ (biểu tượng chữ e xanh dương, Windows 10 bản cũ) cũng không chạy được: cập nhật Windows hoặc cài Edge mới tại microsoft.com/edge.\n' +
          'Trình duyệt đang dùng: ' + navigator.userAgent, 'old');
    });
  }
  // only the app's own files count: errors of browser extensions (ad blockers, translators…) are not the app's
  function ours(file) { return !file || String(file).indexOf(location.origin + '/') === 0; }
  window.addEventListener('error', function (e) {
    if (!e || !e.message) return;   // a picture or video that did not load: not a script error
    if (!ours(e.filename)) return;
    var where = e.filename ? ' (' + String(e.filename).replace(/^.*\//, '') + ':' + e.lineno + ')' : '';
    ready(function () { bar('⚠ Lỗi giao diện: ' + e.message + where + '\nChụp màn hình thông báo này gửi người hỗ trợ.', 'error'); });
  });
  window.addEventListener('unhandledrejection', function (e) {
    var r = e && e.reason;
    if (r && r.name === 'AbortError') return;
    // errors from the server are already shown by the page itself; only unexpected script errors here
    if (r && r.status) return;
    var text = r && (r.stack || r.message) || String(r);
    if (/(chrome|moz|safari)-extension:\/\//.test(text)) return;
    if (/Failed to fetch|NetworkError|Load failed/i.test(text)) {
      ready(function () { bar('⚠ Mất kết nối với ứng dụng. Kiểm tra cửa sổ đen (START_WINDOWS.bat) còn mở không rồi tải lại trang.', 'error'); });
      return;
    }
    ready(function () { bar('⚠ Lỗi giao diện: ' + String(text).split('\n').slice(0, 2).join(' · ') + '\nChụp màn hình thông báo này gửi người hỗ trợ.', 'error'); });
  });
})();
