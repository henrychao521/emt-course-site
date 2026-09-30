/* 深淺色切換＋測驗；零外部相依 */
(function () {
  "use strict";
  var root = document.documentElement;

  function store(k, v) {
    try {
      if (v === undefined) return localStorage.getItem(k);
      if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v);
    } catch (e) { return null; }
    return null;
  }

  // ── 深淺色 ──
  var btn = document.getElementById("theme-btn");
  function current() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function label() {
    if (btn) btn.textContent = current() === "dark" ? "改成淺色" : "改成深色";
  }
  if (btn) {
    btn.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      store("emt-theme", next);
      label();
    });
    label();
  }


  // ── 測驗：從內嵌題庫依章節與難度平衡抽 10 題 ──
  var dataEl = document.getElementById("quiz-bank");
  var app = document.getElementById("quiz-app");
  var all = document.getElementById("bank-all");
  if (!dataEl || !app || !all) return;
  var BANK;
  try { BANK = JSON.parse(dataEl.textContent); } catch (e) { all.hidden = false; return; }
  var QS = BANK.questions, SRC = BANK.sources;
  var N = 10;
  var CH_QUOTA = { ch1: 2, ch2: 1, ch3: 2, ch4: 5 };
  var DIFF_TARGET = { 1: 3, 2: 4, 3: 3 };
  var TYPE_NAME = { single: "單選", tf: "是非", scenario: "情境判斷", order: "排序" };
  var DIFF_NAME = { 1: "基礎", 2: "進階", 3: "挑戰" };
  var list = document.getElementById("quiz-list");
  var out = document.getElementById("score-text");
  var metaEl = document.getElementById("quiz-meta");
  var round = 0, answered = 0, correct = 0, current = [], seen = {}, results = {};
  var rid = "", sent = false, identSent = false;

  // ── 作答紀錄：每完成一組送一次到老師的 Google 試算表（未設定網址就完全不送） ──
  // 作答紀錄只含題號、題目指紋、對錯、所選與正解代號；班級座號只在學生按「成果報告產生」時，
  // 另送一筆 identify（同一作答編號，每組只送第一次），排在該組作答紀錄之後。
  var CFG = {};
  try { CFG = JSON.parse((document.getElementById("quiz-config") || {}).textContent || "{}") || {}; } catch (e) { CFG = {}; }
  var SHEET_ENDPOINT = typeof CFG.SHEET_ENDPOINT === "string" ? CFG.SHEET_ENDPOINT : "";
  var SHEET_TOKEN = typeof CFG.SHEET_TOKEN === "string" ? CFG.SHEET_TOKEN : "";
  var QKEY = "emt-sheet-queue", QMAX = 50, flushing = false;
  function newRid() {
    try {
      var c = window.crypto || window.msCrypto, b = new Uint8Array(16), h = "";
      c.getRandomValues(b);
      for (var i = 0; i < b.length; i++) h += ("0" + b[i].toString(16)).slice(-2);
      return h;
    } catch (e) { return ""; }
  }
  function qRead() {
    try {
      var a = JSON.parse(localStorage.getItem(QKEY) || "[]");
      return Array.isArray(a) ? a.filter(function (x) { return typeof x === "string"; }) : [];
    } catch (e) { return []; }
  }
  function qWrite(a) {
    try {
      if (a.length) localStorage.setItem(QKEY, JSON.stringify(a.slice(-QMAX)));
      else localStorage.removeItem(QKEY);
    } catch (e) { /* 無痕視窗等情況存不了就算了 */ }
  }
  function post(body) {
    // no-cors＋text/plain：不觸發 CORS 預檢；回應讀不到，只要沒有網路錯誤就當作送達
    try {
      return fetch(SHEET_ENDPOINT, { method: "POST", mode: "no-cors",
        headers: { "Content-Type": "text/plain" }, body: body });
    } catch (e) { return Promise.reject(e); }
  }
  // 依序補送佇列；遇到失敗就停，留待下次開頁或恢復連線
  function flush() {
    if (!SHEET_ENDPOINT || flushing || !window.fetch) return;
    var q = qRead();
    if (!q.length) return;
    flushing = true;
    var body = q[0];
    post(body).then(function () {
      qWrite(qRead().filter(function (x) { return x !== body; }));
      flushing = false; flush();
    }, function () { flushing = false; });
  }
  function sendRound() {
    if (!SHEET_ENDPOINT || sent || !rid) return;
    sent = true;
    var items = current.map(function (q) {
      var r = results[q.id];
      return { q: q.id, h: q.h || "", t: q.type, ok: r.ok ? 1 : 0, a: r.code, k: r.key };
    });
    enqueue(JSON.stringify({ v: 1, token: SHEET_TOKEN, rid: rid, bank: String(BANK.version || ""), round: round, items: items }));
  }
  // 先進佇列再依序送：送到一半關掉頁面也不會遺失，identify 一定排在作答紀錄之後；伺服器端同一作答編號只收一次
  var direct = Promise.resolve();
  function enqueue(body) {
    var q = qRead();
    q.push(body); qWrite(q);
    if (qRead().indexOf(body) < 0) {  // 存不了佇列（無痕等）時直接依序送一次
      direct = direct.then(function () { return post(body); }).then(null, function () {});
      return;
    }
    flush();
  }
  function sendIdentify(cls, seat) {
    if (!SHEET_ENDPOINT || !sent || identSent || !rid) return;
    identSent = true;
    enqueue(JSON.stringify({ v: 1, type: "identify", token: SHEET_TOKEN, rid: rid, "class": cls, seat: seat }));
  }
  window.addEventListener("online", flush);

  // Fisher–Yates
  function shuffle(a) {
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function draw() {
    // 已出過的題目先避開；不足時才重用
    // 同一 variant_group（同一知識點的不同情境／題型變體）一輪最多出一題
    var pool = {}, picked = [], usedKp = {}, usedId = {}, usedVg = {};
    var need = {}; for (var d in DIFF_TARGET) need[d] = DIFF_TARGET[d];
    var typeCount = {};
    QS.forEach(function (q) { (pool[q.chapter] = pool[q.chapter] || []).push(q); });
    var slots = [];
    Object.keys(CH_QUOTA).forEach(function (ch) { for (var i = 0; i < CH_QUOTA[ch]; i++) slots.push(ch); });
    shuffle(slots);
    function score(q) {
      var s = Math.random();
      if (seen[q.id]) s -= 10;
      if (q.kp.some(function (k) { return usedKp[k]; })) s -= 5;
      s += (need[q.difficulty] || 0) > 0 ? 3 * need[q.difficulty] : -2;
      s -= (typeCount[q.type] || 0) * 0.8;
      return s;
    }
    function vgOf(q) { return q.variant_group || q.id; }
    function free(q) { return !usedId[q.id] && !usedVg[vgOf(q)]; }
    slots.forEach(function (ch) {
      var cand = (pool[ch] || []).filter(free);
      if (!cand.length) cand = QS.filter(free);
      if (!cand.length) cand = QS.filter(function (q) { return !usedId[q.id]; });
      var best = null, bs = -1e9;
      cand.forEach(function (q) { var s = score(q); if (s > bs) { bs = s; best = q; } });
      if (!best) return;
      picked.push(best); usedId[best.id] = 1; usedVg[vgOf(best)] = 1;
      best.kp.forEach(function (k) { usedKp[k] = 1; });
      need[best.difficulty] = (need[best.difficulty] || 0) - 1;
      typeCount[best.type] = (typeCount[best.type] || 0) + 1;
    });
    // 依章節排序，同章內隨機
    var order = { ch1: 1, ch2: 2, ch3: 3, ch4: 4 };
    picked.sort(function (a, b) { return order[a.chapter] - order[b.chapter]; });
    picked.forEach(function (q) { seen[q.id] = 1; });
    if (Object.keys(seen).length >= QS.length) seen = {};
    return picked;
  }

  function citeLinks(keys) {
    var p = el("p", "cites");
    keys.forEach(function (k) {
      var s = SRC[k]; if (!s) return;
      var a = el("a", "cite", s[0]);
      a.href = s[1]; a.target = "_blank"; a.rel = "noopener"; a.title = s[2];
      p.appendChild(a);
    });
    return p;
  }

  function finish(q, box, ok, chosen, code, key) {
    results[q.id] = { ok: ok, chosen: chosen, code: code, key: key };
    box.setAttribute("data-done", "1");
    box.setAttribute("data-result", ok ? "right" : "wrong");
    answered++; if (ok) correct++;
    var ex = box.querySelector(".explain");
    var verdict = el("p", "verdict " + (ok ? "ok" : "ng"), ok ? "答對了。" : "答錯了。");
    ex.insertBefore(verdict, ex.firstChild);
    ex.hidden = false;
    update();
    if (answered === current.length) sendRound();
  }

  function renderChoice(q, box) {
    var opts = q.type === "tf" ? q.options.slice() : shuffle(q.options.slice());
    var ol = el("ol", "opts");
    var btns = [];
    opts.forEach(function (o, i) {
      var li = el("li");
      var b = el("button", "opt", (q.type === "tf" ? "" : "ABCD".charAt(i) + ". ") + o);
      b.type = "button";
      b.setAttribute("data-v", o);
      b.addEventListener("click", function () {
        if (box.getAttribute("data-done")) return;
        btns.forEach(function (x) {
          x.disabled = true;
          var v = x.getAttribute("data-v");
          if (v === q.answer) { x.classList.add("right"); x.appendChild(el("span", "mark", "正解")); }
          else if (x === b) { x.classList.add("wrong"); x.appendChild(el("span", "mark", "你的選擇")); }
        });
        var L = "ABCDEF";
        finish(q, box, o === q.answer, o,
          q.type === "tf" ? o : L.charAt(q.options.indexOf(o)),
          q.type === "tf" ? q.answer : L.charAt(q.options.indexOf(q.answer)));
      });
      btns.push(b); li.appendChild(b); ol.appendChild(li);
    });
    box.appendChild(ol);
  }

  function renderOrder(q, box) {
    var items = q.items.slice();
    do { shuffle(items); } while (items.length > 1 && items.join("|") === q.items.join("|"));
    box.appendChild(el("p", "order-hint", "依序點選步驟（先點的是第 1 步）；點錯可按「重排」。"));
    var ol = el("ol", "opts order-opts");
    var seq = [], btns = [];
    var ctl = el("p", "order-ctl");
    var reset = el("button", "btn btn-ghost", "重排"); reset.type = "button";
    ctl.appendChild(reset);
    function paint() {
      btns.forEach(function (b) {
        var n = seq.indexOf(b.getAttribute("data-v"));
        var badge = b.querySelector(".num-badge");
        badge.textContent = n >= 0 ? String(n + 1) : "";
        b.classList.toggle("picked", n >= 0);
        b.setAttribute("aria-pressed", n >= 0 ? "true" : "false");
      });
    }
    items.forEach(function (it) {
      var li = el("li");
      var b = el("button", "opt order-opt"); b.type = "button";
      b.setAttribute("data-v", it);
      b.appendChild(el("span", "num-badge", ""));
      b.appendChild(document.createTextNode(it));
      b.addEventListener("click", function () {
        if (box.getAttribute("data-done") || seq.indexOf(it) >= 0) return;
        seq.push(it); paint();
        if (seq.length === q.items.length) {
          var ok = seq.join("|") === q.items.join("|");
          btns.forEach(function (x) {
            x.disabled = true;
            var v = x.getAttribute("data-v");
            x.classList.add(seq.indexOf(v) === q.items.indexOf(v) ? "right" : "wrong");
          });
          reset.disabled = true;
          var ans = el("ol", "order-answer");
          q.items.forEach(function (x) { ans.appendChild(el("li", null, x)); });
          var ex = box.querySelector(".explain");
          ex.insertBefore(ans, ex.firstChild);
          ex.insertBefore(el("p", "order-answer-h", "正確順序："), ans);
          finish(q, box, ok, seq.join(" → "),
            seq.map(function (v) { return q.items.indexOf(v) + 1; }).join(">"),
            q.items.map(function (v, i) { return i + 1; }).join(">"));
        }
      });
      btns.push(b); li.appendChild(b); ol.appendChild(li);
    });
    reset.addEventListener("click", function () { if (!box.getAttribute("data-done")) { seq = []; paint(); } });
    box.appendChild(ol); box.appendChild(ctl);
  }

  function render() {
    round++; answered = 0; correct = 0; results = {};
    rid = newRid(); sent = false; identSent = false;
    if (reportOut) { reportOut.innerHTML = ""; reportOut.hidden = true; }
    if (reportMsg) reportMsg.textContent = "";
    current = draw();
    list.innerHTML = "";
    current.forEach(function (q) {
      var box = el("div", "q");
      box.setAttribute("data-id", q.id);
      box.setAttribute("data-type", q.type);
      box.appendChild(el("p", "q-meta", TYPE_NAME[q.type] + "｜" + DIFF_NAME[q.difficulty]));
      box.appendChild(el("h3", null, q.stem));
      if (q.type === "order") renderOrder(q, box); else renderChoice(q, box);
      var ex = el("div", "explain"); ex.hidden = true;
      ex.appendChild(el("p", null, q.explain));
      ex.appendChild(citeLinks(q.sources));
      box.appendChild(ex);
      list.appendChild(box);
    });
    if (metaEl) metaEl.textContent = "第 " + round + " 組｜題庫共 " + QS.length + " 題，本組 " + current.length + " 題。";
    update();
  }

  function update() {
    if (!out) return;
    var t = "已作答 " + answered + " / " + current.length + " 題，答對 " + correct + " 題";
    if (current.length && answered === current.length) t += "｜本組完成，得分 " + Math.round(correct * 100 / current.length) + " 分";
    out.textContent = t;
  }


  // ---------- 成果報告（JPG，在瀏覽器內產生，不上傳） ----------
  var reportBtn = document.getElementById("report-make");
  var reportOut = document.getElementById("report-out");
  var reportMsg = document.getElementById("report-msg");
  var FONT = '"PingFang TC","Noto Sans TC","Microsoft JhengHei",sans-serif';
  function wrap(ctx, text, maxW) {
    var lines = [], line = "";
    String(text).split("").forEach(function (ch) {
      if (ch === "\n") { lines.push(line); line = ""; return; }
      // 避頭點：標點不放在行首，允許略為超出
      if (ctx.measureText(line + ch).width > maxW && line && "，。、；：！？）」』》,.;:!?)".indexOf(ch) < 0) { lines.push(line); line = ch; }
      else line += ch;
    });
    if (line) lines.push(line);
    return lines;
  }
  // 全形數字與英文字母轉半形；班級規則要和 Code.gs 的 CLASS_RE 相同
  function toHalf(t) {
    return t.replace(/[\uFF10-\uFF19\uFF21-\uFF3A\uFF41-\uFF5A\uFF0D]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0xFEE0); });
  }
  var CLASS_RE = /^(?!-)[0-9A-Za-z\u3400-\u9FFF\-]{1,10}$/;
  function makeReport() {
    var cls = toHalf((document.getElementById("report-class").value || "").trim());
    var seat = toHalf((document.getElementById("report-seat").value || "").trim());
    if (!cls || !seat) { reportMsg.textContent = "請先填寫班級與座號。"; return; }
    if (!CLASS_RE.test(cls)) { reportMsg.textContent = "班級只能填中文、英文字母、數字或 -（不可用 - 開頭），最多 10 個字。"; return; }
    if (!/^[0-9]{1,4}$/.test(seat)) { reportMsg.textContent = "座號請填 1 到 4 位數字。"; return; }
    var left = current.length - answered;
    if (left > 0) { reportMsg.textContent = "還有 " + left + " 題沒有作答，全部作答後才能產生成果報告。"; return; }
    reportMsg.textContent = "";
    var W = 1080, PAD = 64, CW = W - PAD * 2;
    var cv = document.createElement("canvas"), ctx = cv.getContext("2d");
    var rightQs = current.filter(function (q) { return results[q.id] && results[q.id].ok; });
    var wrongQs = current.filter(function (q) { return results[q.id] && !results[q.id].ok; });
    var now = new Date();
    var stamp = now.getFullYear() + "/" + (now.getMonth() + 1) + "/" + now.getDate() + " " +
      ("0" + now.getHours()).slice(-2) + ":" + ("0" + now.getMinutes()).slice(-2);
    var scoreN = Math.round(correct * 100 / current.length);
    // 先排版成指令，再依總高度畫
    var ops = [], y = PAD;
    function text(t, size, color, weight, indent, gap) {
      ctx.font = (weight || "normal") + " " + size + "px " + FONT;
      wrap(ctx, t, CW - (indent || 0)).forEach(function (ln) {
        ops.push({ t: ln, x: PAD + (indent || 0), y: y + size, size: size, color: color, weight: weight || "normal" });
        y += Math.round(size * 1.5);
      });
      y += gap || 0;
    }
    function rule(color) { ops.push({ rule: true, y: y, color: color }); y += 24; }
    text("從工場安全到 EMT-1｜小測驗成果報告", 40, "#16202a", "bold", 0, 8);
    text("班級：" + cls + "　座號：" + seat, 30, "#16202a", "bold", 0, 0);
    text("作答時間：" + stamp + "　第 " + round + " 組", 24, "#56616b", "normal", 0, 12);
    text("得分 " + scoreN + " 分（答對 " + correct + " / " + current.length + " 題）", 36, scoreN >= 60 ? "#1d6b3a" : "#a33a2a", "bold", 0, 8);
    rule("#c9d1d8");
    text("答錯的題目（" + wrongQs.length + " 題）", 30, "#a33a2a", "bold", 0, 6);
    if (!wrongQs.length) text("沒有答錯的題目。", 24, "#56616b", "normal", 0, 10);
    wrongQs.forEach(function (q, i) {
      var r = results[q.id];
      text((i + 1) + ". " + q.stem, 26, "#16202a", "bold", 0, 2);
      text("你的答案：" + r.chosen, 24, "#a33a2a", "normal", 28, 0);
      text("正確答案：" + (q.type === "order" ? q.items.join(" → ") : q.answer), 24, "#1d6b3a", "normal", 28, 0);
      text("解說：" + q.explain, 22, "#3e4850", "normal", 28, 16);
    });
    rule("#c9d1d8");
    text("答對的題目（" + rightQs.length + " 題）", 30, "#1d6b3a", "bold", 0, 6);
    if (!rightQs.length) text("這組沒有答對的題目，再抽一組試試看。", 24, "#56616b", "normal", 0, 10);
    rightQs.forEach(function (q, i) {
      text("✓ " + q.stem, 24, "#16202a", "normal", 0, 0);
      text("你的答案：" + results[q.id].chosen, 22, "#1d6b3a", "normal", 28, 8);
    });
    y += 8; rule("#c9d1d8");
    text("本報告由學生自行在瀏覽器產生，僅供學習紀錄。觀念測驗答對不代表會做，急救技能須經合格課程實作訓練。", 20, "#56616b", "normal", 0, 0);
    text("網站：henrychao521.github.io/emt-course-site", 20, "#56616b", "normal", 0, 0);
    var H = y + PAD - 16, scale = 1;
    cv.width = W * scale; cv.height = H * scale;
    ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "#a33a2a"; ctx.fillRect(0, 0, W, 12);
    ops.forEach(function (o) {
      if (o.rule) { ctx.fillStyle = o.color; ctx.fillRect(PAD, o.y, CW, 2); return; }
      ctx.font = o.weight + " " + o.size + "px " + FONT; ctx.fillStyle = o.color; ctx.textBaseline = "alphabetic";
      ctx.fillText(o.t, o.x, o.y);
    });
    var url = cv.toDataURL("image/jpeg", 0.92);
    var fname = "EMT小測驗成果報告_" + cls + "_" + seat + ".jpg";
    reportOut.innerHTML = "";
    var a = el("a", "btn", "下載成果報告（JPG）"); a.href = url; a.download = fname;
    var tip = el("p", "report-tip", "手機若無法直接下載，請長按下方圖片選「儲存影像」。");
    var img = document.createElement("img"); img.src = url; img.alt = "小測驗成果報告：班級 " + cls + "、座號 " + seat + "，得分 " + scoreN + " 分";
    img.className = "report-img";
    reportOut.appendChild(a); reportOut.appendChild(tip); reportOut.appendChild(img);
    reportOut.hidden = false;
    sendIdentify(cls, seat);
    reportOut.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  if (reportBtn) reportBtn.addEventListener("click", makeReport);

  var redraw = document.getElementById("quiz-redraw");
  if (redraw) redraw.addEventListener("click", function () {
    render();
    window.scrollTo(0, app.offsetTop - 20);
  });
  var pr = document.getElementById("bank-print");
  if (pr) pr.addEventListener("click", function () { window.print(); });
  var back = document.getElementById("back-to-quiz");
  if (back) back.addEventListener("click", function (e) {
    e.preventDefault();
    try { history.replaceState(null, "", location.pathname + location.search); } catch (x) { location.hash = ""; }
    route();
  });

  function route() {
    var teacher = location.hash === "#all";
    all.hidden = !teacher;
    root.classList.toggle("teacher-mode", teacher);
    app.hidden = teacher;
    if (!teacher && !current.length) render();
  }
  window.addEventListener("hashchange", route);
  route();
  flush();
})();
