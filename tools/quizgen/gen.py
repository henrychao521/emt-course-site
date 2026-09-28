"""多模型出題：agy_meter.run 派工 → validate 驗收 → 不合格退回（每模型最多 3 回合）。
提示只含本網站文字與本機整理的知識點清單（site_text），不含外部原文。
用法：python3 tools/quizgen/gen.py <模型> [<模型> ...]
"""
import json, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/quiz-bank-2026-09-29/raw"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, "/Users/Shared/antigravity-bridge")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agy_guard, agy_meter  # noqa: E402
from validate import KN, check_batch, extract_json  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
from sources import SOURCES  # noqa: E402

CH = {"ch1": "第一章 EMT 是什麼", "ch2": "第二章 在台灣哪裡上課", "ch3": "第三章 EMT-1 課程單元", "ch4": "第四章 工場常見傷害的第一時間處置"}

PLAN = {
    "gemini-3.1-pro-high": dict(n=24, focus=[k for k in KN if k[0] in "EU"],
                                mins={"single": 7, "tf": 5, "scenario": 4, "order": 3}),
    "gemini-3.8-flash-high": dict(n=24, focus=[k for k in KN if k[0] in "GBRC"],
                                  mins={"single": 6, "tf": 5, "scenario": 7, "order": 3}),
    "claude-sonnet-4-6": dict(n=24, focus=[k for k in KN if k[0] in "YSP"],
                              mins={"single": 6, "tf": 5, "scenario": 7, "order": 3}),
    "gpt-oss-120b-medium": dict(n=20, focus=[k for k in KN if k[0] in "W"] + ["E07", "E12", "E13", "G01", "G02", "B05", "R01", "C04", "S01", "P02", "P04", "P10"],
                                mins={"single": 5, "tf": 4, "scenario": 5, "order": 2}),
}


def kn_block():
    lines = []
    for ch, title in CH.items():
        lines.append(f"## {ch}｜{title}")
        for k, v in KN.items():
            if v["chapter"] == ch:
                lines.append(f"- [{k}] {v['topic']}：{v['site_text']}（出處 key：{', '.join(v['sources'])}）")
    return "\n".join(lines)


def src_block():
    used = sorted({s for v in KN.values() for s in v["sources"]})
    return "\n".join(f"- {k}：{SOURCES[k][0]}" for k in used)


def build_prompt(model, feedback=None):
    p = PLAN[model]
    focus = "、".join(p["focus"])
    mins = "、".join(f"{t} 至少 {n} 題" for t, n in p["mins"].items())
    s = f"""你是台灣高中生活科技課的命題老師。以下是本課程網站「從工場安全到 EMT-1」整理出的知識點清單（每點都是網站原句）。
請**只根據這份清單**出選擇題，給高中生做觀念測驗。不要使用清單以外的知識、數字或做法；清單沒寫的一律不要考。

# 知識點清單
{kn_block()}

# 出處 key 對照（只能用這些 key）
{src_block()}

# 任務
出 {p['n']} 題，**優先涵蓋這些知識點**：{focus}（每題 kp 至少要有一個是這些 id；同一知識點最多出 2 題且角度要不同）。
題型要多元：{mins}。四種題型說明：
- single：一般單選，4 個選項。
- tf：是非題，options 固定為 ["正確","錯誤"]。
- scenario：情境判斷題，4 個選項。第四章用工場或校園事故情境（例如線鋸割傷、熱熔膠槍燙傷、虎鉗夾傷、木屑或化學品入眼、延長線觸電、同學昏倒），問「你第一步／下一步應該做什麼」或「在場的人誰先做什麼」；第一～三章用報名資格、證書展延、找開課單位、判斷某項救護能不能由初級做等生活情境。
- order：排序題，items 依**正確順序**列出 3 到 6 個步驟（例如 CPR 流程、沖脫泡蓋送、斷指保存步驟）；不用 options 與 answer。
難度分三級並大致平均：1＝直接記憶、2＝理解或區辨相近數字與條件、3＝情境應用或需要整合兩個以上知識點。

# 品質規則
1. 正確答案必須能由清單原句直接支持；干擾選項必須依清單**明確是錯的**，但要合理（常見迷思、相近數字、其他等級的規定），不可模稜兩可。
2. 情境題不可誘導危險行為：正確選項絕不能是清單說「不要做」的事；題幹不要描述血腥細節。
3. 解說（explain）要說明正確答案的依據，並簡短指出主要干擾選項錯在哪；可以引用清單原句。
4. 繁體中文、台灣用語（例如：影片、列印、網路、資訊、包紮），不可出現簡體字。
5. 選項文字前面不要加 A. B. 字首；不要用「以上皆是」「以上皆非」。
6. sources 只能填該題所用知識點後面列出的出處 key。
7. 不要出重複或換句話說的同一題。

# 輸出格式
只輸出一個 JSON 陣列，不要任何其他文字、不要 markdown。每個元素：
{{"type":"single|tf|scenario|order","difficulty":1|2|3,"chapter":"ch1|ch2|ch3|ch4","kp":["知識點id"],"stem":"題幹","options":["…","…","…","…"],"answer":"與某個選項完全相同的文字","items":["排序題才有，依正確順序"],"explain":"解說","sources":["出處key"]}}
chapter 必須等於知識點所屬章節。排序題省略 options 與 answer；其他題型省略 items。
"""
    if feedback:
        s += "\n# 上一回合驗收未通過，問題如下，請修正後**重新輸出完整的 JSON 陣列**（全部題目）：\n" + "\n".join("- " + f for f in feedback[:40])
    return s


def run_model(model):
    blocked = agy_guard.blocked()
    if blocked:
        print("agy_guard 擋下：", blocked); return None
    p = PLAN[model]
    log = {"model": model, "rounds": [], "started": datetime.now().astimezone().isoformat()}
    best, feedback = [], None
    for r in range(1, 4):
        prompt = build_prompt(model, feedback)
        t0 = time.time()
        data = agy_meter.run(prompt, model=model, timeout=900, note=f"emt-quiz 出題 r{r}")
        resp = data.get("response") or ""
        (OUT / f"{model}_r{r}.txt").write_text(resp, encoding="utf-8")
        rec = {"round": r, "status": data.get("status"), "secs": round(time.time() - t0), "resp_chars": len(resp),
               "usage": data.get("usage")}
        if data.get("status") in ("NETWORK_BLOCKED", "LOCAL_ERROR") or (not resp and data.get("status") != "SUCCESS"):
            rec["error"] = data.get("error") or data.get("status")
            log["rounds"].append(rec)
            print(model, "呼叫失敗，停止：", rec["error"])
            break
        try:
            items = extract_json(resp)
            ok, errs, good = check_batch(items, need=p["n"], mins=p["mins"])
        except Exception as e:
            ok, errs, good, items = False, [f"JSON 解析失敗：{e}"], [], []
        rec.update(ok=ok, n_items=len(items) if isinstance(items, list) else 0, n_good=len(good), errors=errs)
        log["rounds"].append(rec)
        print(f"{model} 第{r}回合：{'通過' if ok else '退回'} 合格 {len(good)}/{len(items) if isinstance(items, list) else 0}；{errs[:3]}")
        if len(good) > len(best):
            best = good
        if ok:
            break
        feedback = errs
    for q in best:
        q["model"] = model
    (OUT / f"{model}_final.json").write_text(json.dumps(best, ensure_ascii=False, indent=1), encoding="utf-8")
    log["n_final"] = len(best)
    (OUT / f"{model}_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    return log


if __name__ == "__main__":
    for m in sys.argv[1:]:
        run_model(m)
