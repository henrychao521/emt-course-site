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
  var round = 0, answered = 0, correct = 0, current = [], seen = {};

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
    var pool = {}, picked = [], usedKp = {}, usedId = {};
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
    slots.forEach(function (ch) {
      var cand = (pool[ch] || []).filter(function (q) { return !usedId[q.id]; });
      if (!cand.length) cand = QS.filter(function (q) { return !usedId[q.id]; });
      var best = null, bs = -1e9;
      cand.forEach(function (q) { var s = score(q); if (s > bs) { bs = s; best = q; } });
      if (!best) return;
      picked.push(best); usedId[best.id] = 1;
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

  function finish(q, box, ok) {
    box.setAttribute("data-done", "1");
    box.setAttribute("data-result", ok ? "right" : "wrong");
    answered++; if (ok) correct++;
    var ex = box.querySelector(".explain");
    var verdict = el("p", "verdict " + (ok ? "ok" : "ng"), ok ? "答對了。" : "答錯了。");
    ex.insertBefore(verdict, ex.firstChild);
    ex.hidden = false;
    update();
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
        finish(q, box, o === q.answer);
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
          finish(q, box, ok);
        }
      });
      btns.push(b); li.appendChild(b); ol.appendChild(li);
    });
    reset.addEventListener("click", function () { if (!box.getAttribute("data-done")) { seq = []; paint(); } });
    box.appendChild(ol); box.appendChild(ctl);
  }

  function render() {
    round++; answered = 0; correct = 0;
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
})();
