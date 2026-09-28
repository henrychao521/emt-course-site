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

  // ── 測驗 ──
  var quiz = document.querySelector(".quiz");
  if (!quiz) return;
  var qs = quiz.querySelectorAll(".q");
  var total = qs.length, answered = 0, correct = 0;
  var out = document.getElementById("score-text");

  function update() {
    if (out) out.textContent = "已作答 " + answered + " / " + total + " 題，答對 " + correct + " 題";
  }

  Array.prototype.forEach.call(qs, function (q) {
    var ans = q.getAttribute("data-answer");
    var opts = q.querySelectorAll(".opt");
    var ex = q.querySelector(".explain");
    Array.prototype.forEach.call(opts, function (o) {
      o.addEventListener("click", function () {
        if (q.getAttribute("data-done")) return;
        q.setAttribute("data-done", "1");
        answered++;
        var pick = o.getAttribute("data-k");
        Array.prototype.forEach.call(opts, function (x) {
          x.disabled = true;
          var k = x.getAttribute("data-k");
          if (k === ans) {
            x.classList.add("right");
            x.insertAdjacentHTML("beforeend", '<span class="mark">正解</span>');
          } else if (k === pick) {
            x.classList.add("wrong");
            x.insertAdjacentHTML("beforeend", '<span class="mark">你的選擇</span>');
          }
        });
        if (pick === ans) correct++;
        if (ex) ex.hidden = false;
        update();
      });
    });
  });

  var reset = document.getElementById("quiz-reset");
  if (reset) {
    reset.addEventListener("click", function () {
      Array.prototype.forEach.call(qs, function (q) {
        q.removeAttribute("data-done");
        var ex = q.querySelector(".explain");
        if (ex) ex.hidden = true;
        Array.prototype.forEach.call(q.querySelectorAll(".opt"), function (x) {
          x.disabled = false;
          x.classList.remove("right", "wrong");
          var m = x.querySelector(".mark");
          if (m) m.remove();
        });
      });
      answered = 0; correct = 0; update();
      window.scrollTo(0, quiz.offsetTop - 20);
    });
  }
  update();
})();
