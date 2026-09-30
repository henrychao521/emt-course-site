/**
 * EMT 小測驗：匿名作答紀錄接收端＋題目分析（Google Apps Script，綁在試算表上）
 *
 * - doPost：接收網站每完成一組送來的 JSON（Content-Type: text/plain），嚴格驗證後寫入
 *   「responses」（一列一次作答組）與「items」（一列一題，可關閉）。
 * - analyze：依 responses 產生「item_stats」（難度 p、鑑別度 D、點二系列相關、選項分布）。
 * - 選單「EMT 分析 → 重新計算」。
 *
 * 不收姓名、班級、座號；Apps Script 本來就拿不到送出者的 IP。
 * 設定步驟見同資料夾 README.md。
 */

var CONFIG = {
  TOKEN: '',            // 共用口令；留空＝不檢查。要和網站 tools/site_config.json 的 SHEET_TOKEN 相同（只能擋掃描，不是保密）
  WRITE_ITEMS: true,    // 同時寫「items」長格式工作表（一列一題，方便樞紐分析）
  MAX_ITEMS: 20,        // 單次最多幾題
  MAX_BODY: 8000,       // 單次最多幾個字元
  MIN_N: 30,            // 作答人次少於此數標示「樣本不足」
  GROUP: 0.27,          // 高低分組比例
  SHEET_RESPONSES: 'responses',
  SHEET_ITEMS: 'items',
  SHEET_STATS: 'item_stats',
  SHEET_NOTES: 'item_stats_說明'
};

var SLOT_FIELDS = ['題號', '版本', '對錯', '所選', '正解'];
var BASE_COLS = 6;  // 時間戳、作答編號、題庫版本、第幾組、題數、答對數
var ITEMS_HEADER = ['時間戳', '作答編號', '題庫版本', '第幾組', '題序', '題號', '版本', '題型', '對錯', '所選', '正解'];
var STATS_HEADER = ['題號', '版本', '題型', '作答人次', '答對人次', '答對率p', '高低分組各幾人', '高分組答對率', '低分組答對率',
  '鑑別度D', '點二系列相關', '正解', '選項分布（全體）', '選項分布（高分組）', '選項分布（低分組）', '提示'];
var TYPE_NAME = { single: '單選', tf: '是非', scenario: '情境判斷', order: '排序' };
var TOP_KEYS = ['v', 'token', 'rid', 'bank', 'round', 'items'];
var ITEM_KEYS = ['q', 'h', 't', 'ok', 'a', 'k'];
var ANS_RE = /^([A-F]|正確|錯誤|[1-9](>[1-9]){1,8})$/;

function responsesHeader_() {
  var h = ['時間戳', '作答編號', '題庫版本', '第幾組', '題數', '答對數'];
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
  var d = v.data;
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) return { ok: false, error: 'busy' };
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var rs = ensureSheet_(ss, CONFIG.SHEET_RESPONSES, responsesHeader_());
    if (ridExists_(rs, d.rid)) return { ok: true, dup: true };  // 同一作答編號只收一次（重送也不重複計）
    var now = new Date();
    var nOk = d.items.filter(function (it) { return it.ok === 1; }).length;
    var row = [now, d.rid, d.bank, d.round, d.items.length, nOk];
    for (var i = 0; i < CONFIG.MAX_ITEMS; i++) {
      var it = d.items[i];
      if (it) row.push(it.q, it.h, it.ok, it.a, it.k); else row.push('', '', '', '', '');
    }
    rs.appendRow(row);
    if (CONFIG.WRITE_ITEMS) {
      var is = ensureSheet_(ss, CONFIG.SHEET_ITEMS, ITEMS_HEADER);
      var rows = d.items.map(function (it, j) {
        return [now, d.rid, d.bank, d.round, j + 1, it.q, it.h, TYPE_NAME[it.t], it.ok, it.a, it.k];
      });
      is.getRange(is.getLastRow() + 1, 1, rows.length, ITEMS_HEADER.length).setValues(rows);
    }
    return { ok: true };
  } finally {
    lock.releaseLock();
  }
}

/** 嚴格驗證：格式不對、多出欄位、超過長度一律拒收。回傳 {ok:true,data} 或 {ok:false,error}。 */
function validate_(body) {
  if (typeof body !== 'string' || !body) return { ok: false, error: 'empty' };
  if (body.length > CONFIG.MAX_BODY) return { ok: false, error: 'too_long' };
  var d;
  try { d = JSON.parse(body); } catch (e) { return { ok: false, error: 'json' }; }
  if (!d || typeof d !== 'object' || Array.isArray(d)) return { ok: false, error: 'shape' };
  var keys = Object.keys(d);
  for (var i = 0; i < keys.length; i++) if (TOP_KEYS.indexOf(keys[i]) < 0) return { ok: false, error: 'extra_field' };
  if (d.v !== 1) return { ok: false, error: 'version' };
  if (CONFIG.TOKEN && d.token !== CONFIG.TOKEN) return { ok: false, error: 'token' };
  if (d.token != null && (typeof d.token !== 'string' || d.token.length > 64)) return { ok: false, error: 'token' };
  if (typeof d.rid !== 'string' || !/^[0-9a-f]{32}$/.test(d.rid)) return { ok: false, error: 'rid' };
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
  return { ok: true, data: { rid: d.rid, bank: d.bank, round: d.round, items: items } };
}

function ensureSheet_(ss, name, header) {
  var sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  if (sh.getLastRow() === 0) {
    // 全部欄位設成純文字，避免 1>2>3、2026-09-29、全數字的作答編號被自動轉成日期或數字
    sh.getRange('A:' + colLetter_(header.length)).setNumberFormat('@');
    sh.getRange('A:A').setNumberFormat('yyyy-mm-dd hh:mm:ss');
    sh.getRange(1, 1, 1, header.length).setValues([header]);
    sh.setFrozenRows(1);
  }
  return sh;
}

function ridExists_(sh, rid) {
  var n = sh.getLastRow() - 1;
  if (n < 1) return false;
  var col = sh.getRange(2, 2, n, 1).getValues();
  for (var i = 0; i < col.length; i++) if (String(col[i][0]) === rid) return true;
  return false;
}

function colLetter_(n) {
  var s = '';
  while (n > 0) { var m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); }
  return s;
}

// ───────────── 分析 ─────────────

function onOpen() {
  SpreadsheetApp.getUi().createMenu('EMT 分析').addItem('重新計算', 'analyze').addToUi();
}

/** 讀 responses，重寫 item_stats 與說明頁。 */
function analyze() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var rs = ss.getSheetByName(CONFIG.SHEET_RESPONSES);
  var resp = rs && rs.getLastRow() > 1 ? parseResponses_(rs.getDataRange().getValues()) : [];
  var stats = computeStats_(resp, CONFIG.MIN_N, CONFIG.GROUP);
  var st = ss.getSheetByName(CONFIG.SHEET_STATS) || ss.insertSheet(CONFIG.SHEET_STATS);
  st.clear();
  var rows = [STATS_HEADER].concat(stats.map(function (s) {
    return [s.q, s.h, s.type, s.n, s.nOk, s.p, s.g, s.pU, s.pL, s.D, s.rpb, s.key, s.dist, s.distU, s.distL, s.flags];
  }));
  st.getRange('A:C').setNumberFormat('@');
  st.getRange(1, 1, rows.length, STATS_HEADER.length).setValues(rows);
  st.setFrozenRows(1);
  writeNotes_(ss, resp.length, stats.length);
  return { responses: resp.length, items: stats.length };
}

/** 把 responses 工作表的值（含標題列）轉成 [{rid, items:[{q,h,ok,a,k}]}]。 */
function parseResponses_(values) {
  var out = [];
  for (var r = 1; r < values.length; r++) {
    var row = values[r], items = [];
    for (var i = 0; i < CONFIG.MAX_ITEMS; i++) {
      var b = BASE_COLS + i * SLOT_FIELDS.length;
      var q = String(row[b] == null ? '' : row[b]).trim();
      if (!q) continue;
      items.push({ q: q, h: String(row[b + 1]), ok: Number(row[b + 2]) === 1 ? 1 : 0, a: String(row[b + 3]), k: String(row[b + 4]) });
    }
    if (items.length) out.push({ rid: String(row[1]), items: items });
  }
  return out;
}

function round3_(x) { return x === '' || x == null || isNaN(x) ? '' : Math.round(x * 1000) / 1000; }

/**
 * 題目分析（純函式，方便離線測試）。
 * resp：[{rid, items:[{q,h,ok,a,k}]}]；每題以「題號＋版本指紋」為單位。
 * p＝答對率；D＝高分組答對率－低分組答對率（在「有作答這題的作答組」中，依該組總答對率排序取前後 27%）；
 * rpb＝該題對錯（0/1）與「同組其餘題答對率」的 Pearson 相關（即校正後的點二系列相關）。
 */
function computeStats_(resp, minN, groupRatio) {
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
    var distAll = dist_(rows, keyAns, type), distU = upper.length ? dist_(upper, keyAns, type) : '', distL = lower.length ? dist_(lower, keyAns, type) : '';
    var flags = [];
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
    return { q: s.q, h: s.h, type: type, n: n, nOk: nOk, p: round3_(p), g: g && 2 * g <= n ? g : '', pU: round3_(pU), pL: round3_(pL),
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

/** 選項分布字串，正解標 ＊；排序題只列最常見的 3 種順序。 */
function dist_(rows, keyAns, type) {
  var c = countBy_(rows), n = rows.length;
  var ks = Object.keys(c);
  if (type === '排序') {
    ks.sort(function (a, b) { return c[b] - c[a] || (a < b ? -1 : 1); });
    ks = ks.slice(0, 3);
  } else {
    if (ks.indexOf(keyAns) < 0) { ks.push(keyAns); c[keyAns] = 0; }
    ks.sort();
  }
  var s = ks.map(function (a) { return a + (a === keyAns ? '＊' : '') + ' ' + c[a] + '（' + Math.round(c[a] * 100 / n) + '%）'; }).join('｜');
  if (type === '排序' && Object.keys(c).length > 3) s += '｜其他 ' + (Object.keys(c).length - 3) + ' 種';
  return s;
}

function writeNotes_(ss, nResp, nItems) {
  var sh = ss.getSheetByName(CONFIG.SHEET_NOTES) || ss.insertSheet(CONFIG.SHEET_NOTES);
  sh.clear();
  var lines = [
    ['計算時間', new Date()],
    ['作答組數', nResp],
    ['題目數（題號＋版本）', nItems],
    ['答對率 p', '該題作答人次中答對的比例；數值越大越容易。一般 0.3–0.8 較能區分程度。'],
    ['鑑別度 D', '在「有作答這題的作答組」中，依該組 10 題總答對率排序，取前 ' + Math.round(CONFIG.GROUP * 100) + '% 為高分組、後 ' + Math.round(CONFIG.GROUP * 100) + '% 為低分組；D＝高分組答對率－低分組答對率。常見參考：≥0.4 佳、0.3–0.39 尚可、0.2–0.29 待改進、<0.2 建議修改或刪除。同分時以作答編號排序決定分組。'],
    ['點二系列相關', '該題對錯（0/1）與「同一組其餘題答對率」的相關係數（已排除本題，避免自我膨脹）；負值通常表示答案標錯或題意誤導。'],
    ['選項分布', '選擇題的代號依教師版頁面各題 A、B、C、D 的順序；＊為正解。排序題以步驟序號表示點選順序（例如 2>1>3>4），只列最常見的 3 種。高分組較常選的錯誤選項會在「提示」欄標出。'],
    ['樣本不足', '作答人次少於 ' + CONFIG.MIN_N + ' 時標示，指標波動大，只供參考。'],
    ['矩陣抽樣的限制', '每組 10 題是從題庫隨機抽出，每個人做的題目不同：①「總分」是不同題目組合的答對率，組合難易不一，高低分組只能近似代表能力高低；②每題的作答人次會比作答組數少很多（約為 10／題庫題數），指標需要更多作答才穩定；③同一個學生可能做好幾組，這些作答組彼此不是獨立樣本，本系統也刻意不識別學生；④題目改版（版本指紋改變）後新舊版分開統計。'],
    ['資料', '不含姓名、班級、座號；Apps Script 取得不到送出者 IP。']
  ];
  sh.getRange(1, 1, lines.length, 2).setValues(lines);
}
