// Code.gs 離線模擬測試：把 SpreadsheetApp／LockService／ContentService 換成假物件，
// 測驗證、寫入、重複作答編號、分析指標（手算小例＋獨立實作對帳）。
// 用法：node tools/sheets/test_code_gs.js
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm"), assert = require("assert");

function makeFakes() {
  const sheets = {};
  function Sheet(name) {
    this.name = name; this.data = []; this.frozen = 0;
  }
  Sheet.prototype.getLastRow = function () { return this.data.length; };
  Sheet.prototype.appendRow = function (row) { this.data.push(row.slice()); };
  Sheet.prototype.setFrozenRows = function (n) { this.frozen = n; };
  Sheet.prototype.clear = function () { this.data = []; };
  Sheet.prototype.getDataRange = function () {
    const w = Math.max(0, ...this.data.map(r => r.length));
    return this.getRange(1, 1, this.data.length, w);
  };
  Sheet.prototype.getRange = function (r, c, nr, nc) {
    const sh = this;
    if (typeof r === "string") return { setNumberFormat() { return this; } };
    nr = nr || 1; nc = nc || 1;
    return {
      setNumberFormat() { return this; },
      getValues() {
        const out = [];
        for (let i = 0; i < nr; i++) {
          const row = sh.data[r - 1 + i] || [];
          const o = [];
          for (let j = 0; j < nc; j++) o.push(row[c - 1 + j] === undefined ? "" : row[c - 1 + j]);
          out.push(o);
        }
        return out;
      },
      setValues(v) {
        assert.strictEqual(v.length, nr, "setValues 列數不符");
        v.forEach((row, i) => {
          assert.strictEqual(row.length, nc, "setValues 欄數不符");
          const t = sh.data[r - 1 + i] || (sh.data[r - 1 + i] = []);
          row.forEach((x, j) => { t[c - 1 + j] = x; });
        });
        return this;
      }
    };
  };
  const ss = {
    getSheetByName: n => sheets[n] || null,
    insertSheet: n => (sheets[n] = new Sheet(n)),
  };
  let locked = false;
  return {
    sheets,
    ctx: {
      SpreadsheetApp: { getActiveSpreadsheet: () => ss, getUi: () => ({ createMenu() { return { addItem() { return this; }, addToUi() {} }; } }) },
      LockService: { getScriptLock: () => ({ tryLock() { if (locked) return false; locked = true; return true; }, releaseLock() { locked = false; } }) },
      ContentService: {
        MimeType: { JSON: "json" },
        createTextOutput: s => ({ body: s, setMimeType() { return this; } })
      },
      console,
    }
  };
}

function load(token) {
  const f = makeFakes();
  vm.createContext(f.ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "Code.gs"), "utf8"), f.ctx);
  f.ctx.CONFIG.TOKEN = token || "";
  f.post = body => JSON.parse(f.ctx.doPost({ postData: { contents: body } }).body);
  return f;
}

let pass = 0;
function ok(cond, msg) { assert.ok(cond, msg); pass++; }

const rid = () => [...Array(32)].map(() => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("");
function payload(over, itemsOver) {
  const items = [
    { q: "q001", h: "1a2b3c4d", t: "single", ok: 1, a: "B", k: "B" },
    { q: "q050", h: "00000000", t: "tf", ok: 0, a: "錯誤", k: "正確" },
    { q: "q090", h: "abcdef01", t: "order", ok: 0, a: "2>1>3>4", k: "1>2>3>4" },
  ];
  return Object.assign({ v: 1, token: "", rid: rid(), bank: "2026-09-29", round: 1, items: itemsOver || items }, over || {});
}

// ── 驗證與寫入 ──
{
  const f = load();
  const good = payload();
  let r = f.post(JSON.stringify(good));
  ok(r.ok === true && !r.dup, "正常資料應收下 " + JSON.stringify(r));
  const resp = f.sheets.responses.data, items = f.sheets.items.data;
  ok(resp.length === 2 && resp[0].length === 6 + 20 * 5, "responses 一列一組、106 欄");
  ok(resp[1][1] === good.rid && resp[1][2] === "2026-09-29" && resp[1][4] === 3 && resp[1][5] === 1, "responses 基本欄位");
  ok(resp[1][6] === "q001" && resp[1][9] === "B" && resp[1][16] === "q090" && resp[1][19] === "2>1>3>4" && resp[1][20] === "1>2>3>4", "responses 每題欄位");
  ok(resp[1][21] === "", "未用到的題位留空");
  ok(resp[1][0] instanceof Date || Object.prototype.toString.call(resp[1][0]) === "[object Date]", "時間戳由伺服器產生");
  ok(items.length === 4 && items[3][5] === "q090" && items[3][7] === "排序", "items 一列一題");
  // 重複作答編號
  r = f.post(JSON.stringify(good));
  ok(r.ok && r.dup && f.sheets.responses.data.length === 2 && f.sheets.items.data.length === 4, "同一作答編號只收一次");

  const bad = [
    ["", "empty"], ["{", "json"], ["[]", "shape"], ["x".repeat(9000), "too_long"],
    [JSON.stringify(payload({ cls: "228" })), "extra_field"],
    [JSON.stringify(payload({ v: 2 })), "version"],
    [JSON.stringify(payload({ rid: "ABC" })), "rid"],
    [JSON.stringify(payload({ rid: "g".repeat(32) })), "rid"],
    [JSON.stringify(payload({ bank: "<script>" })), "bank"],
    [JSON.stringify(payload({ round: 0 })), "round"],
    [JSON.stringify(payload({ round: 1.5 })), "round"],
    [JSON.stringify(payload({ items: [] })), "items"],
    [JSON.stringify(payload({}, Array.from({ length: 21 }, (_, i) => ({ q: "q" + String(i + 100).padStart(3, "0"), h: "00000000", t: "tf", ok: 1, a: "正確", k: "正確" })))), "items"],
    [JSON.stringify(payload({}, [{ q: "Q001", h: "00000000", t: "tf", ok: 1, a: "正確", k: "正確" }])), "qid"],
    [JSON.stringify(payload({}, [{ q: "q0001", h: "00000000", t: "tf", ok: 1, a: "正確", k: "正確" }])), "qid"],
    [JSON.stringify(payload({}, [{ q: "q001", h: "00000000", t: "tf", ok: 1, a: "正確", k: "正確" }, { q: "q001", h: "00000000", t: "tf", ok: 1, a: "正確", k: "正確" }])), "qid_dup"],
    [JSON.stringify(payload({}, [{ q: "q001", h: "xyz", t: "tf", ok: 1, a: "正確", k: "正確" }])), "hash"],
    [JSON.stringify(payload({}, [{ q: "q001", h: "00000000", t: "essay", ok: 1, a: "正確", k: "正確" }])), "type"],
    [JSON.stringify(payload({}, [{ q: "q001", h: "00000000", t: "tf", ok: true, a: "正確", k: "正確" }])), "ok"],
    [JSON.stringify(payload({}, [{ q: "q001", h: "00000000", t: "single", ok: 0, a: "我的名字", k: "A" }])), "answer"],
    [JSON.stringify(payload({}, [{ q: "q001", h: "00000000", t: "single", ok: 0, a: "Z", k: "A" }])), "answer"],
    [JSON.stringify(payload({}, [{ q: "q001", h: "00000000", t: "single", ok: 1, a: "A", k: "B" }])), "ok_mismatch"],
    [JSON.stringify(payload({}, [{ q: "q001", h: "00000000", t: "single", ok: 0, a: "正確", k: "正確" }])), "answer_type"],
    [JSON.stringify(payload({}, [{ q: "q001", h: "00000000", t: "order", ok: 0, a: "2>1", k: "1>2>3" }])), "answer_len"],
    [JSON.stringify(payload({}, [{ q: "q001", h: "00000000", t: "tf", ok: 1, a: "正確", k: "正確", seat: "12" }])), "item_extra_field"],
  ];
  bad.forEach(([body, err]) => {
    const r2 = f.post(body);
    ok(r2.ok === false && r2.error === err, `應拒收（${err}），實得 ${JSON.stringify(r2)}`);
  });
  ok(f.sheets.responses.data.length === 2, "拒收的資料沒有寫入");
  // doPost 沒有 postData
  ok(JSON.parse(f.ctx.doPost({}).body).error === "empty", "無內容");
}
// 口令
{
  const f = load("s3cret");
  ok(f.post(JSON.stringify(payload({ token: "" }))).error === "token", "口令錯誤要拒收");
  ok(f.post(JSON.stringify(payload({ token: "s3cret" }))).ok === true, "口令正確收下");
}
// WRITE_ITEMS 關閉
{
  const f = load(); f.ctx.CONFIG.WRITE_ITEMS = false;
  f.post(JSON.stringify(payload()));
  ok(!f.sheets.items && f.sheets.responses.data.length === 2, "關閉 items 時只寫 responses");
}

// ── 分析：手算小例 ──
{
  const f = load();
  f.ctx.CONFIG.MIN_N = 1;
  const pat = [[1, 1, 1], [1, 1, 0], [0, 1, 0], [0, 0, 0]];
  const ids = ["q001", "q002", "q003"];
  pat.forEach((p, i) => {
    const items = p.map((v, j) => ({ q: ids[j], h: "0000000" + j, t: "single", ok: v, a: v ? "A" : (j === 0 && i === 3 ? "C" : "B"), k: "A" }));
    const r = f.post(JSON.stringify(payload({ rid: String(i + 1).repeat(32).slice(0, 32).replace(/[^0-9a-f]/g, "a") }, items)));
    assert.ok(r.ok, JSON.stringify(r));
  });
  const res = f.ctx.analyze();
  ok(res.responses === 4 && res.items === 3, "analyze 回傳筆數");
  const st = f.sheets.item_stats.data, H = st[0];
  const row = id => { const r = st.find(x => x[0] === id); return Object.fromEntries(H.map((h, i) => [h, r[i]])); };
  const a = row("q001");
  ok(a["作答人次"] === 4 && a["答對率p"] === 0.5 && a["高低分組各幾人"] === 1, "q001 p＝0.5、分組 1 人");
  ok(a["鑑別度D"] === 1 && a["高分組答對率"] === 1 && a["低分組答對率"] === 0, "q001 D＝1");
  ok(a["點二系列相關"] === 0.707, "q001 rpb＝0.707（手算 0.5/√0.5），實得 " + a["點二系列相關"]);
  ok(a["選項分布（全體）"] === "A＊ 2（50%）｜B 1（25%）｜C 1（25%）", "q001 選項分布：" + a["選項分布（全體）"]);
  ok(a["正解"] === "A" && a["題型"] === "選擇", "q001 正解與題型");
  const b = row("q002");
  // q002：ok [1,1,1,0]，rest [1,.5,0,0]；上 r1=1 下 r4=0 → D=1；rpb 手算：
  // ok 偏差 .25,.25,.25,-.75；rest 平均 .375 偏差 .625,.125,-.375,-.375；sxy=.15625+.03125-.09375+.28125=.375
  // sxx=.75；syy=.390625+.015625+.140625+.140625=.6875 → .375/√(.75×.6875)=.5222
  ok(b["答對率p"] === 0.75 && b["鑑別度D"] === 1 && b["點二系列相關"] === 0.522, "q002 指標，實得 rpb " + b["點二系列相關"]);
  ok(f.sheets["item_stats_說明"].data.length >= 8, "說明頁");
  f.ctx.CONFIG.MIN_N = 30; f.ctx.analyze();
  ok(f.sheets.item_stats.data[1][15].indexOf("樣本不足") === 0, "人次 <30 標示樣本不足");
  ok(f.sheets.item_stats.data.length === 4, "重算會清掉舊表");
}

// ── 分析：隨機資料 vs 獨立實作 ──
{
  const f = load(); f.ctx.CONFIG.MIN_N = 30;
  let seed = 12345; const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
  const bankIds = Array.from({ length: 30 }, (_, i) => "q" + String(i + 1).padStart(3, "0"));
  const all = [];
  for (let s = 0; s < 400; s++) {
    const ability = rnd();
    const pick = bankIds.slice().sort(() => rnd() - .5).slice(0, 10);
    const items = pick.map(q => {
      const diff = parseInt(q.slice(1), 10) / 30;
      const v = rnd() < 0.2 + 0.7 * ability * (1.2 - diff) ? 1 : 0;
      const a = v ? "A" : "BCD"[Math.floor(rnd() * 3)];
      return { q, h: "12345678", t: "single", ok: v, a, k: "A" };
    });
    const id = rid();
    all.push({ rid: id, items });
    assert.ok(f.post(JSON.stringify(payload({ rid: id }, items))).ok);
  }
  f.ctx.analyze();
  const st = f.sheets.item_stats.data, H = st[0];
  // 獨立實作
  function indep(q) {
    const rows = [];
    all.forEach(r => {
      const tot = r.items.filter(x => x.ok).length;
      const it = r.items.find(x => x.q === q); if (!it) return;
      rows.push({ rid: r.rid, ok: it.ok, total: tot / r.items.length, rest: (tot - it.ok) / (r.items.length - 1) });
    });
    const n = rows.length, g = Math.round(n * 0.27);
    rows.sort((x, y) => (y.total - x.total) || x.rid.localeCompare(y.rid));
    const avg = a => a.reduce((s, x) => s + x, 0) / a.length;
    const D = avg(rows.slice(0, g).map(x => x.ok)) - avg(rows.slice(n - g).map(x => x.ok));
    const X = rows.map(x => x.ok), Y = rows.map(x => x.rest), mx = avg(X), my = avg(Y);
    let sxy = 0, sxx = 0, syy = 0;
    X.forEach((x, i) => { sxy += (x - mx) * (Y[i] - my); sxx += (x - mx) ** 2; syy += (Y[i] - my) ** 2; });
    return { n, p: avg(X), D, rpb: sxy / Math.sqrt(sxx * syy) };
  }
  let checked = 0, maxErr = 0;
  st.slice(1).forEach(r => {
    const o = Object.fromEntries(H.map((h, i) => [h, r[i]]));
    const e = indep(o["題號"]);
    assert.strictEqual(o["作答人次"], e.n);
    [["答對率p", e.p], ["鑑別度D", e.D], ["點二系列相關", e.rpb]].forEach(([k, v]) => {
      const d = Math.abs(o[k] - v); maxErr = Math.max(maxErr, d);
      assert.ok(d <= 0.0005 + 1e-9, `${o["題號"]} ${k}：${o[k]} vs 獨立實作 ${v}`);
    });
    checked++;
  });
  ok(checked === 30, "30 題全部對帳");
  console.log(`隨機 400 組 × 10 題（題庫 30 題）對帳：最大誤差 ${maxErr.toFixed(5)}（四捨五入到小數三位）`);
  const easy = st.find(r => r[0] === "q001"), hard = st.find(r => r[0] === "q030");
  console.log("q001", easy.slice(3, 11).join(" / "), "｜", easy[15]);
  console.log("q030", hard.slice(3, 11).join(" / "), "｜", hard[15]);
}
console.log(`Code.gs 模擬測試通過 ${pass} 項`);
