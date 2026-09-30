#!/usr/bin/env python3
"""作答紀錄送出端對端測試：本機假 endpoint 代替 Apps Script，用 Playwright 實際作答。
**絕不連老師的正式網址**：測試用的網站複本以環境變數把 SHEET_ENDPOINT 改成本機假 endpoint，
所有瀏覽器分頁都擋掉 script.google.com，只要出現一個對它的請求就判定失敗。

1. 有設定網址：作答 3 組（第 1、3 組產生成果報告，第 1 組還改座號再產生一次；第 2 組不產生）
   → 每組作答紀錄剛好送一次、內容與畫面一致、不含班級座號；identify 只在產生報告時送、每組一次、排在作答紀錄之後。
2. 離線：完成一組並產生報告 → 作答紀錄與 identify 依序進佇列；恢復連線後依序補送。
3. 送出失敗（連線被擋）→ 重新開頁補送；佇列已有 50 筆 → 維持上限 50、保留最新。
4. 班級座號格式不對時不產生報告、不送 identify。
5. SHEET_ENDPOINT 空字串 → 完全不發請求、沒有錯誤、不顯示作答紀錄說明。
6. 收到的全部資料依到達順序交給 Code.gs（假 SpreadsheetApp）跑 doPost，檢查試算表結果。
用法：python3 tools/sheets/send_test.py
"""
import http.server
import json
import os
import random
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
RECV = []          # 假 endpoint 收到的 body（依到達順序）
GOOGLE = []        # 任何對 script.google.com 的請求（應為 0）
errors = []
CLS, SEAT = "測試班", "37"


def check(cond, msg):
    if not cond:
        errors.append(msg)
    return cond


class Endpoint(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8")
        RECV.append({"path": self.path, "ctype": self.headers.get("Content-Type"), "body": body})
        # 模擬 Apps Script：POST /exec 回 302 轉到另一個網址
        self.send_response(302)
        self.send_header("Location", "/echo")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_OPTIONS(self):  # 不該出現（text/plain 不會預檢）
        RECV.append({"path": self.path, "preflight": True, "body": ""})
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(handler, directory=None):
    h = partial(handler, directory=str(directory)) if directory else handler
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), h)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def build_copy(tmp, name, endpoint):
    site = tmp / name
    shutil.copytree(ROOT, site, ignore=shutil.ignore_patterns(".git", "docs", "__pycache__", "*.pyc"))
    env = dict(os.environ, EMT_SHEET_ENDPOINT=endpoint, EMT_SHEET_TOKEN="test-token" if endpoint else "")
    subprocess.run([sys.executable, str(site / "tools" / "build.py")], check=True, env=env, capture_output=True)
    cfg = json.loads(re.search(r'<script type="application/json" id="quiz-config">(.*?)</script>',
                               (site / "quiz.html").read_text(encoding="utf-8")).group(1))
    if cfg["SHEET_ENDPOINT"] != endpoint:
        raise SystemExit(f"測試複本的 SHEET_ENDPOINT 不是預期的 {endpoint!r}：{cfg}，中止以免送到正式網址")
    return site


def guard(ctx):
    """擋掉所有對 Google Apps Script 的請求並記錄。"""
    def block(route):
        GOOGLE.append(route.request.url)
        route.abort()
    ctx.route(re.compile(r"https?://([a-z0-9-]+\.)*(script\.google\.com|googleusercontent\.com)/"), block)


def answer_round(pg, bank, rng):
    """把目前這組全部作答，回傳 (ids, {qid: (ok, code, key, h, type)})（依網站應送出的代號規則自行推算）。"""
    Q = {q["id"]: q for q in bank["questions"]}
    ids = pg.eval_on_selector_all("#quiz-list .q", "els => els.map(e => e.dataset.id)")
    exp = {}
    for qid in ids:
        q = Q[qid]
        box = pg.locator(f'#quiz-list .q[data-id="{qid}"]')
        if q["type"] == "order":
            seq = list(q["items"]) if rng.random() < .5 else rng.sample(q["items"], len(q["items"]))
            for t in seq:
                box.locator(f'.order-opt[data-v="{t}"]').click()
            code = ">".join(str(q["items"].index(t) + 1) for t in seq)
            key = ">".join(str(i + 1) for i in range(len(q["items"])))
        else:
            texts = box.locator(".opt").evaluate_all("els => els.map(e => e.dataset.v)")
            pick = q["answer"] if rng.random() < .5 else rng.choice(texts)
            box.locator(f'.opt[data-v="{pick}"]').click()
            if q["type"] == "tf":
                code, key = pick, q["answer"]
            else:
                code, key = "ABCDEF"[q["options"].index(pick)], "ABCDEF"[q["options"].index(q["answer"])]
        ok = box.get_attribute("data-result") == "right"
        check(ok == (code == key), f"{qid} 畫面對錯與代號不一致")
        exp[qid] = (1 if ok else 0, code, key, q["h"], q["type"])
    return ids, exp


def check_record(body, ids, exp, round_no, bank):
    d = json.loads(body)
    check(set(d) == {"v", "token", "rid", "bank", "round", "items"}, f"作答紀錄頂層欄位不對：{sorted(d)}")
    check(d["v"] == 1 and d["token"] == "test-token" and d["bank"] == bank["version"], "v／token／bank 不對")
    check(re.fullmatch(r"[0-9a-f]{32}", d["rid"]) is not None, f"作答編號格式 {d['rid']}")
    check(d["round"] == round_no, f"第幾組 {d['round']} ≠ {round_no}")
    check([it["q"] for it in d["items"]] == ids, "題號順序和畫面不同")
    for it in d["items"]:
        ok, code, key, h, t = exp[it["q"]]
        check(set(it) == {"q", "h", "t", "ok", "a", "k"}, f"{it['q']} 欄位 {sorted(it)}")
        check((it["ok"], it["a"], it["k"], it["h"], it["t"]) == (ok, code, key, h, t),
              f"{it['q']} 送出 {it} ≠ 預期 {(ok, code, key, h, t)}")
    # 作答紀錄本身不能含班級座號
    check(CLS not in body, "作答紀錄含班級字串")
    vals = [str(v) for v in d.values()] + [str(v) for it in d["items"] for v in it.values()]
    check(SEAT not in vals, "作答紀錄某個欄位值等於座號")
    for w in ("class", "seat", "班級", "座號"):
        check(w not in body, f"作答紀錄含 {w}")
    return d["rid"]


def check_ident(body, rid, cls=CLS, seat=SEAT):
    d = json.loads(body)
    check(d == {"v": 1, "type": "identify", "token": "test-token", "rid": rid, "class": cls, "seat": seat},
          f"identify 內容不對：{d}（預期 rid {rid}、{cls}／{seat}）")


def kind(x):
    return "identify" if json.loads(x["body"]).get("type") == "identify" else "record"


def main():
    rng = random.Random(11)
    ep_srv, ep_port = serve(Endpoint)
    endpoint = f"http://127.0.0.1:{ep_port}/exec"
    tmp = Path(tempfile.mkdtemp(prefix="emt-send-"))
    site = build_copy(tmp, "site", endpoint)
    empty = build_copy(tmp, "empty", "")
    site_srv, site_port = serve(Quiet, site)
    empty_srv, empty_port = serve(Quiet, empty)
    url = f"http://127.0.0.1:{site_port}/quiz.html"
    summary = {"endpoint": endpoint}
    expect_sheet = []   # (rid, 班級, 座號)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        ctx = b.new_context()
        guard(ctx)
        pg = ctx.new_page()
        console = []
        # 離線／連線被擋時瀏覽器本來就會記一筆 Failed to load resource，那是預期中的；其餘錯誤都算失敗
        pg.on("console", lambda m: m.type == "error" and not m.text.startswith("Failed to load resource") and console.append(m.text))
        pg.on("pageerror", lambda e: console.append(str(e)))
        pg.goto(url)
        bank = json.loads(pg.locator("#quiz-bank").text_content())
        check(pg.locator("#data-note").is_visible(), "有設定網址時應顯示作答紀錄說明")
        note = pg.locator("#data-note").inner_text()
        check("填寫的班級座號也會一起送給老師" in note and "成果報告圖片本身只在你的瀏覽器裡產生" in note, f"作答紀錄說明文字：{note}")
        check("匿名" not in note, "說明不應再寫匿名")
        rnote = pg.locator(".report-box p").first.inner_text()
        check("班級與座號會和這一組的作答紀錄一起送給老師" in rnote, f"成果報告說明：{rnote}")

        # ── 1. 三組：1、3 產生報告，2 不產生 ──
        pg.fill("#report-class", CLS)
        pg.fill("#report-seat", SEAT)
        rids, ident_count = [], 0
        for r in range(1, 4):
            before = len(RECV)
            ids, exp = answer_round(pg, bank, rng)
            pg.wait_for_timeout(500)
            got = RECV[before:]
            check(len(got) == 1, f"第{r}組作答完應送 1 次，實際 {len(got)} 次")
            if not got:
                continue
            check(got[0]["path"] == "/exec" and (got[0]["ctype"] or "").startswith("text/plain"), f"路徑或 Content-Type：{got[0]}")
            rid = check_record(got[0]["body"], ids, exp, r, bank)
            rids.append(rid)
            if r in (1, 3):
                pg.click("#report-make")
                pg.wait_for_timeout(500)
                check(pg.locator("#report-out img").count() == 1, f"第{r}組成果報告沒有產生")
                got = RECV[before:]
                check(len(got) == 2 and kind(got[1]) == "identify", f"第{r}組產生報告後應多送 1 筆 identify，實得 {len(got)}")
                if len(got) == 2:
                    check_ident(got[1]["body"], rid)
                    ident_count += 1
                expect_sheet.append((rid, CLS, SEAT))
                if r == 1:  # 改座號再產生一次：報告照常產生，但不再送
                    pg.fill("#report-seat", "8")
                    pg.click("#report-make")
                    pg.wait_for_timeout(400)
                    check(pg.locator("#report-out img").count() == 1, "第二次產生報告失敗")
                    check(len(RECV) == before + 2, "同一組第二次產生報告不應再送 identify")
                    pg.fill("#report-seat", SEAT)
            else:
                expect_sheet.append((rid, "", ""))
                pg.wait_for_timeout(300)
                check(len(RECV) == before + 1, "沒產生報告的組不應送 identify")
            pg.click("#quiz-redraw")
        check(len(set(rids)) == 3, "三組作答編號應各不相同")
        summary["three_rounds"] = {"records": 3, "identify": ident_count}
        check(pg.evaluate("localStorage.getItem('emt-sheet-queue')") is None, "全部送達後佇列應清空")

        # ── 4. 格式不對：不產生報告、不送 ──
        before = len(RECV)
        ids, exp = answer_round(pg, bank, rng)
        pg.wait_for_timeout(400)
        check(len(RECV) == before + 1, "第 4 組作答紀錄")
        if len(RECV) == before + 1:
            rid4 = check_record(RECV[before]["body"], ids, exp, 4, bank)
        bad_msgs = {}
        for c, s in (("-228", "3"), ("228", "12a"), ("<b>", "3"), ("2 28", "3"), ("228", "1.5")):
            pg.fill("#report-class", c)
            pg.fill("#report-seat", s)
            pg.click("#report-make")
            pg.wait_for_timeout(200)
            bad_msgs[f"{c}/{s}"] = pg.locator("#report-msg").inner_text()
            check(pg.locator("#report-out img").count() == 0, f"格式不對（{c}/{s}）不應產生報告")
        check(len(RECV) == before + 1, "格式不對時不應送 identify")
        # 全形數字會轉半形後送出
        pg.fill("#report-class", "２２８")
        pg.fill("#report-seat", "０５")
        pg.click("#report-make")
        pg.wait_for_timeout(400)
        check(len(RECV) == before + 2, "全形數字轉半形後應送出 identify")
        if len(RECV) == before + 2:
            check_ident(RECV[before + 1]["body"], rid4, "228", "05")
            expect_sheet.append((rid4, "228", "05"))
        summary["bad_format_msgs"] = bad_msgs
        pg.fill("#report-class", CLS)
        pg.fill("#report-seat", SEAT)
        pg.click("#quiz-redraw")

        # ── 2. 離線 → 佇列依序 → 恢復後依序補送 ──
        before = len(RECV)
        ctx.set_offline(True)
        ids, exp = answer_round(pg, bank, rng)
        pg.click("#report-make")
        pg.wait_for_timeout(600)
        check(len(RECV) == before, "離線時不應送達")
        q = json.loads(pg.evaluate("localStorage.getItem('emt-sheet-queue')") or "[]")
        check(len(q) == 2 and "identify" not in q[0] and '"type":"identify"' in q[1], f"離線佇列應為［作答紀錄, identify］，實得 {len(q)} 筆")
        summary["offline_queue"] = [("identify" if '"identify"' in x else "record") for x in q]
        ctx.set_offline(False)
        pg.wait_for_timeout(1000)
        via_online = len(RECV) - before
        if via_online == 0:
            pg.reload()
            pg.wait_for_timeout(1000)
        got = RECV[before:]
        check([kind(x) for x in got] == ["record", "identify"], f"恢復連線後應依序補送作答紀錄、identify，實得 {[kind(x) for x in got]}")
        summary["resend_via"] = "online 事件" if via_online else "重新開頁"
        if len(got) == 2:
            rid5 = check_record(got[0]["body"], ids, exp, 5, bank)
            check_ident(got[1]["body"], rid5)
            expect_sheet.append((rid5, CLS, SEAT))
        check(pg.evaluate("localStorage.getItem('emt-sheet-queue')") is None, "補送後佇列應清空")

        # ── 3a. 連線被擋 → 重新開頁補送（作答紀錄＋identify） ──
        pg.reload()
        pg.fill("#report-class", CLS)
        pg.fill("#report-seat", SEAT)
        before = len(RECV)
        pg.route("**/exec", lambda route: route.abort())
        ids, exp = answer_round(pg, bank, rng)
        pg.click("#report-make")
        pg.wait_for_timeout(500)
        check(len(RECV) == before, "連線被擋時不應送達")
        check(len(json.loads(pg.evaluate("localStorage.getItem('emt-sheet-queue')") or "[]")) == 2, "送出失敗應進佇列 2 筆")
        pg.unroute("**/exec")
        pg2 = ctx.new_page()
        pg2.goto(url)
        pg2.wait_for_timeout(1000)
        got = RECV[before:]
        check([kind(x) for x in got] == ["record", "identify"], f"重新開頁應依序補送，實得 {[kind(x) for x in got]}")
        if len(got) == 2:
            rid6 = check_record(got[0]["body"], ids, exp, 1, bank)
            check_ident(got[1]["body"], rid6)
            expect_sheet.append((rid6, CLS, SEAT))
        check(pg2.evaluate("localStorage.getItem('emt-sheet-queue')") is None, "重新開頁補送後佇列應清空")
        pg2.close()

        # ── 3b. 佇列上限 50 ──
        pg.reload()
        pg.fill("#report-class", CLS)
        pg.fill("#report-seat", SEAT)
        pg.route("**/exec", lambda route: route.abort())
        seed = [json.dumps({"seed": i}) for i in range(50)]
        pg.evaluate("s => localStorage.setItem('emt-sheet-queue', JSON.stringify(s))", seed)
        answer_round(pg, bank, rng)
        pg.wait_for_timeout(300)
        pg.click("#report-make")
        pg.wait_for_timeout(300)
        q = json.loads(pg.evaluate("localStorage.getItem('emt-sheet-queue')") or "[]")
        check(len(q) == 50, f"佇列上限應為 50，實得 {len(q)}")
        check(len(q) == 50 and '"seed": 0' not in q[0] and '"seed": 1' not in q[0] and '"type":"identify"' in q[-1]
              and json.loads(q[-2]).get("items"), "超過上限應丟最舊、保留最新（作答紀錄＋identify）")
        summary["queue_cap"] = len(q)
        pg.evaluate("localStorage.removeItem('emt-sheet-queue')")
        pg.unroute("**/exec")

        # localStorage 不能用時也不出錯，直接依序送
        before = len(RECV)
        pg3 = ctx.new_page()
        pg3.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})")
        pg3.on("pageerror", lambda e: console.append("[無 localStorage] " + str(e)))
        pg3.goto(url)
        ids, exp = answer_round(pg3, bank, rng)
        pg3.fill("#report-class", CLS)
        pg3.fill("#report-seat", SEAT)
        pg3.click("#report-make")
        pg3.wait_for_timeout(800)
        got = RECV[before:]
        check([kind(x) for x in got] == ["record", "identify"], f"localStorage 被封鎖時應直接依序送，實得 {[kind(x) for x in got]}")
        if len(got) == 2:
            rid7 = check_record(got[0]["body"], ids, exp, 1, bank)
            check_ident(got[1]["body"], rid7)
            expect_sheet.append((rid7, CLS, SEAT))
        pg3.close()
        check(not console, f"主控台錯誤：{console}")
        # 教師版（有設定）
        pg.goto(url + "#all")
        pg.wait_for_timeout(200)
        flow = pg.locator("#bank-all .data-flow").inner_text()
        check("班級與座號會再送一次" in flow and "沒有產生報告的組別不含班級座號" in flow, f"教師版資料流向說明（已設定）：{flow}")

        # ── 5. SHEET_ENDPOINT 空：完全不送 ──
        ctx2 = b.new_context()
        guard(ctx2)
        pp = ctx2.new_page()
        reqs, perr = [], []
        pp.on("request", lambda rq: reqs.append((rq.method, rq.url)))
        pp.on("console", lambda m: m.type == "error" and perr.append(m.text))
        pp.on("pageerror", lambda e: perr.append(str(e)))
        base = f"http://127.0.0.1:{empty_port}/"
        pp.goto(base + "quiz.html")
        check(pp.locator("#data-note").count() == 0, "未設定網址時不應顯示作答紀錄說明")
        check("不會上傳" in pp.locator(".report-box p").first.inner_text(), "未設定網址時成果報告說明應為不上傳")
        before = len(RECV)
        pp.fill("#report-class", CLS)
        pp.fill("#report-seat", SEAT)
        for _ in range(2):
            answer_round(pp, bank, rng)
            pp.click("#report-make")
            pp.wait_for_timeout(200)
            pp.click("#quiz-redraw")
        pp.wait_for_timeout(500)
        other = [r for r in reqs if r[0] != "GET" or not r[1].startswith(base)]
        check(not other, f"未設定網址時不應有任何對外或 POST 請求：{other}")
        check(len(RECV) == before, "未設定網址時不應送到 endpoint")
        check(pp.evaluate("localStorage.getItem('emt-sheet-queue')") is None, "未設定網址時不應建立佇列")
        check(not perr, f"未設定網址時主控台錯誤：{perr}")
        pp.goto(base + "quiz.html#all")
        pp.wait_for_timeout(200)
        check("目前未設定作答紀錄接收網址" in pp.locator("#bank-all .data-flow").inner_text(), "教師版資料流向說明（未設定）")
        summary["empty_endpoint_requests"] = len(reqs)
        b.close()
    check(not GOOGLE, f"出現對 Google 的請求（已擋下）：{GOOGLE}")
    summary["google_requests"] = len(GOOGLE)
    check(not any(x.get("preflight") for x in RECV), "出現 CORS 預檢請求")

    # ── 6. 全部資料依到達順序交給 Code.gs doPost，檢查試算表 ──
    bodies = [x["body"] for x in RECV if not x.get("preflight")]
    js = ("const {load}=require(" + json.dumps(str(ROOT / "tools/sheets/fake_gas.js")) + ");"
          "const f=load('test-token');const bodies=JSON.parse(require('fs').readFileSync(0,'utf8'));"
          "const res=bodies.map(b=>f.post(b));const R=f.sheets.responses.data,I=f.sheets.items.data;"
          "console.log(JSON.stringify({res,rows:R.slice(1).map(r=>[r[1],r[6],r[7]]),"
          "items:I.slice(1).map(r=>[r[1],r[4],r[5]]),header:R[0].slice(0,9)}));")
    r = subprocess.run(["node", "-e", js], input=json.dumps(bodies), capture_output=True, text=True)
    try:
        out = json.loads(r.stdout)
    except ValueError:
        out = None
        errors.append(f"Code.gs 模擬失敗：{r.stderr[-500:]}")
    if out:
        bad = [x for x in out["res"] if not x.get("ok") or x.get("dup")]
        check(not bad, f"Code.gs doPost 有拒收或重複：{bad}")
        rows = {x[0]: (x[1], x[2]) for x in out["rows"]}
        check(len(rows) == len(expect_sheet) == len(out["rows"]), f"responses 列數 {len(out['rows'])} ≠ 預期 {len(expect_sheet)}")
        for rid, c, s in expect_sheet:
            check(rows.get(rid) == (c, s), f"responses {rid[:8]} 班級座號 {rows.get(rid)} ≠ {(c, s)}")
            its = [x for x in out["items"] if x[0] == rid]
            check(len(its) == 10 and all((x[1], x[2]) == (c, s) for x in its), f"items {rid[:8]} 班級座號不對")
        summary["codegs_sheet"] = {"posts": len(out["res"]), "responses_rows": len(out["rows"]),
                                   "with_class": sum(1 for v in rows.values() if v[0]),
                                   "without_class": sum(1 for v in rows.values() if not v[0])}
    for s in (ep_srv, site_srv, empty_srv):
        s.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    summary["errors"] = errors
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
