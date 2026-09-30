"""2026-09-30 題庫擴充（98→約 200 題）：多模型出「同一知識點的不同情境／題型變體」。

分工（依知識點切開，避免跨模型重複）：
- gemini-3.1-pro-high（agy）：第一章 E、第三章 U
- gemini-3.8-flash-high（agy）：第四章 G、B、R、C
- claude-sonnet-4-6（`claude -p --model sonnet --tools ""`，無工具）：第四章 Y、S、P
- claude-opus-5-5（主控本機，claude_0930.py）：第二章 W、第三章 U（與 gemini-pro 交叉）

提示只含本網站文字（知識點的 site_text）、既有題幹與出題規格，不含任何網頁／PDF 原文（MULTIMODEL_BRIEF 安全規則）。
用法：python3 tools/quizgen/gen_0930.py plan｜prompt <模型>｜run <模型>
"""
import json, subprocess, sys, time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/quiz-bank-2026-09-30/raw"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))
from validate import KN, check_batch, extract_json  # noqa: E402
from sources import SOURCES  # noqa: E402

BANK = json.loads((ROOT / "assets/quiz-bank.json").read_text(encoding="utf-8"))
QS = [q for q in BANK["questions"] if int(q["id"][1:]) <= 103]  # 擴充前的 98 題

CH = {"ch1": "第一章 EMT 是什麼", "ch2": "第二章 在台灣哪裡上課", "ch3": "第三章 EMT-1 課程單元", "ch4": "第四章 工場常見傷害的第一時間處置"}
TYPE_ZH = {"single": "單選", "tf": "是非", "scenario": "情境判斷", "order": "排序"}

# 可排序的知識點（有先後步驟或編號順序）
ORDERABLE = {"E07", "E08", "E09", "E10", "E11", "E13", "U02", "U03", "U04", "U05", "U06", "U07", "U09", "U10",
             "W02", "G01", "G02", "B01", "B04", "B05", "B09", "R01", "C04", "S01", "S02", "P02", "P10", "P16", "P18",
             "P04", "P14", "Y02"}
# 只需 2 題的小知識點；第二章與第三章題目少，放大到 4
MINOR = {"E03", "E04", "E06", "E21", "W06", "G03", "G04", "P01", "S03", "U01", "E02", "E20", "W03", "R11", "C07",
         "P15", "Y03", "R05", "R04", "P08", "C05", "C06", "B03", "E05"}
BIG = {"W01", "W02", "W04", "W05", "U02", "U04", "U05", "U07", "U08", "U09", "U10", "E10", "E13", "E12", "E09"}

SCOPE = {
    "gemini-3.1-pro-high": ("E",),
    "gemini-3.8-flash-high": ("G", "B", "R", "C"),
    "claude-sonnet-4-6": ("Y", "S", "P"),
    "claude-opus-5-5": ("W", "U"),
}
DIFF_BY_TYPE = {"tf": [1, 2, 1, 3], "single": [1, 2, 3], "scenario": [2, 3, 3, 1], "order": [2, 3]}
KEY4 = {"P02", "P04", "P10", "R01", "R02", "B01", "B05", "C04", "S01", "S05", "Y01", "Y02", "Y04", "G01", "C02", "R08"}


def existing_by_kp():
    by = defaultdict(list)
    for q in QS:
        for k in q["kp"]:
            by[k].append(q)
    return by


PART = None  # (第幾份, 共幾份)：輸出太長時把規格格切成幾份分次呼叫（sonnet 46 題一次呼叫 25 分鐘未回應）


def slots_for(model, part=None):
    part = part or PART
    full = _slots_for(model)
    if not part:
        return full
    i, n = part
    return [x for j, x in enumerate(full) if j * n // len(full) == i - 1]


def _slots_for(model):
    """每個知識點要補幾題、建議題型：避開既有題型，輪流 scenario→tf→single→order。"""
    by = existing_by_kp()
    prim = Counter(q["kp"][0] for q in QS)
    out, used = [], Counter()
    for k, v in KN.items():
        if not v["quiz_ok"] or not k.startswith(SCOPE[model]):
            continue
        if k[0] in "GBRCYSP":  # 第四章知識點多：一般 2 題、重點 3 題、小知識點 1 題
            target = 3 if k in KEY4 else 1 if k in MINOR else 2
        else:
            target = 4 if k in BIG else 2 if k in MINOR else 3
        need = max(0, target - prim[k])
        if need == 0:
            continue
        have = Counter(q["type"] for q in by[k])
        order = ["scenario", "single", "tf"] + (["order"] if k in ORDERABLE else [])
        order.sort(key=lambda t: have[t])
        types = [order[i % len(order)] for i in range(need)]
        for t in types:
            d = DIFF_BY_TYPE[t][used[t] % len(DIFF_BY_TYPE[t])]
            used[t] += 1
            out.append((k, t, d))
    return out


def kn_block(model):
    lines = []
    for ch, title in CH.items():
        ks = [(k, v) for k, v in KN.items() if v["chapter"] == ch and v["quiz_ok"] and k.startswith(SCOPE[model])]
        if not ks:
            continue
        lines.append(f"## {ch}｜{title}")
        for k, v in ks:
            lines.append(f"- [{k}] {v['topic']}：{v['site_text']}（出處 key：{', '.join(v['sources'])}）")
    return "\n".join(lines)


def existing_block(model):
    by = existing_by_kp()
    lines = []
    for k, v in KN.items():
        if not v["quiz_ok"] or not k.startswith(SCOPE[model]) or not by[k]:
            continue
        for q in by[k]:
            ans = " → ".join(q["items"]) if q["type"] == "order" else q["answer"]
            lines.append(f"- [{k}]（{TYPE_ZH[q['type']]}）{q['stem']}　答：{ans}")
    return "\n".join(lines)


def build_prompt(model, feedback=None):
    slots = slots_for(model)
    slot_lines = "\n".join(f"{i}. 知識點 {k}｜題型 {t}｜難度 {d}" for i, (k, t, d) in enumerate(slots, 1))
    srcs = sorted({s for k, _, _ in slots for s in KN[k]["sources"]})
    s = f"""你是台灣高中生活科技課的命題老師。以下是課程網站「從工場安全到 EMT-1」的知識點清單，每一點都是網站原句，網站原句都引用法規或衛福部、消防署、臺北市消防局、臺大醫院等權威資料。
網站的原則是「以引用資料為主，不自行引申或補充說明」。請**只根據這份清單**出題；清單沒寫的數字、做法、理由一律不要出現在題目、選項或解說中。

# 知識點清單
{kn_block(model)}

# 出處 key 對照（只能用這些 key）
{chr(10).join(f"- {k}：{SOURCES[k][0]}" for k in srcs)}

# 已經有的題目（不要再出相同或換句話說的題目；你要出的是同一知識點的「不同情境、不同問法」變體）
{existing_block(model)}

# 任務：依下列規格逐格出題，共 {len(slots)} 題，順序照規格
{slot_lines}

四種題型：
- single：一般單選，4 個選項。
- tf：是非題，options 固定為 ["正確","錯誤"]。是非題的錯誤敘述要只錯一個關鍵點（例如數字、等級、順序），不可整句都錯。
- scenario：情境判斷，4 個選項。第四章用高中生活科技工場或校園情境（線鋸、美工刀、熱熔膠槍、烙鐵、雷切件、虎鉗、鑽床、木屑、化學品、延長線、電動工具、體育課或走廊有人倒下），問「下一步」「哪個做法正確」「誰先做什麼」。第一～三章用報名、證書展延、找開課單位、查課程模組時數等情境（人物用學生、學長姐、老師、家長、社區志工）。
- order：排序題，items 依**正確順序**列出 3 到 6 項，不要 options 與 answer；只能排清單原句明確有先後的步驟，或附表的科目編號／時數大小。
難度：1＝直接記憶；2＝區辨相近數字、等級或條件；3＝情境應用或整合兩個以上知識點。

# 品質規則
1. 正確答案必須能由清單原句直接支持；每個干擾選項必須依清單**明確是錯的**（清單沒寫到的做法不能當錯誤選項，因為無法查證），不可模稜兩可。
2. 情境題不可誘導危險行為：正確選項絕不能是清單說「不要做」的事；不要描述血腥細節；情境中的學生不做清單沒寫的處置。止血帶、CPR、AED 相關題目不要暗示沒受訓的學生去做清單沒寫的操作。
3. 清單寫「依授課單位規定」的事項（工場停機斷電程序、學校通報流程、護目鏡配戴、年齡限制、費用、及格分數），不可出成有標準答案的題目。
4. 解說（explain）只寫清單原句的依據，可引用原句（用「」），簡短指出主要干擾選項錯在哪；**不可**加上清單沒有的理由、醫學解釋或建議；不要出現知識點代號（如 E01）、出處代碼、「選項 A」這類字。
5. 繁體中文、台灣用語（影片、列印、網路、資訊、包紮、冰敷袋），不可出現簡體字。
6. 選項前不要加 A. B. 字首；不要用「以上皆是」「以上皆非」；4 個選項長短不要差太多，正確答案不要總是最長的那個。
7. sources 只能填該題知識點後面列出的出處 key，且只填解說真正用到的。
8. 每題加 "variant_group" 欄位，值等於該題主要測的知識點 id（規格上的那個知識點）。

# 輸出格式
只輸出一個 JSON 陣列，不要任何其他文字、不要 markdown、不要寫任何檔案。每個元素：
{{"slot":規格序號,"type":"single|tf|scenario|order","difficulty":1|2|3,"chapter":"ch1|ch2|ch3|ch4","kp":["知識點id"],"variant_group":"知識點id","stem":"題幹","options":["…","…","…","…"],"answer":"與某個選項完全相同的文字","items":["排序題才有，依正確順序"],"explain":"解說","sources":["出處key"]}}
kp 第一個必須是規格上的知識點；chapter 必須等於該知識點所屬章節。排序題省略 options 與 answer；其他題型省略 items。
"""
    if feedback:
        s += "\n# 上一回合驗收未通過，問題如下，請修正後**重新輸出完整的 JSON 陣列**（全部題目）：\n" + "\n".join("- " + f for f in feedback[:50])
    return s


def call(model, prompt, r):
    t0 = time.time()
    if model.startswith("gemini"):
        sys.path.insert(0, "/Users/Shared/antigravity-bridge")
        import agy_guard, agy_meter  # noqa: E402
        b = agy_guard.blocked()
        if b:
            return {"status": "NETWORK_BLOCKED", "error": b, "response": ""}, 0
        data = agy_meter.run(prompt, model=model, timeout=1200, note=f"emt-quiz 0930 擴充 r{r}")
        return data, round(time.time() - t0)
    # sonnet：claude -p 無工具
    # 延伸思考預設開啟時，3 題就吃掉 28k 輸出 token、6.5 分鐘，46 題會撞 32k 輸出上限而卡住；出題不需要，關掉
    import os
    env = dict(os.environ, MAX_THINKING_TOKENS="0")
    p = subprocess.run(["claude", "-p", "--model", "sonnet", "--tools", "", "--output-format", "json"],
                       input=prompt, capture_output=True, text=True, timeout=2400, env=env)
    try:
        j = json.loads(p.stdout)
    except Exception:
        return {"status": "LOCAL_ERROR", "error": p.stderr[-500:] or p.stdout[-500:], "response": ""}, round(time.time() - t0)
    return {"status": "SUCCESS" if not j.get("is_error") else "ERROR", "response": j.get("result", ""),
            "usage": j.get("usage"), "cost_usd": j.get("total_cost_usd"), "model_usage": j.get("modelUsage")}, round(time.time() - t0)


def run_model(model, rounds=2):
    n = len(slots_for(model))
    tag = f"{model}_p{PART[0]}" if PART else model
    (OUT / f"{tag}_prompt.txt").write_text(build_prompt(model), encoding="utf-8")
    log = {"model": model, "slots": n, "rounds": [], "started": datetime.now().astimezone().isoformat()}
    best, feedback = [], None
    for r in range(1, rounds + 1):
        data, secs = call(model, build_prompt(model, feedback), r)
        resp = data.get("response") or ""
        (OUT / f"{tag}_r{r}.txt").write_text(resp, encoding="utf-8")
        rec = {"round": r, "status": data.get("status"), "secs": secs, "resp_chars": len(resp),
               "usage": data.get("usage"), "cost_usd": data.get("cost_usd"), "model_usage": data.get("model_usage")}
        if data.get("status") in ("NETWORK_BLOCKED", "LOCAL_ERROR") or not resp:
            rec["error"] = data.get("error") or data.get("status")
            log["rounds"].append(rec)
            print(model, "呼叫失敗，停止：", rec["error"])
            break
        try:
            items = extract_json(resp)
            ok, errs, good = check_batch(items, need=int(n * 0.8))
        except Exception as e:
            ok, errs, good, items = False, [f"JSON 解析失敗：{e}"], [], []
        rec.update(ok=ok, n_items=len(items), n_good=len(good), errors=errs)
        log["rounds"].append(rec)
        print(f"{model} 第{r}回合：{'通過' if ok else '退回'} 合格 {len(good)}/{len(items)}；{errs[:4]}")
        if len(good) > len(best):
            best = good
        if ok:
            break
        feedback = errs
    (OUT / f"{tag}_final.json").write_text(json.dumps(best, ensure_ascii=False, indent=1), encoding="utf-8")
    log["n_final"] = len(best)
    (OUT / f"{tag}_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    return log


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "plan":
        for m in SCOPE:
            sl = slots_for(m)
            print(m, len(sl), Counter(t for _, t, _ in sl), Counter(d for _, _, d in sl))
    elif cmd == "prompt":
        print(build_prompt(sys.argv[2]))
    elif cmd == "run":
        for m in sys.argv[2:]:
            run_model(m)
    elif cmd == "runpart":  # runpart <模型> <第幾份> <共幾份>
        PART = (int(sys.argv[3]), int(sys.argv[4]))
        run_model(sys.argv[2])
    elif cmd == "merge":  # merge <模型> <共幾份>：各份 final 依序合併成 <模型>_final.json
        m, n = sys.argv[2], int(sys.argv[3])
        allq = []
        for i in range(1, n + 1):
            allq += json.loads((OUT / f"{m}_p{i}_final.json").read_text(encoding="utf-8"))
        (OUT / f"{m}_final.json").write_text(json.dumps(allq, ensure_ascii=False, indent=1), encoding="utf-8")
        print(m, len(allq))
