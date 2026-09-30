#!/usr/bin/env python3
"""作答紀錄送出端對端測試：本機假 endpoint 代替 Apps Script，用 Playwright 實際作答。
1. 有設定網址：作答 3 組 → 每組剛好送一次、內容與畫面一致、不含班級座號；送到的資料再交給 Code.gs 的 validate_ 驗一次。
2. 離線：瀏覽器離線時完成一組 → 進 localStorage 佇列、不送；恢復連線／重新開頁後補送。
3. 送出失敗（連線被擋）且佇列已有 50 筆 → 佇列維持上限 50、保留最新。
4. SHEET_ENDPOINT 空字串（網站根目錄的正式版）→ 完全不發請求、沒有錯誤、不顯示作答紀錄說明。
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
RECV = []          # 假 endpoint 收到的 body
errors = []


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


def answer_round(pg, bank, rng):
    """把目前這組全部作答，回傳 {qid: (ok, code, key)}（依網站應送出的代號規則自行推算）。"""
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


def check_body(body, ids, exp, round_no, bank, token, secrets):
    d = json.loads(body)
    check(set(d) == {"v", "token", "rid", "bank", "round", "items"}, f"頂層欄位不對：{sorted(d)}")
    check(d["v"] == 1 and d["token"] == token and d["bank"] == bank["version"], "v／token／bank 不對")
    check(re.fullmatch(r"[0-9a-f]{32}", d["rid"]) is not None, f"作答編號格式 {d['rid']}")
    check(d["round"] == round_no, f"第幾組 {d['round']} ≠ {round_no}")
    check([it["q"] for it in d["items"]] == ids, "題號順序和畫面不同")
    for it in d["items"]:
        ok, code, key, h, t = exp[it["q"]]
        check(set(it) == {"q", "h", "t", "ok", "a", "k"}, f"{it['q']} 欄位 {sorted(it)}")
        check((it["ok"], it["a"], it["k"], it["h"], it["t"]) == (ok, code, key, h, t),
              f"{it['q']} 送出 {it} ≠ 預期 {(ok, code, key, h, t)}")
    for s in secrets:
        check(s not in body, f"送出內容含班級座號字串 {s!r}")
    for w in ("class", "seat", "班級", "座號"):
        check(w not in body, f"送出內容含 {w}")
    return d["rid"]


def main():
    rng = random.Random(11)
    ep_srv, ep_port = serve(Endpoint)
    endpoint = f"http://127.0.0.1:{ep_port}/exec"
    tmp = Path(tempfile.mkdtemp(prefix="emt-send-"))
    site = tmp / "site"
    shutil.copytree(ROOT, site, ignore=shutil.ignore_patterns(".git", "docs", "__pycache__", "*.pyc"))
    env = dict(os.environ, EMT_SHEET_ENDPOINT=endpoint, EMT_SHEET_TOKEN="test-token")
    subprocess.run([sys.executable, str(site / "tools" / "build.py")], check=True, env=env, capture_output=True)
    site_srv, site_port = serve(Quiet, site)
    prod_srv, prod_port = serve(Quiet, ROOT)
    url = f"http://127.0.0.1:{site_port}/quiz.html"
    summary = {"endpoint": endpoint}
    secrets = ["測試班ZQ", "Q7"]
    all_bodies = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        ctx = b.new_context()
        pg = ctx.new_page()
        console = []
        # 離線／連線被擋時瀏覽器本來就會記一筆 Failed to load resource，那是預期中的；其餘錯誤都算失敗
        pg.on("console", lambda m: m.type == "error" and not m.text.startswith("Failed to load resource") and console.append(m.text))
        pg.on("pageerror", lambda e: console.append(str(e)))
        pg.goto(url)
        bank = json.loads(pg.locator("#quiz-bank").text_content())
        check(pg.locator("#data-note").is_visible(), "有設定網址時應顯示作答紀錄說明")
        note = pg.locator("#data-note").inner_text()
        check("匿名送出各題對錯與所選答案" in note and "不含班級座號" in note, "作答紀錄說明文字")
        # ── 1. 三組 ──
        pg.fill("#report-class", secrets[0])
        pg.fill("#report-seat", secrets[1])
        rids = []
        for r in range(1, 4):
            before = len(RECV)
            ids, exp = answer_round(pg, bank, rng)
            pg.wait_for_timeout(600)
            got = RECV[before:]
            check(len(got) == 1, f"第{r}組應送 1 次，實際 {len(got)} 次")
            if got:
                check(got[0]["path"] == "/exec" and (got[0]["ctype"] or "").startswith("text/plain"), f"路徑或 Content-Type：{got[0]}")
                rids.append(check_body(got[0]["body"], ids, exp, r, bank, "test-token", secrets))
                all_bodies.append(got[0]["body"])
            if r == 1:  # 成果報告照常可以產生，而且不會多送
                pg.click("#report-make")
                pg.wait_for_timeout(300)
                check(pg.locator("#report-out img").count() == 1, "成果報告沒有產生")
                # 報告區再點一次、重複點已答題目都不應再送
                pg.locator("#quiz-list .q .opt").first.click(force=True)
                pg.wait_for_timeout(300)
                check(len(RECV) == before + 1, "產生成果報告或重複點選後多送了")
            pg.click("#quiz-redraw")
        check(len(set(rids)) == 3, "三組作答編號應各不相同")
        check(not any(x.get("preflight") for x in RECV), "出現 CORS 預檢請求")
        summary["three_rounds_sent"] = len(RECV)
        q = pg.evaluate("localStorage.getItem('emt-sheet-queue')")
        check(q is None, f"全部送達後佇列應清空，實得 {q}")

        # ── 2. 離線 → 佇列 → 恢復後補送 ──
        before = len(RECV)
        ctx.set_offline(True)
        ids, exp = answer_round(pg, bank, rng)
        pg.wait_for_timeout(600)
        check(len(RECV) == before, "離線時不應送達")
        q = json.loads(pg.evaluate("localStorage.getItem('emt-sheet-queue')") or "[]")
        check(len(q) == 1, f"離線完成一組應進佇列 1 筆，實得 {len(q)}")
        summary["offline_queue_len"] = len(q)
        ctx.set_offline(False)
        pg.wait_for_timeout(800)
        via_online = len(RECV) - before
        if via_online == 0:  # 若 online 事件沒觸發，重新開頁補送
            pg.reload()
            pg.wait_for_timeout(800)
        got = RECV[before:]
        check(len(got) == 1, f"恢復連線後應補送 1 次，實得 {len(got)}")
        summary["resend_via"] = "online 事件" if via_online else "重新開頁"
        if got:
            check_body(got[0]["body"], ids, exp, 4, bank, "test-token", secrets)
            all_bodies.append(got[0]["body"])
        check(pg.evaluate("localStorage.getItem('emt-sheet-queue')") is None, "補送後佇列應清空")

        # 重新開頁補送（明確測）：先離線完成一組，關掉連線狀態下不補送；恢復後開新頁
        pg.reload()
        before = len(RECV)
        pg.route("**/exec", lambda route: route.abort())
        ids, exp = answer_round(pg, bank, rng)
        pg.wait_for_timeout(500)
        check(len(RECV) == before, "連線被擋時不應送達")
        check(len(json.loads(pg.evaluate("localStorage.getItem('emt-sheet-queue')") or "[]")) == 1, "送出失敗應進佇列")
        pg.unroute("**/exec")
        pg2 = ctx.new_page()
        pg2.goto(url)
        pg2.wait_for_timeout(800)
        got = RECV[before:]
        check(len(got) == 1, f"重新開頁應補送 1 次，實得 {len(got)}")
        if got:
            check_body(got[0]["body"], ids, exp, 1, bank, "test-token", secrets)
            all_bodies.append(got[0]["body"])
        check(pg2.evaluate("localStorage.getItem('emt-sheet-queue')") is None, "重新開頁補送後佇列應清空")
        summary["resend_on_reload"] = len(got)
        pg2.close()

        # ── 3. 佇列上限 50 ──
        pg.reload()
        pg.route("**/exec", lambda route: route.abort())
        seed = [json.dumps({"seed": i}) for i in range(50)]
        pg.evaluate("s => localStorage.setItem('emt-sheet-queue', JSON.stringify(s))", seed)
        answer_round(pg, bank, rng)
        pg.wait_for_timeout(500)
        q = json.loads(pg.evaluate("localStorage.getItem('emt-sheet-queue')") or "[]")
        check(len(q) == 50, f"佇列上限應為 50，實得 {len(q)}")
        check(q and '"seed": 0' not in q[0] and json.loads(q[-1]).get("v") == 1, "超過上限應丟最舊、保留最新")
        summary["queue_cap"] = len(q)
        pg.evaluate("localStorage.removeItem('emt-sheet-queue')")
        pg.unroute("**/exec")

        # localStorage 不能用時（例如被封鎖）也不出錯，直接送
        before = len(RECV)
        pg3 = ctx.new_page()
        pg3.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})")
        pg3.on("pageerror", lambda e: console.append("[無 localStorage] " + str(e)))
        pg3.goto(url)
        ids, exp = answer_round(pg3, bank, rng)
        pg3.wait_for_timeout(600)
        got = RECV[before:]
        check(len(got) == 1, f"localStorage 被封鎖時應直接送 1 次，實得 {len(got)}")
        if got:
            all_bodies.append(got[0]["body"])
        summary["no_storage_sent"] = len(got)
        pg3.close()
        check(not console, f"主控台錯誤：{console}")

        # ── 4. 正式版（SHEET_ENDPOINT 空）：完全不送 ──
        ctx2 = b.new_context()
        pp = ctx2.new_page()
        reqs, perr = [], []
        pp.on("request", lambda rq: reqs.append((rq.method, rq.url)))
        pp.on("console", lambda m: m.type == "error" and perr.append(m.text))
        pp.on("pageerror", lambda e: perr.append(str(e)))
        prod = f"http://127.0.0.1:{prod_port}/quiz.html"
        pp.goto(prod)
        cfg = json.loads(pp.locator("#quiz-config").text_content())
        check(cfg["SHEET_ENDPOINT"] == "", f"正式版 SHEET_ENDPOINT 應為空：{cfg}")
        check(pp.locator("#data-note").count() == 0, "未設定網址時不應顯示作答紀錄說明")
        before = len(RECV)
        for _ in range(2):
            answer_round(pp, bank, rng)
            pp.click("#quiz-redraw")
        pp.wait_for_timeout(500)
        posts = [r for r in reqs if r[0] != "GET" or not r[1].startswith(f"http://127.0.0.1:{prod_port}/")]
        check(not posts, f"正式版不應有任何對外或 POST 請求：{posts}")
        check(len(RECV) == before, "正式版不應送到 endpoint")
        check(pp.evaluate("localStorage.getItem('emt-sheet-queue')") is None, "正式版不應建立佇列")
        check(not perr, f"正式版主控台錯誤：{perr}")
        pp.goto(prod + "#all")
        pp.wait_for_timeout(200)
        check("目前未設定作答紀錄接收網址" in pp.locator("#bank-all .data-flow").inner_text(), "教師版資料流向說明（未設定）")
        summary["prod_requests"] = len(reqs)
        # 教師版（有設定）
        pg.goto(url + "#all")
        pg.wait_for_timeout(200)
        check("匿名送到老師的 Google 試算表" in pg.locator("#bank-all .data-flow").inner_text(), "教師版資料流向說明（已設定）")
        b.close()

    # ── 送到的資料交給 Code.gs 的 validate_ 再驗一次 ──
    js = ("const fs=require('fs'),vm=require('vm');const c={};vm.createContext(c);"
          f"vm.runInContext(fs.readFileSync({json.dumps(str(ROOT / 'tools/sheets/Code.gs'))},'utf8'),c);"
          "c.CONFIG.TOKEN='test-token';const bodies=JSON.parse(fs.readFileSync(0,'utf8'));"
          "console.log(JSON.stringify(bodies.map(b=>c.validate_(b).ok?'ok':c.validate_(b).error)));")
    r = subprocess.run(["node", "-e", js], input=json.dumps(all_bodies), capture_output=True, text=True)
    verdicts = json.loads(r.stdout or "[]")
    check(verdicts and all(v == "ok" for v in verdicts), f"Code.gs validate_ 結果：{verdicts} {r.stderr}")
    summary["codegs_validate"] = f"{verdicts.count('ok')}/{len(verdicts)} ok"
    if all_bodies:
        d0 = json.loads(all_bodies[0])
        summary["sample_body"] = {k: v for k, v in d0.items() if k != "items"} | {"items[0:2]": d0["items"][:2], "body_bytes": len(all_bodies[0].encode())}
    for s in (ep_srv, site_srv, prod_srv):
        s.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    summary["errors"] = errors
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
