/**
 * EMT 小測驗：作答紀錄接收端＋題目分析（Google Apps Script，綁在試算表上）  第 2 版
 *
 * - doPost：接收網站送來的 JSON（Content-Type: text/plain），嚴格驗證後寫入：
 *   ・作答紀錄（每完成一組 10 題送一次）→「responses」（一列一組）與「items」（一列一題，可關閉）
 *   ・identify（學生按「成果報告產生」時送一次）→ 把班級、座號補進同一作答編號的列；同一作答編號只收第一次
 * - importBank：從網站抓題庫索引，寫成「題庫」工作表（題號 → 題幹、選項文字）
 * - analyze：依 responses 產生「item_stats」（難度 p、鑑別度 D、點二系列相關、選項分布，附題幹與選項文字）
 * - 選單「EMT 分析 → 重新計算／匯入最新題庫」
 *
 * 不收姓名；班級座號只有學生產生成果報告的組別才有。Apps Script 本來就拿不到送出者的 IP。
 * 設定與更新步驟見同資料夾 README.md。
 */

var CONFIG = {
  TOKEN: '',            // 共用口令；留空＝不檢查。要和網站 tools/site_config.json 的 SHEET_TOKEN 相同（只能擋掃描，不是保密）
  WRITE_ITEMS: true,    // 同時寫「items」長格式工作表（一列一題，方便樞紐分析）
  MAX_ITEMS: 20,        // 單次最多幾題
  MAX_BODY: 8000,       // 單次最多幾個字元
  MIN_N: 30,            // 作答人次少於此數標示「樣本不足」
  GROUP: 0.27,          // 高低分組比例
  BANK_URL: 'https://henrychao521.github.io/emt-course-site/assets/quiz-bank-index.json',
  SHEET_RESPONSES: 'responses',
  SHEET_ITEMS: 'items',
  SHEET_STATS: 'item_stats',
  SHEET_NOTES: 'item_stats_說明',
  SHEET_BANK: '題庫'
};

var SLOT_FIELDS = ['題號', '版本', '對錯', '所選', '正解'];
var RESP_BASE = ['時間戳', '作答編號', '題庫版本', '第幾組', '題數', '答對數', '班級', '座號'];
var ITEMS_HEADER = ['時間戳', '作答編號', '題庫版本', '第幾組', '班級', '座號', '題序', '題號', '版本', '題型', '對錯', '所選', '正解'];
var STATS_HEADER = ['題號', '版本', '題幹', '題型', '作答人次', '答對人次', '答對率p', '高低分組各幾人', '高分組答對率', '低分組答對率',
  '鑑別度D', '點二系列相關', '正解', '選項分布（全體）', '選項分布（高分組）', '選項分布（低分組）', '提示'];
var OPT_CODES = ['A', 'B', 'C', 'D', 'E', 'F'];
var BANK_HEADER = ['題號', '版本', '題型', '章節', '難度', '題幹', '正解',
  '選項A', '選項B', '選項C', '選項D', '選項E', '選項F', '正確步驟', '題庫版本'];
var TYPE_NAME = { single: '單選', tf: '是非', scenario: '情境判斷', order: '排序' };
var TOP_KEYS = ['v', 'type', 'token', 'rid', 'bank', 'round', 'items'];
var IDENT_KEYS = ['v', 'type', 'token', 'rid', 'class', 'seat'];
var ITEM_KEYS = ['q', 'h', 't', 'ok', 'a', 'k'];
var ANS_RE = /^([A-F]|正確|錯誤|[1-9](>[1-9]){1,8})$/;
// 班級：中文、英文字母、數字、-，1–10 字，不可用 - 開頭（避免匯出 CSV 後被 Excel 當公式）；要和網站 app.js 的 CLASS_RE 相同
var CLASS_RE = /^(?!-)[0-9A-Za-z㐀-鿿\-]{1,10}$/;
var SEAT_RE = /^[0-9]{1,4}$/;

function responsesHeader_() {
  var h = RESP_BASE.slice();
  for (var i = 1; i <= CONFIG.MAX_ITEMS; i++) SLOT_FIELDS.forEach(function (f) { h.push('題' + i + '_' + f); });
  return h;
}

// ───────────── 接收 ─────────────

function doGet() {
  return ContentService.createTextOutput('EMT 小測驗作答紀錄接收端運作中（只接受網站送出的 POST）。');
}

function doPost(e) {
  var out;
  try {
    out = handle_(e && e.postData ? String(e.postData.contents || '') : '');
  } catch (err) {
    out = { ok: false, error: 'server' };
  }
  return ContentService.createTextOutput(JSON.stringify(out)).setMimeType(ContentService.MimeType.JSON);
}

function handle_(body) {
  var v = validate_(body);
  if (!v.ok) return v;
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) return { ok: false, error: 'busy' };
  try {
    return v.kind === 'identify' ? writeIdentify_(v.data) : writeRecord_(v.data);
  } finally {
    lock.releaseLock();
  }
}

function writeRecord_(d) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var rs = ensureSheet_(ss, CONFIG.SHEET_RESPONSES, responsesHeader_());
  if (findRow_(rs, d.rid) > 0) return { ok: true, dup: true };  // 同一作答編號只收一次（重送也不重複計）
  var now = new Date();
  var nOk = d.items.filter(function (it) { return it.ok === 1; }).length;
  var row = [now, d.rid, d.bank, d.round, d.items.length, nOk, '', ''];
  for (var i = 0; i < CONFIG.MAX_ITEMS; i++) {
    var it = d.items[i];
    if (it) row.push(it.q, it.h, it.ok, it.a, it.k); else row.push('', '', '', '', '');
  }
  rs.appendRow(row);
  if (CONFIG.WRITE_ITEMS) {
    var is = ensureSheet_(ss, CONFIG.SHEET_ITEMS, ITEMS_HEADER);
    var rows = d.items.map(function (it, j) {
      return [now, d.rid, d.bank, d.round, '', '', j + 1, it.q, it.h, TYPE_NAME[it.t], it.ok, it.a, it.k];
    });
    is.getRange(is.getLastRow() + 1, 1, rows.length, ITEMS_HEADER.length).setValues(rows);
  }
  return { ok: true };
}

/** 班級座號補進同一作答編號的列。已經有班級座號就不覆寫（只收第一次）。 */
function writeIdentify_(d) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var rs = ensureSheet_(ss, CONFIG.SHEET_RESPONSES, responsesHeader_());
  var r = findRow_(rs, d.rid);
  if (r < 0) return { ok: false, error: 'no_rid' };
  var cur = rs.getRange(r, 7, 1, 2).getValues()[0];
  if (String(cur[0]) !== '' || String(cur[1]) !== '') return { ok: true, dup: true };
  rs.getRange(r, 7, 1, 2).setValues([[d.cls, d.seat]]);
  var is = ss.getSheetByName(CONFIG.SHEET_ITEMS);
  if (is && is.getLastRow() > 1) {
    ensureSheet_(ss, CONFIG.SHEET_ITEMS, ITEMS_HEADER);
    var ids = is.getRange(2, 2, is.getLastRow() - 1, 1).getValues();
    for (var i = 0; i < ids.length; i++) {
      if (String(ids[i][0]) === d.rid) is.getRange(i + 2, 5, 1, 2).setValues([[d.cls, d.seat]]);
    }
  }
  return { ok: true };
}

/** 嚴格驗證：格式不對、多出欄位、超過長度一律拒收。回傳 {ok:true,kind,data} 或 {ok:false,error}。 */
function validate_(body) {
  if (typeof body !== 'string' || !body) return { ok: false, error: 'empty' };
  if (body.length > CONFIG.MAX_BODY) return { ok: false, error: 'too_long' };
  var d;
  try { d = JSON.parse(body); } catch (e) { return { ok: false, error: 'json' }; }
  if (!d || typeof d !== 'object' || Array.isArray(d)) return { ok: false, error: 'shape' };
  if (d.v !== 1) return { ok: false, error: 'version' };
  if (CONFIG.TOKEN && d.token !== CONFIG.TOKEN) return { ok: false, error: 'token' };
  if (d.token != null && (typeof d.token !== 'string' || d.token.length > 64)) return { ok: false, error: 'token' };
  if (typeof d.rid !== 'string' || !/^[0-9a-f]{32}$/.test(d.rid)) return { ok: false, error: 'rid' };
  if (d.type === 'identify') return validateIdentify_(d);
  if (d.type != null && d.type !== 'record') return { ok: false, error: 'type' };
  var keys = Object.keys(d);
  for (var i = 0; i < keys.length; i++) if (TOP_KEYS.indexOf(keys[i]) < 0) return { ok: false, error: 'extra_field' };
  if (typeof d.bank !== 'string' || !/^[0-9A-Za-z._-]{0,40}$/.test(d.bank)) return { ok: false, error: 'bank' };
  if (typeof d.round !== 'number' || d.round % 1 !== 0 || d.round < 1 || d.round > 999) return { ok: false, error: 'round' };
  if (!Array.isArray(d.items) || d.items.length < 1 || d.items.length > CONFIG.MAX_ITEMS) return { ok: false, error: 'items' };
  var seen = {}, items = [];
  for (var j = 0; j < d.items.length; j++) {
    var it = d.items[j];
    if (!it || typeof it !== 'object' || Array.isArray(it)) return { ok: false, error: 'item_shape' };
    var ik = Object.keys(it);
    for (var m = 0; m < ik.length; m++) if (ITEM_KEYS.indexOf(ik[m]) < 0) return { ok: false, error: 'item_extra_field' };
    if (typeof it.q !== 'string' || !/^q\d{3}$/.test(it.q)) return { ok: false, error: 'qid' };
    if (seen[it.q]) return { ok: false, error: 'qid_dup' };
    seen[it.q] = 1;
    if (typeof it.h !== 'string' || !/^[0-9a-f]{8}$/.test(it.h)) return { ok: false, error: 'hash' };
    if (!TYPE_NAME.hasOwnProperty(it.t)) return { ok: false, error: 'type' };
    if (it.ok !== 0 && it.ok !== 1) return { ok: false, error: 'ok' };
    if (typeof it.a !== 'string' || typeof it.k !== 'string' || it.a.length > 20 || it.k.length > 20 ||
        !ANS_RE.test(it.a) || !ANS_RE.test(it.k)) return { ok: false, error: 'answer' };
    var isOrder = it.k.indexOf('>') >= 0, isTf = it.k === '正確' || it.k === '錯誤';
    if ((it.t === 'order') !== isOrder || (it.t === 'tf') !== isTf) return { ok: false, error: 'answer_type' };
    if (isOrder && it.a.split('>').length !== it.k.split('>').length) return { ok: false, error: 'answer_len' };
    if ((it.a === it.k) !== (it.ok === 1)) return { ok: false, error: 'ok_mismatch' };  // 對錯要和所選／正解一致
    items.push({ q: it.q, h: it.h, t: it.t, ok: it.ok, a: it.a, k: it.k });
  }
  return { ok: true, kind: 'record', data: { rid: d.rid, bank: d.bank, round: d.round, items: items } };
}

function validateIdentify_(d) {
  var keys = Object.keys(d);
  for (var i = 0; i < keys.length; i++) if (IDENT_KEYS.indexOf(keys[i]) < 0) return { ok: false, error: 'extra_field' };
  if (typeof d['class'] !== 'string' || !CLASS_RE.test(d['class'])) return { ok: false, error: 'class' };
  if (typeof d.seat !== 'string' || !SEAT_RE.test(d.seat)) return { ok: false, error: 'seat' };
  return { ok: true, kind: 'identify', data: { rid: d.rid, cls: d['class'], seat: d.seat } };
}

function ensureSheet_(ss, name, header) {
  var sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  if (sh.getLastRow() === 0) {
    // 全部欄位設成純文字，避免 1>2>3、2026-09-29、全數字的作答編號、座號 07 被自動轉成日期或數字
    sh.getRange('A:' + colLetter_(header.length)).setNumberFormat('@');
    sh.getRange('A:A').setNumberFormat('yyyy-mm-dd hh:mm:ss');
    sh.getRange(1, 1, 1, header.length).setValues([header]);
    sh.setFrozenRows(1);
  } else {
    migrate_(sh, name);
  }
  return sh;
}

/** 第 1 版的工作表沒有「班級」「座號」：在原本位置插入兩欄（既有資料會跟著右移，不會錯位）。 */
function migrate_(sh, name) {
  var at = name === CONFIG.SHEET_RESPONSES ? 6 : name === CONFIG.SHEET_ITEMS ? 4 : 0;
  if (!at) return;
  var head = sh.getRange(1, at + 1, 1, 2).getValues()[0];
  if (head[0] === '班級' && head[1] === '座號') return;
  sh.insertColumnsAfter(at, 2);
  sh.getRange(colLetter_(at + 1) + ':' + colLetter_(at + 2)).setNumberFormat('@');
  sh.getRange(1, at + 1, 1, 2).setValues([['班級', '座號']]);
}

function findRow_(sh, rid) {
  var n = sh.getLastRow() - 1;
  if (n < 1) return -1;
  var col = sh.getRange(2, 2, n, 1).getValues();
  for (var i = 0; i < col.length; i++) if (String(col[i][0]) === rid) return i + 2;
  return -1;
}

function colLetter_(n) {
  var s = '';
  while (n > 0) { var m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); }
  return s;
}

// ───────────── 選單 ─────────────

function onOpen() {
  SpreadsheetApp.getUi().createMenu('EMT 分析')
    .addItem('重新計算', 'analyze')
    .addItem('匯入最新題庫', 'importBank')
    .addToUi();
}

// ───────────── 題庫 ─────────────

/** 從網站抓題庫索引，整張覆寫「題庫」工作表。第一次執行會要求「連線到外部服務」授權。 */
function importBank() {
  var res = UrlFetchApp.fetch(CONFIG.BANK_URL, { muteHttpExceptions: true, followRedirects: true });
  var code = res.getResponseCode();
  if (code !== 200) throw new Error('下載題庫失敗：HTTP ' + code + '（' + CONFIG.BANK_URL + '）');
  var d;
  try { d = JSON.parse(res.getContentText('UTF-8')); } catch (e) { throw new Error('題庫索引不是正確的 JSON'); }
  var rows = bankRows_(d);
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(CONFIG.SHEET_BANK) || ss.insertSheet(CONFIG.SHEET_BANK);
  sh.clear();
  sh.getRange('A:' + colLetter_(BANK_HEADER.length)).setNumberFormat('@');
  sh.getRange(1, 1, rows.length + 1, BANK_HEADER.length).setValues([BANK_HEADER].concat(rows));
  sh.setFrozenRows(1);
  var msg = '已匯入題庫 ' + rows.length + ' 題（版本 ' + (d.version || '未標示') + '）';
  try { ss.toast(msg, 'EMT 分析', 5); } catch (e) { /* 從編輯器執行時沒有畫面 */ }
  return { count: rows.length, version: String(d.version || '') };
}

/** 題庫索引 JSON → 「題庫」工作表的列；格式不對就丟錯，不寫入半套資料。 */
function bankRows_(d) {
  if (!d || !Array.isArray(d.questions) || !d.questions.length) throw new Error('題庫索引沒有題目');
  var ver = String(d.version || '');
  return d.questions.map(function (q) {
    if (!q || !/^q\d{3}$/.test(q.id) || !/^[0-9a-f]{8}$/.test(q.h) || !TYPE_NAME.hasOwnProperty(q.type)) {
      throw new Error('題庫索引格式不對：' + JSON.stringify(q).slice(0, 80));
    }
    var opts = OPT_CODES.map(function (c) {
      var o = (q.options || []).filter(function (x) { return x.code === c; })[0];
      return o ? String(o.text) : '';
    });
    var steps = (q.steps || []).map(function (s, i) { return (i + 1) + '. ' + s; }).join('\n');
    return [q.id, q.h, TYPE_NAME[q.type], String(q.chapter || ''), String(q.difficulty || ''), String(q.stem || ''),
      String(q.answer || '')].concat(opts, [steps, ver]);
  });
}

/** 讀「題庫」工作表 → {題號: {h, stem, type, opts:{A:文字}}}；沒有匯入過就回傳 null。 */
function loadBank_(ss) {
  var sh = ss.getSheetByName(CONFIG.SHEET_BANK);
  if (!sh || sh.getLastRow() < 2) return null;
  var v = sh.getDataRange().getValues(), H = v[0], idx = {};
  H.forEach(function (h, i) { idx[h] = i; });
  var out = {};
  for (var r = 1; r < v.length; r++) {
    var row = v[r], id = String(row[idx['題號']] || '');
    if (!id) continue;
    var opts = {};
    OPT_CODES.forEach(function (c) { var t = String(row[idx['選項' + c]] || ''); if (t) opts[c] = t; });
    out[id] = { h: String(row[idx['版本']]), stem: String(row[idx['題幹']] || ''), type: String(row[idx['題型']] || ''), opts: opts };
  }
  return out;
}

// ───────────── 分析 ─────────────

/** 讀 responses（和題庫工作表，若有），重寫 item_stats 與說明頁。 */
function analyze() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var rs = ss.getSheetByName(CONFIG.SHEET_RESPONSES);
  var resp = rs && rs.getLastRow() > 1 ? parseResponses_(rs.getDataRange().getValues()) : [];
  var bank = loadBank_(ss);
  var stats = computeStats_(resp, CONFIG.MIN_N, CONFIG.GROUP, bank);
  var st = ss.getSheetByName(CONFIG.SHEET_STATS) || ss.insertSheet(CONFIG.SHEET_STATS);
  st.clear();
  var rows = [STATS_HEADER].concat(stats.map(function (s) {
    return [s.q, s.h, s.stem, s.type, s.n, s.nOk, s.p, s.g, s.pU, s.pL, s.D, s.rpb, s.key, s.dist, s.distU, s.distL, s.flags];
  }));
  st.getRange('A:D').setNumberFormat('@');
  st.getRange(1, 1, rows.length, STATS_HEADER.length).setValues(rows);
  st.setFrozenRows(1);
  var nIdent = resp.filter(function (r) { return r.identified; }).length;
  writeNotes_(ss, resp.length, stats.length, nIdent, bank);
  return { responses: resp.length, items: stats.length, identified: nIdent };
}

/** 把 responses 工作表的值（含標題列）轉成 [{rid, identified, items:[{q,h,ok,a,k}]}]；欄位依標題列定位，新舊版都能讀。 */
function parseResponses_(values) {
  var H = values[0].map(String);
  var base = H.indexOf('題1_題號'); if (base < 0) base = RESP_BASE.length;
  var ci = H.indexOf('班級'), si = H.indexOf('座號');
  var out = [];
  for (var r = 1; r < values.length; r++) {
    var row = values[r], items = [];
    for (var i = 0; i < CONFIG.MAX_ITEMS; i++) {
      var b = base + i * SLOT_FIELDS.length;
      var q = String(row[b] == null ? '' : row[b]).trim();
      if (!q) continue;
      items.push({ q: q, h: String(row[b + 1]), ok: Number(row[b + 2]) === 1 ? 1 : 0, a: String(row[b + 3]), k: String(row[b + 4]) });
    }
    var identified = ci >= 0 && si >= 0 && String(row[ci] == null ? '' : row[ci]) !== '' && String(row[si] == null ? '' : row[si]) !== '';
    if (items.length) out.push({ rid: String(row[1]), identified: identified, items: items });
  }
  return out;
}

function round3_(x) { return x === '' || x == null || isNaN(x) ? '' : Math.round(x * 1000) / 1000; }

/**
 * 題目分析（純函式，方便離線測試）。
 * resp：[{rid, items:[{q,h,ok,a,k}]}]；每題以「題號＋版本指紋」為單位。bank：loadBank_() 的結果或 null。
 * p＝答對率；D＝高分組答對率－低分組答對率（在「有作答這題的作答組」中，依該組總答對率排序取前後 27%）；
 * rpb＝該題對錯（0/1）與「同組其餘題答對率」的 Pearson 相關（即校正後的點二系列相關）。
 */
function computeStats_(resp, minN, groupRatio, bank) {
  var byItem = {}, order = [];
  resp.forEach(function (r) {
    var nOk = r.items.reduce(function (s, it) { return s + it.ok; }, 0), len = r.items.length;
    r.items.forEach(function (it) {
      var key = it.q + '@' + it.h;
      if (!byItem[key]) { byItem[key] = { q: it.q, h: it.h, rows: [], keys: {} }; order.push(key); }
      var s = byItem[key];
      s.rows.push({ rid: r.rid, ok: it.ok, a: it.a, total: nOk / len, rest: len > 1 ? (nOk - it.ok) / (len - 1) : null });
      s.keys[it.k] = (s.keys[it.k] || 0) + 1;
    });
  });
  order.sort();
  return order.map(function (key) {
    var s = byItem[key], rows = s.rows, n = rows.length;
    var nOk = rows.reduce(function (t, x) { return t + x.ok; }, 0);
    var keyAns = Object.keys(s.keys).sort(function (a, b) { return s.keys[b] - s.keys[a]; })[0];
    var type = keyAns.indexOf('>') >= 0 ? '排序' : (keyAns === '正確' || keyAns === '錯誤') ? '是非' : '選擇';
    var bq = bank ? bank[s.q] : null, same = !!(bq && bq.h === s.h);
    var stem = bq ? (same ? bq.stem : '（現行版）' + bq.stem) : '';
    var label = same ? bq.opts : null;
    var sorted = rows.slice().sort(function (a, b) { return b.total - a.total || (a.rid < b.rid ? -1 : a.rid > b.rid ? 1 : 0); });
    var g = Math.round(groupRatio * n);
    var upper = [], lower = [], pU = '', pL = '', D = '';
    if (g >= 1 && 2 * g <= n) {
      upper = sorted.slice(0, g); lower = sorted.slice(n - g);
      pU = mean_(upper.map(function (x) { return x.ok; }));
      pL = mean_(lower.map(function (x) { return x.ok; }));
      D = pU - pL;
    }
    var pr = rows.filter(function (x) { return x.rest !== null; });
    var rpb = pearson_(pr.map(function (x) { return x.ok; }), pr.map(function (x) { return x.rest; }));
    var p = n ? nOk / n : '';
    var distAll = dist_(rows, keyAns, type, label), distU = upper.length ? dist_(upper, keyAns, type, label) : '',
      distL = lower.length ? dist_(lower, keyAns, type, label) : '';
    var flags = [];
    if (bank && !bq) flags.push('題庫中找不到這個題號');
    if (bq && !same) flags.push('題目已修改，舊版作答');
    if (n < minN) flags.push('樣本不足（' + n + ' < ' + minN + '），指標僅供參考');
    else {
      if (p >= 0.9) flags.push('偏易');
      if (p <= 0.2) flags.push('偏難');
      if (D !== '' && D < 0.2) flags.push('鑑別度低，建議檢查題意或選項');
      else if (D !== '' && D >= 0.4) flags.push('鑑別度佳');
      if (rpb !== '' && rpb < 0) flags.push('與其餘題負相關，檢查答案是否正確');
      if (type === '選擇' && upper.length) {
        var cu = countBy_(upper), cl = countBy_(lower);
        Object.keys(cu).forEach(function (a) {
          if (a !== keyAns && cu[a] > (cl[a] || 0)) flags.push('誘答選項 ' + a + ' 高分組反而較常選');
        });
      }
    }
    if (Object.keys(s.keys).length > 1) flags.push('同一版本出現不同正解，請檢查資料');
    var typeName = bq && same && bq.type ? bq.type : type;
    return { q: s.q, h: s.h, stem: stem, type: typeName, n: n, nOk: nOk, p: round3_(p), g: g && 2 * g <= n ? g : '', pU: round3_(pU), pL: round3_(pL),
      D: round3_(D), rpb: round3_(rpb), key: keyAns, dist: distAll, distU: distU, distL: distL, flags: flags.join('；') };
  });
}

function mean_(a) { return a.length ? a.reduce(function (s, x) { return s + x; }, 0) / a.length : ''; }

function pearson_(x, y) {
  var n = x.length;
  if (n < 3) return '';
  var mx = mean_(x), my = mean_(y), sxy = 0, sxx = 0, syy = 0;
  for (var i = 0; i < n; i++) { sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) * (x[i] - mx); syy += (y[i] - my) * (y[i] - my); }
  if (sxx === 0 || syy === 0) return '';
  return sxy / Math.sqrt(sxx * syy);
}

function countBy_(rows) {
  var c = {};
  rows.forEach(function (x) { c[x.a] = (c[x.a] || 0) + 1; });
  return c;
}

function short_(t) {
  var a = Array.from ? Array.from(t) : t.split('');
  return a.length > 12 ? a.slice(0, 12).join('') + '…' : t;
}

/**
 * 選項分布字串，例如「A＊（直接加壓止血）：12（40%）｜B（先塗藥膏再包紮）：3（10%）」。
 * 正解標 ＊；選擇題附選項文字前 12 字（題庫已匯入且版本相同時）；排序題只列最常見的 3 種順序。
 */
function dist_(rows, keyAns, type, label) {
  var c = countBy_(rows), n = rows.length;
  var ks = Object.keys(c);
  if (type === '排序') {
    ks.sort(function (a, b) { return c[b] - c[a] || (a < b ? -1 : 1); });
    ks = ks.slice(0, 3);
  } else {
    if (ks.indexOf(keyAns) < 0) { ks.push(keyAns); c[keyAns] = 0; }
    if (type === '選擇' && label) Object.keys(label).forEach(function (code) { if (ks.indexOf(code) < 0) { ks.push(code); c[code] = 0; } });
    ks.sort();
  }
  var s = ks.map(function (a) {
    var txt = type === '選擇' && label && label[a] ? '（' + short_(label[a]) + '）' : '';
    return a + (a === keyAns ? '＊' : '') + txt + '：' + c[a] + '（' + Math.round(c[a] * 100 / n) + '%）';
  }).join('｜');
  if (type === '排序' && Object.keys(c).length > 3) s += '｜其他 ' + (Object.keys(c).length - 3) + ' 種';
  return s;
}

function writeNotes_(ss, nResp, nItems, nIdent, bank) {
  var sh = ss.getSheetByName(CONFIG.SHEET_NOTES) || ss.insertSheet(CONFIG.SHEET_NOTES);
  sh.clear();
  var lines = [
    ['計算時間', new Date()],
    ['作答組數', nResp],
    ['其中有班級座號的組數', nIdent],
    ['題目數（題號＋版本）', nItems],
    ['題庫工作表', bank ? '已匯入 ' + Object.keys(bank).length + ' 題；題幹與選項文字取自「題庫」工作表' : '尚未匯入（選單「EMT 分析 → 匯入最新題庫」），題幹與選項文字會空白'],
    ['答對率 p', '該題作答人次中答對的比例；數值越大越容易。一般 0.3–0.8 較能區分程度。'],
    ['鑑別度 D', '在「有作答這題的作答組」中，依該組 10 題總答對率排序，取前 ' + Math.round(CONFIG.GROUP * 100) + '% 為高分組、後 ' + Math.round(CONFIG.GROUP * 100) + '% 為低分組；D＝高分組答對率－低分組答對率。常見參考：≥0.4 佳、0.3–0.39 尚可、0.2–0.29 待改進、<0.2 建議修改或刪除。同分時以作答編號排序決定分組。'],
    ['點二系列相關', '該題對錯（0/1）與「同一組其餘題答對率」的相關係數（已排除本題，避免自我膨脹）；負值通常表示答案標錯或題意誤導。'],
    ['選項分布', '選擇題的代號依教師版頁面各題 A、B、C、D 的順序，括號內是選項文字前 12 字；＊為正解。排序題以步驟序號表示點選順序（例如 2>1>3>4），只列最常見的 3 種。高分組較常選的錯誤選項會在「提示」欄標出。'],
    ['題目已修改，舊版作答', '作答時的版本指紋和目前題庫不同：題目內容後來改過。題幹欄顯示的是「現行版」題幹，選項文字不套用（代號可能已對不上），這一列的統計只代表舊版。'],
    ['樣本不足', '作答人次少於 ' + CONFIG.MIN_N + ' 時標示，指標波動大，只供參考。'],
    ['矩陣抽樣的限制', '每組 10 題是從題庫隨機抽出，每個人做的題目不同：①「總分」是不同題目組合的答對率，組合難易不一，高低分組只能近似代表能力高低；②每題的作答人次會比作答組數少很多（約為 10／題庫題數），指標需要更多作答才穩定；③同一個學生可能做好幾組，這些作答組彼此不是獨立樣本；④題目改版（版本指紋改變）後新舊版分開統計。'],
    ['資料', '不含姓名；只有學生產生成果報告的組別有班級座號。Apps Script 取得不到送出者 IP。']
  ];
  sh.getRange(1, 1, lines.length, 2).setValues(lines);
}
