// Apps Script 的最小假物件：SpreadsheetApp／LockService／ContentService／UrlFetchApp。
// 給 test_code_gs.js 與 send_test.py 共用。
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm"), assert = require("assert");
let FAKE_FETCH = () => ({ code: 404, body: "" });
function setFetch(fn) { FAKE_FETCH = fn; }
function makeFakes() {
  const sheets = {}, toasts = [], fetched = [];
  function Sheet(name) {
    this.name = name; this.data = []; this.frozen = 0;
  }
  Sheet.prototype.getLastRow = function () { return this.data.length; };
  Sheet.prototype.appendRow = function (row) { this.data.push(row.slice()); };
  Sheet.prototype.setFrozenRows = function (n) { this.frozen = n; };
  Sheet.prototype.clear = function () { this.data = []; };
  Sheet.prototype.insertColumnsAfter = function (after, n) {
    this.data.forEach(r => { while (r.length < after) r.push(""); r.splice(after, 0, ...Array(n).fill("")); });
  };
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
    toast: msg => { toasts.push(msg); },
    insertSheet: n => (sheets[n] = new Sheet(n)),
  };
  let locked = false;
  return {
    sheets, toasts, fetched,
    ctx: {
      UrlFetchApp: {
        fetch(url, opt) {
          fetched.push({ url, opt });
          const r = FAKE_FETCH(String(url).split("?")[0]);
          return { getResponseCode: () => r.code, getContentText: () => r.body };
        }
      },
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

module.exports = { makeFakes, load, setFetch };
