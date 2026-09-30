// Code.gs 離線模擬測試：把 SpreadsheetApp／LockService／ContentService 換成假物件，
// 測驗證、寫入、重複作答編號、分析指標（手算小例＋獨立實作對帳）。
// 用法：node tools/sheets/test_code_gs.js
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm"), assert = require("assert");

const { load, setFetch } = require("./fake_gas.js");
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
  ok(resp.length === 2 && resp[0].length === 8 + 20 * 5, "responses 一列一組、108 欄");
  ok(resp[0][6] === "班級" && resp[0][7] === "座號" && resp[1][6] === "" && resp[1][7] === "", "班級座號欄預設空白");
  ok(resp[1][1] === good.rid && resp[1][2] === "2026-09-29" && resp[1][4] === 3 && resp[1][5] === 1, "responses 基本欄位");
  ok(resp[1][8] === "q001" && resp[1][11] === "B" && resp[1][18] === "q090" && resp[1][21] === "2>1>3>4" && resp[1][22] === "1>2>3>4", "responses 每題欄位");
  ok(resp[1][23] === "", "未用到的題位留空");
  ok(resp[1][0] instanceof Date || Object.prototype.toString.call(resp[1][0]) === "[object Date]", "時間戳由伺服器產生");
  ok(items.length === 4 && items[0][4] === "班級" && items[3][7] === "q090" && items[3][9] === "排序" && items[3][4] === "", "items 一列一題");
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
  ok(a["選項分布（全體）"] === "A＊：2（50%）｜B：1（25%）｜C：1（25%）", "q001 選項分布：" + a["選項分布（全體）"]);
  ok(a["正解"] === "A" && a["題型"] === "選擇", "q001 正解與題型");
  const b = row("q002");
  // q002：ok [1,1,1,0]，rest [1,.5,0,0]；上 r1=1 下 r4=0 → D=1；rpb 手算：
  // ok 偏差 .25,.25,.25,-.75；rest 平均 .375 偏差 .625,.125,-.375,-.375；sxy=.15625+.03125-.09375+.28125=.375
  // sxx=.75；syy=.390625+.015625+.140625+.140625=.6875 → .375/√(.75×.6875)=.5222
  ok(b["答對率p"] === 0.75 && b["鑑別度D"] === 1 && b["點二系列相關"] === 0.522, "q002 指標，實得 rpb " + b["點二系列相關"]);
  ok(f.sheets["item_stats_說明"].data.length >= 8, "說明頁");
  f.ctx.CONFIG.MIN_N = 30; f.ctx.analyze();
  ok(f.sheets.item_stats.data[1][16].indexOf("樣本不足") === 0, "人次 <30 標示樣本不足");
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
  console.log("q001", easy.slice(4, 12).join(" / "), "｜", easy[16]);
  console.log("q030", hard.slice(4, 12).join(" / "), "｜", hard[16]);
}
// ── identify：班級座號補進同一作答編號 ──
{
  const f = load();
  const r1 = payload(), r2 = payload();
  f.post(JSON.stringify(r1)); f.post(JSON.stringify(r2));
  const ident = (rid, cls, seat, extra) => JSON.stringify(Object.assign({ v: 1, type: "identify", token: "", rid, class: cls, seat }, extra || {}));
  let r = f.post(ident(r1.rid, "228", "07"));
  ok(r.ok === true && !r.dup, "identify 收下 " + JSON.stringify(r));
  const R = f.sheets.responses.data, I = f.sheets.items.data;
  ok(R[1][6] === "228" && R[1][7] === "07", "responses 補上班級座號（座號保留前導 0）");
  ok(R[2][6] === "" && R[2][7] === "", "沒送 identify 的組維持空白");
  ok(I.slice(1).filter(x => x[1] === r1.rid).every(x => x[4] === "228" && x[5] === "07"), "items 同一作答編號各列都補上");
  ok(I.slice(1).filter(x => x[1] === r2.rid).every(x => x[4] === "" && x[5] === ""), "items 其他作答編號不受影響");
  r = f.post(ident(r1.rid, "229", "8"));
  ok(r.ok && r.dup && R[1][6] === "228" && R[1][7] === "07", "同一作答編號第二次 identify 不覆寫");
  ok(f.post(ident("f".repeat(32), "228", "1")).error === "no_rid", "找不到作答編號要拒收");
  [["", "class"], ["12345678901", "class"], ["-228", "class"], ["=1+1", "class"], ["2 28", "class"], ["<b>", "class"],
   ["高一3班", null], ["A-12", null]].forEach(([c, err]) => {
    const x = f.post(ident(r2.rid, c, "5"));
    if (err) ok(x.ok === false && x.error === err, `班級 ${JSON.stringify(c)} 應拒收，實得 ${JSON.stringify(x)}`);
    else ok(x.ok === true, `班級 ${JSON.stringify(c)} 應收下`);
  });
  ok(R[2][6] === "高一3班" && R[2][7] === "5", "第一筆合格的 identify 生效、之後的（A-12）不覆寫");
  const f2 = load(); const rr = payload(); f2.post(JSON.stringify(rr));
  [["", "seat"], ["12345", "seat"], ["1a", "seat"], ["１２", "seat"], [12, "seat"]].forEach(([s2, err]) => {
    const x = f2.post(JSON.stringify({ v: 1, type: "identify", token: "", rid: rr.rid, class: "228", seat: s2 }));
    ok(x.ok === false && x.error === err, `座號 ${JSON.stringify(s2)} 應拒收，實得 ${JSON.stringify(x)}`);
  });
  ok(f2.post(ident(rr.rid, "228", "5", { name: "王小明" })).error === "extra_field", "identify 多餘欄位拒收");
  ok(f2.post(JSON.stringify({ v: 1, type: "hack", rid: rr.rid })).error === "type", "未知 type 拒收");
  ok(f2.post(ident(rr.rid, "高一3班", "5")).ok === true && f2.sheets.responses.data[1][6] === "高一3班", "中文班級可收");
  const f3 = load("pw"); const r3 = payload({ token: "pw" }); f3.post(JSON.stringify(r3));
  ok(f3.post(ident(r3.rid, "228", "1")).error === "token", "identify 也檢查口令");
  ok(f3.post(ident(r3.rid, "228", "1", { token: "pw" })).ok === true, "identify 口令正確收下");
  // 分析：有班級座號的組數
  const res = f.ctx.analyze();
  ok(res.identified === 2 && res.responses === 2, "analyze 統計有班級座號的組數");
}
// ── 第 1 版工作表遷移：沒有班級座號欄 → 插入兩欄，既有資料右移 ──
{
  const f = load();
  const old = ["時間戳", "作答編號", "題庫版本", "第幾組", "題數", "答對數"];
  for (let i = 1; i <= 20; i++) ["題號", "版本", "對錯", "所選", "正解"].forEach(x => old.push(`題${i}_${x}`));
  const oldRid = "a".repeat(32);
  const oldRow = [new Date(), oldRid, "2026-09-29", 1, 1, 1, "q001", "0000000a", 1, "A", "A"].concat(Array(95).fill(""));
  const rs = f.ctx.SpreadsheetApp.getActiveSpreadsheet().insertSheet("responses");
  rs.data = [old, oldRow];
  const is = f.ctx.SpreadsheetApp.getActiveSpreadsheet().insertSheet("items");
  is.data = [["時間戳", "作答編號", "題庫版本", "第幾組", "題序", "題號", "版本", "題型", "對錯", "所選", "正解"],
             [new Date(), oldRid, "2026-09-29", 1, 1, "q001", "0000000a", "單選", 1, "A", "A"]];
  const nw = payload(); f.post(JSON.stringify(nw));
  ok(rs.data[0][6] === "班級" && rs.data[0][8] === "題1_題號" && rs.data[1][8] === "q001" && rs.data[1][6] === "", "responses 舊資料右移兩欄");
  ok(rs.data[2][8] === "q001" && rs.data[2].length === 108, "遷移後新資料對齊");
  ok(is.data[0][4] === "班級" && is.data[1][7] === "q001" && is.data[2][7] === "q001", "items 遷移");
  ok(f.post(JSON.stringify({ v: 1, type: "identify", token: "", rid: oldRid, class: "301", seat: "3" })).ok && rs.data[1][6] === "301" && is.data[1][4] === "301", "舊資料也能補班級座號");
  const res = f.ctx.analyze();
  ok(res.responses === 2, "遷移後 analyze 可讀新舊資料");
  f.post(JSON.stringify(payload()));
  ok(rs.data[0].filter(x => x === "班級").length === 1, "遷移只做一次");
}
// ── importBank ＋ analyze 帶題幹、選項文字、版本不符 ──
{
  const f = load(); f.ctx.CONFIG.MIN_N = 1;
  const idx = { version: "2026-09-30", count: 3, questions: [
    { id: "q001", h: "11111111", type: "single", chapter: "ch1", difficulty: 1, stem: "EMT-1 訓練課程總時數是多少？",
      options: [{ code: "A", text: "24 小時" }, { code: "B", text: "56 小時，分七個模組並且有實作訓練" }, { code: "C", text: "336 小時" }], answer: "B" },
    { id: "q002", h: "22222222", type: "tf", chapter: "ch4", difficulty: 2, stem: "燙傷要沖冷水。", options: [{ code: "正確", text: "正確" }, { code: "錯誤", text: "錯誤" }], answer: "正確" },
    { id: "q003", h: "33333333", type: "order", chapter: "ch4", difficulty: 3, stem: "排出順序", options: [], steps: ["沖", "脫", "泡", "蓋", "送"], answer: "1>2>3>4>5" },
  ] };
  setFetch(url => url.endsWith("/assets/quiz-bank-index.json") ? { code: 200, body: JSON.stringify(idx) } : { code: 404, body: "" });
  let r = f.ctx.importBank();
  ok(r.count === 3 && r.version === "2026-09-30", "importBank 回傳");
  ok(f.fetched[0].url === "https://henrychao521.github.io/emt-course-site/assets/quiz-bank-index.json", "importBank 抓正式網址");
  const B = f.sheets["題庫"].data;
  ok(B.length === 4 && B[0][0] === "題號" && B[1][6] === "B" && B[1][8] === "56 小時，分七個模組並且有實作訓練" && B[3][13] === "1. 沖\n2. 脫\n3. 泡\n4. 蓋\n5. 送", "題庫工作表內容");
  ok(f.toasts.length === 1 && f.toasts[0].indexOf("3 題") > 0, "匯入完成提示");
  idx.questions = idx.questions.slice(0, 2); idx.count = 2;
  f.ctx.importBank();
  ok(f.sheets["題庫"].data.length === 3, "重新匯入整張覆寫");
  setFetch(() => ({ code: 500, body: "" }));
  let threw = false; try { f.ctx.importBank(); } catch (e) { threw = /HTTP 500/.test(e.message); }
  ok(threw && f.sheets["題庫"].data.length === 3, "下載失敗會報錯且不動原表");
  setFetch(() => ({ code: 200, body: JSON.stringify({ questions: [{ id: "x1", h: "zz" }] }) }));
  threw = false; try { f.ctx.importBank(); } catch (e) { threw = true; }
  ok(threw && f.sheets["題庫"].data.length === 3, "格式不對會報錯且不動原表");
  // 作答：q001 現行版、q002 舊版指紋、q009 題庫沒有
  const mk = (a, ok1) => [{ q: "q001", h: "11111111", t: "single", ok: ok1, a, k: "B" },
                         { q: "q002", h: "2222aaaa", t: "tf", ok: 1, a: "正確", k: "正確" },
                         { q: "q009", h: "99999999", t: "single", ok: 1, a: "A", k: "A" }];
  f.post(JSON.stringify(payload({}, mk("B", 1)))); f.post(JSON.stringify(payload({}, mk("A", 0)))); f.post(JSON.stringify(payload({}, mk("B", 1))));
  f.ctx.analyze();
  const st = f.sheets.item_stats.data, H = st[0];
  const row = id => { const x = st.find(y => y[0] === id); return Object.fromEntries(H.map((h, i) => [h, x[i]])); };
  const a = row("q001"), b = row("q002"), c = row("q009");
  ok(H[2] === "題幹" && a["題幹"] === "EMT-1 訓練課程總時數是多少？" && a["題型"] === "單選", "item_stats 帶題幹與題型");
  ok(a["選項分布（全體）"] === "A（24 小時）：1（33%）｜B＊（56 小時，分七個模組並…）：2（67%）｜C（336 小時）：0（0%）", "選項文字前 12 字：" + a["選項分布（全體）"]);
  ok(b["題幹"] === "（現行版）燙傷要沖冷水。" && b["提示"].indexOf("題目已修改，舊版作答") === 0, "版本不符標示：" + b["提示"]);
  ok(b["選項分布（全體）"] === "正確＊：3（100%）", "是非題分布");
  ok(c["題幹"] === "" && c["提示"].indexOf("題庫中找不到這個題號") === 0, "題庫沒有的題號");
  ok(f.sheets["item_stats_說明"].data.some(x => String(x[1]).indexOf("已匯入 2 題") === 0), "說明頁記錄題庫匯入");
}
// ── 用網站 build 出來的真實題庫索引跑一次 importBank ──
{
  const real = path.join(__dirname, "..", "..", "assets", "quiz-bank-index.json");
  if (fs.existsSync(real)) {
    const f = load();
    const txt = fs.readFileSync(real, "utf8");
    setFetch(() => ({ code: 200, body: txt }));
    const r = f.ctx.importBank(), n = JSON.parse(txt).questions.length;
    ok(r.count === n && f.sheets["題庫"].data.length === n + 1, `真實題庫索引匯入 ${n} 題`);
  }
}
console.log(`Code.gs 模擬測試通過 ${pass} 項`);
