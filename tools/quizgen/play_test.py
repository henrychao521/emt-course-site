"""Playwright 實際作答 3 輪：檢查抽題（10 題、無重複、章節與難度平衡）、計分、解說與出處、教師版。
用法：python3 tools/quizgen/play_test.py <quiz.html 的 URL> [輸出 json]
"""
import json, random, sys
from collections import Counter
from playwright.sync_api import sync_playwright

url = sys.argv[1]
report = {"url": url, "rounds": [], "errors": [], "console": []}
random.seed(7)
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page()
    pg.on("console", lambda m: m.type in ("error", "warning") and report["console"].append(m.text))
    pg.on("pageerror", lambda e: report["console"].append(str(e)))
    pg.goto(url)
    bank = json.loads(pg.locator("#quiz-bank").text_content())
    Q = {q["id"]: q for q in bank["questions"]}
    all_seen = []
    for r in range(1, 4):
        ids = pg.eval_on_selector_all("#quiz-list .q", "els => els.map(e => e.dataset.id)")
        rec = {"round": r, "ids": ids}
        if len(ids) != 10: report["errors"].append(f"第{r}輪題數 {len(ids)}")
        if len(set(ids)) != len(ids): report["errors"].append(f"第{r}輪有重複題")
        kps = [k for i in ids for k in Q[i]["kp"]]
        rec["chapters"] = dict(Counter(Q[i]["chapter"] for i in ids))
        rec["difficulty"] = dict(Counter(Q[i]["difficulty"] for i in ids))
        rec["types"] = dict(Counter(Q[i]["type"] for i in ids))
        rec["dup_kp"] = [k for k, c in Counter(kps).items() if c > 1]
        expect_correct = 0
        for n, qid in enumerate(ids):
            q = Q[qid]
            box = pg.locator(f'#quiz-list .q[data-id="{qid}"]')
            if box.locator(".explain").is_visible(): report["errors"].append(f"{qid} 作答前解說就顯示")
            if q["type"] == "order":
                btns = box.locator(".order-opt")
                texts = btns.evaluate_all("els => els.map(e => e.dataset.v)")
                if sorted(texts) != sorted(q["items"]): report["errors"].append(f"{qid} 排序選項不符")
                seq = list(q["items"]) if random.random() < .5 else random.sample(q["items"], len(q["items"]))
                for t in seq:
                    box.locator(f'.order-opt[data-v="{t}"]').click()
                ok = seq == q["items"]
            else:
                texts = box.locator(".opt").evaluate_all("els => els.map(e => e.dataset.v)")
                if sorted(texts) != sorted(q["options"]): report["errors"].append(f"{qid} 選項不符")
                if q["type"] == "tf" and texts != ["正確", "錯誤"]: report["errors"].append(f"{qid} 是非題順序異常")
                pick = q["answer"] if random.random() < .5 else random.choice(texts)
                box.locator(f'.opt[data-v="{pick}"]').click()
                ok = pick == q["answer"]
                right = box.locator(".opt.right").evaluate_all("els => els.map(e => e.dataset.v)")
                if right != [q["answer"]]: report["errors"].append(f"{qid} 標示的正解不對：{right}")
            expect_correct += ok
            res = box.get_attribute("data-result")
            if res != ("right" if ok else "wrong"): report["errors"].append(f"{qid} 判分錯：{res} vs {ok}")
            ex = box.locator(".explain")
            if not ex.is_visible(): report["errors"].append(f"{qid} 解說未顯示")
            hrefs = ex.locator("a.cite").evaluate_all("els => els.map(e => e.href)")
            want = [bank["sources"][s][1] for s in q["sources"]]
            if [h.rstrip("/") for h in hrefs] != [w.rstrip("/") for w in want]:
                report["errors"].append(f"{qid} 出處連結不符 {hrefs} vs {want}")
            if q["explain"] not in ex.inner_text(): report["errors"].append(f"{qid} 解說文字不符")
        score = pg.locator("#score-text").inner_text()
        rec["score_text"] = score
        rec["expect_correct"] = expect_correct
        if f"答對 {expect_correct} 題" not in score or "10 / 10" not in score:
            report["errors"].append(f"第{r}輪計分顯示不符：{score}（預期答對 {expect_correct}）")
        report["rounds"].append(rec)
        all_seen += ids
        pg.locator("#quiz-redraw").click()
    report["overlap_between_rounds"] = len(all_seen) - len(set(all_seen))
    # 教師版
    pg.goto(url.split("#")[0] + "#all")
    pg.wait_for_timeout(300)
    n_all = pg.locator("#bank-all .qa").count()
    report["teacher_count"] = n_all
    if n_all != len(Q): report["errors"].append(f"教師版題數 {n_all} ≠ 題庫 {len(Q)}")
    if pg.locator("#quiz-app").is_visible(): report["errors"].append("教師版仍顯示測驗區")
    if not pg.locator("#bank-all").is_visible(): report["errors"].append("教師版未顯示")
    b.close()
if len(sys.argv) > 2:
    open(sys.argv[2], "w").write(json.dumps(report, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in report.items() if k != "rounds"}, ensure_ascii=False, indent=1))
for r in report["rounds"]:
    print(r["round"], r["chapters"], r["difficulty"], r["types"], r["dup_kp"], r["score_text"])
