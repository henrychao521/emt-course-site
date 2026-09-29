"""E07 補題庫缺口（2026-09-29）：章節×題型×難度矩陣的空格補題。

在建國中學網路，Antigravity 不可用，改由兩個 Claude 模型出題：
- claude-opus-5-5（本機主控，自己出一批）
- claude-sonnet-4-6（`claude -p --model sonnet --tools ""`，提示只含網站知識點原文與既有題幹）
每格兩個模型各出 1 題候選，逐題回權威原文查證後每格擇一採用（或修正後採用），
另一題記錄淘汰原因。只用有明確權威出處的知識點；不用 W07、W08（網站自行整理的建議）
與 W05 首句（「主要對象是自己的救護人員與救護義消」為網站敘述）。

新題附加在既有題目之後（接在最大題號後編號），不重排既有題號。
輸出：assets/quiz-bank.json、docs/quiz-bank-2026-09-29/verified_gapfill.json
"""
import copy, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "docs/quiz-bank-2026-09-29/raw"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))
from validate import check_item, norm  # noqa: E402
from claude_batch import S  # noqa: E402
from verify import LINT  # noqa: E402
from sources import SOURCES  # noqa: E402

BANK = ROOT / "assets/quiz-bank.json"
OUT = ROOT / "docs/quiz-bank-2026-09-29/verified_gapfill.json"
CH, TY, DF = ("ch1", "ch2", "ch3", "ch4"), ("single", "tf", "scenario", "order"), (1, 2, 3)

OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-4-6"

# ── claude-opus-5-5 自出的一批（每格 1 題，順序同 CELLS） ──
CELLS = [("ch1", "scenario", 1), ("ch1", "scenario", 2), ("ch1", "tf", 3), ("ch1", "order", 3),
         ("ch2", "scenario", 1), ("ch2", "scenario", 3), ("ch2", "tf", 3),
         ("ch3", "single", 1), ("ch3", "tf", 1), ("ch3", "scenario", 1), ("ch3", "tf", 3), ("ch3", "order", 1)]

OPUS_ITEMS = [
    S("scenario", 1, "ch1", ["E01"], "運動會上有人扭傷，場邊有四個人過來幫忙。依《緊急醫療救護法》，哪一位「不屬於」法律所稱的救護人員？",
      ["學校的護理師", "來看比賽的醫師家長", "持有效證書的救護技術員", "沒有醫護資格的熱心同學"], "沒有醫護資格的熱心同學",
      "《緊急醫療救護法》第 4 條：救護人員是指醫師、護理人員、救護技術員。沒有這三種資格的人，不是法律所稱的救護人員。", ["EMSA4"]),
    S("scenario", 2, "ch1", ["E09"], "陳大哥高職畢業，一直擔任中級救護技術員從事緊急救護，至今已連續五年。依《救護技術員管理辦法》第 2 條，他能不能報名高級救護技術員訓練？",
      ["可以，從事中級救護技術員緊急救護連續四年以上就符合資格", "不行，報名高級一定要專科以上學校畢業",
       "不行，要先考上高級救護技術員甄試才能報名訓練", "不行，必須從事中級救護技術員緊急救護連續十年以上"],
      "可以，從事中級救護技術員緊急救護連續四年以上就符合資格",
      "第 2 條高級救護技術員的報名資格有兩種，符合其一即可：從事中級救護技術員緊急救護連續四年以上；或專科以上學校畢業，並領有效期內中級證書一年以上。甄試是完成高級訓練之後才有的程序（第 8 條），不是報名條件。",
      ["EMTR2"]),
    S("tf", 3, "ch1", ["E13"], "各級救護技術員展延證書所需的繼續教育時數都一樣：3 年內完成 24 小時以上。", None, "錯誤",
      "第 10 條：初級 24 小時以上（其中 12 小時以上為模組二、四、六）；中級 72 小時以上（其中 36 小時以上為模組二、四、五、七）；高級 96 小時以上（其中 48 小時以上為模組二、四、五）。三個等級的時數不同。",
      ["EMTR10"]),
    S("order", 3, "ch1", ["E07", "E08", "E09", "E11"], "一位國中畢業生打算一路走到高級救護技術員（EMTP），依《救護技術員管理辦法》，下列過程的正確順序是？",
      ["報名初級救護技術員訓練，完成後由辦理訓練的單位發給初級證書",
       "高級中等以上學校畢業後，持有效期內的初級證書報名中級訓練",
       "取得中級證書，從事中級救護技術員緊急救護連續四年以上",
       "報名高級救護技術員訓練並完成課程",
       "由訓練單位把完成訓練人員名冊送指定的甄試機構，甄試通過後發給高級證書"], None,
      "第 2 條：初級要國中以上畢業；中級要高級中等以上學校畢業並領有效期內的初級證書；高級可由從事中級救護技術員緊急救護連續四年以上取得資格。第 8 條：初級、中級證書由辦理訓練的單位發給；高級完成訓練後送指定的甄試機構，甄試通過才發證。",
      ["EMTR2", "EMTR8"]),
    S("scenario", 1, "ch2", ["W04"], "學姊已經持有初級救護技術員證書，想在紅十字會的線上教育訓練系統找「繼續教育」課程。下列哪一個訓練項目是她要找的？",
      ["A13.初級救護技術員EMT1繼續教育訓練", "A08.初級救護技術員EMT1訓練", "基本救命術訓練", "急救員訓練"],
      "A13.初級救護技術員EMT1繼續教育訓練",
      "紅十字會線上教育訓練系統的訓練項目中，「A08.初級救護技術員EMT1訓練」是初級訓練，「A13.初級救護技術員EMT1繼續教育訓練」是繼續教育；基本救命術、急救員是同一系統列出的非 EMT 課程。",
      ["RCCLASS"]),
    S("scenario", 3, "ch2", ["W01", "W02"], "下學期有三個單位都想開初級救護技術員訓練：甲、某縣消防局；乙、設有消防系的科技大學；丙、符合條件的急救責任醫院。依《救護技術員管理辦法》，哪些單位每次辦訓前必須把計畫書送中央衛生主管機關審查核准？",
      ["只有丙", "甲、乙、丙都要", "只有甲", "只有乙和丙"], "只有丙",
      "三個單位都是第 4 條允許開課的單位。第 6 條：開課前要送計畫書經中央衛生主管機關審查核准，但衛生、消防主管機關（甲）與設有相關科系所的專科以上學校（乙）辦理初級、中級訓練得免予申請；急救責任醫院（丙）不在免申請之列。",
      ["EMTR4", "EMTR6"]),
    S("tf", 3, "ch2", ["W01", "W02"], "法規允許辦理初級救護技術員訓練的醫院不限種類：任何醫院都可以開課，只是開課前要送計畫書審查核准。", None, "錯誤",
      "第 4 條列出可辦理初級訓練的四類單位，其中醫院限於符合條件的急救責任醫院，不是任何醫院都可以。後半句「開課前要送計畫書審查核准」對醫院而言是正確的（第 6 條），但前半句錯，所以整句錯誤。",
      ["EMTR4", "EMTR6"]),
    S("single", 1, "ch3", ["U01"], "初級救護技術員訓練的模組、科目、內容與時數，是依什麼辦理？",
      ["《救護技術員管理辦法》附表一", "各開課單位自行決定", "《救護技術員管理辦法》附表三", "每位授課講師自己的教材"],
      "《救護技術員管理辦法》附表一",
      "《救護技術員管理辦法》第 3 條：各級救護技術員的訓練課程模組、科目、內容及時數，依附表一至附表三辦理；初級是附表一，附表三是高級。",
      ["EMTR3"]),
    S("tf", 1, "ch3", ["U08"], "依《救護技術員管理辦法》第 13 條，「心理支持」是初級救護技術員得施行的救護項目之一。", None, "正確",
      "第 13 條列出初級救護技術員得施行的 20 項救護項目，第十七項就是心理支持。", ["EMTR13"]),
    S("scenario", 1, "ch3", ["U04"], "工場課有同學割傷後需要加壓止血。在初級救護技術員訓練課程（附表一）中，專門練習加壓止血與止血帶的是哪一個科目？",
      ["4.2 傷口清洗、止血、包紮與固定", "2.3 清除呼吸道異物", "4.5 傷患搬運", "6.5 傳染病防治演練"],
      "4.2 傷口清洗、止血、包紮與固定",
      "附表一模組四：4.2 傷口清洗、止血、包紮與固定，內容含加壓止血及止血帶的操作，時數 5 小時。2.3 是清除呼吸道異物，4.5 是傷患搬運，6.5 是傳染病防治演練。",
      ["T1"]),
    S("tf", 3, "ch3", ["U10"], "高級救護技術員課程基準（附表三）中的實習，只有醫院急診實習與救護車實習兩種。", None, "錯誤",
      "附表三除了八個課程模組，還有醫院急診實習 480 小時、救護車實習 240 小時、救護指揮中心實習 8 小時，以及綜合演練及測試 14 小時。實習不只兩種。",
      ["T3"]),
    S("order", 1, "ch3", ["U07"], "附表一模組五「半情境流程演練」的科目，是照一趟救護的先後安排的。請排出正確順序。",
      ["危急或非危急病人之現場救護", "轉送途中（救護車內）之救護", "到達醫院（下救護車）之救護"], None,
      "附表一模組五：5.1 危急病人之現場救護、5.2 非危急病人之現場救護、5.3 轉送途中（救護車內）之救護、5.4 到達醫院（下救護車）之救護。",
      ["T1"]),
]
for q in OPUS_ITEMS:
    if q["type"] == "tf":
        q["options"] = ["正確", "錯誤"]

# 查證結論在 gapfill_verdicts.py（候選 id：OG＝opus 第 n 格、SG＝sonnet 第 n 格）

METHOD = ("每格由兩個 Claude 模型各出一題候選。每題由主控（claude-opus-5-5）回到 tools/sources.py 登錄的權威來源逐句核對："
          "《救護技術員管理辦法》全文與附表一、附表三 PDF、《緊急醫療救護法》全文（全國法規資料庫，2026-09-29 以 curl 下載）、"
          "紅十字會開課資訊頁（2026-09-29 下載，確認 A08／A13 訓練項目名稱）；確認正確答案有原文支持、每個干擾選項依原文確實錯、"
          "解說不含來源未載明的推論、情境不誘導危險行為、台灣用語；再與既有 91 題比對，去除語意重複。"
          "只使用有明確權威出處的知識點，不使用網站自行整理的建議（W07、W08、W05 首句、第三章「本站對應」欄）。")


def matrix(qs):
    c = Counter((q["chapter"], q["type"], q["difficulty"]) for q in qs)
    return {f"{ch}|{t}|{d}": c[(ch, t, d)] for ch in CH for t in TY for d in DF}


def empties(m):
    return [k for k, v in m.items() if v == 0]


def load_sonnet():
    """sonnet 原始回應（_r1.txt）先輸出第 7–12 格、再補第 1–6 格，兩個 JSON 區塊依格序合併成 _r1.json。"""
    return json.loads((RAW / "claude-sonnet-4-6_gapfill_r1.json").read_text(encoding="utf-8"))


def main():
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    qs = [q for q in bank["questions"] if not q["cand_id"].startswith(("OG", "SG"))]  # 可重跑
    before = matrix(qs)
    sonnet = load_sonnet()
    cands = {}
    for i, q in enumerate(OPUS_ITEMS, 1):
        cands[f"OG{i:02d}"] = (OPUS, q)
    for i, q in enumerate(sonnet, 1):
        cands[f"SG{i:02d}"] = (SONNET, {k: v for k, v in q.items() if k != "model"})
    from gapfill_verdicts import VERDICTS  # noqa: E402
    records, new = [], []
    seen = {norm(q["stem"]) for q in qs}
    for cid, (model, q) in cands.items():
        v = VERDICTS[cid]
        rec = {"cand_id": cid, "model": model, "cell": f"{q.get('chapter')}|{q.get('type')}|{q.get('difficulty')}",
               "original": q, "auto_check": check_item(q), "verdict": v[0], "note": v[1]}
        if v[0] != "刪除":
            fq = copy.deepcopy(q)
            if len(v) > 2 and v[2]:
                fq.update(v[2])
                rec["fix_category"] = v[3]
            errs = check_item(fq) + [m for r, m in LINT if r.search(fq["explain"] + fq["stem"])]
            if errs:
                raise SystemExit(f"{cid} 最終驗收未過：{errs}")
            assert norm(fq["stem"]) not in seen, f"{cid} 題幹與既有題重複"
            seen.add(norm(fq["stem"]))
            rec["checked_against"] = {s: SOURCES[s][1] for s in fq["sources"]}
            rec["final"] = fq
            new.append((cid, model, fq))
        else:
            rec["reason_category"] = v[2] if len(v) > 2 else ""
        records.append(rec)
    n0 = len(qs)
    start = max(int(q["id"][1:]) for q in qs) + 1  # 既有題號有空號（master 刪題），新題接在最大號之後
    out = list(qs)
    tord = {"single": 0, "tf": 1, "scenario": 2, "order": 3}
    new.sort(key=lambda x: (x[2]["chapter"], x[2]["difficulty"], tord[x[2]["type"]], x[0]))
    for n, (cid, model, q) in enumerate(new, start):
        qid = f"q{n:03d}"
        for r in records:
            if r["cand_id"] == cid:
                r["bank_id"] = qid
        out.append({"id": qid, **{k: q[k] for k in ("chapter", "type", "difficulty", "kp", "stem")},
                    **({"items": q["items"]} if q["type"] == "order" else {"options": q["options"], "answer": q["answer"]}),
                    "explain": q["explain"], "sources": q["sources"], "model": model, "cand_id": cid})
    after = matrix(out)
    bank["questions"] = out
    BANK.write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")
    summ = {
        "題庫總數": {"補題前": n0, "補題後": len(out), "新增": len(new)},
        "各模型": {m: dict(Counter(r["verdict"] for r in records if r["model"] == m)) for m in (OPUS, SONNET)},
        "採用來源": dict(Counter(m for _, m, _ in new)),
        "補題前空格": empties(before), "補題後空格": empties(after),
        "未補空格說明": UNFILLED,
        "章節x題型x難度_補題前": before, "章節x題型x難度_補題後": after,
    }
    OUT.write_text(json.dumps({"date": "2026-09-29", "task": "E07 補題庫缺口", "method": METHOD, "generation": GENERATION,
                               "summary": summ, "records": records}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summ.items() if not k.startswith("章節")}, ensure_ascii=False, indent=1))


UNFILLED = {}
GENERATION = {}

if __name__ == "__main__":
    from gapfill_verdicts import UNFILLED as U, GENERATION as G  # noqa: E402
    UNFILLED.update(U)
    GENERATION.update(G)
    main()
