"""異家族交叉檢查：把主控（claude-opus-5-5）自出的題目交給 gemini-3.1-pro-high 獨立挑錯。
提示只含網站原句（知識點 site_text）與題目本身，不含外部原文。模型的意見只當線索，由主控回原文判定。
用法：python3 tools/quizgen/crosscheck_0930.py
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "docs/quiz-bank-2026-09-30/raw"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "/Users/Shared/antigravity-bridge")
from validate import KN, extract_json  # noqa: E402
import agy_guard, agy_meter  # noqa: E402

items = json.loads((RAW / "claude-opus-5-5_final.json").read_text(encoding="utf-8"))
kps = sorted({k for q in items for k in q["kp"]})
kn = "\n".join(f"- [{k}] {KN[k]['site_text']}" for k in kps)
qs = []
for i, q in enumerate(items, 1):
    body = " → ".join(q["items"]) if q["type"] == "order" else "／".join(("＊" if o == q["answer"] else "") + o for o in q["options"])
    qs.append(f"{i}. [{q['type']}] {q['stem']}\n   選項（＊＝答案；排序題為正確順序）：{body}\n   解說：{q['explain']}")
prompt = f"""你是嚴格的命題審查委員。下面是一個高中課程網站的知識點原句，以及另一位命題者根據這些原句出的題目。
請**獨立**逐題檢查，只找真正的問題：
(a) 正確答案沒有被原句支持；(b) 某個干擾選項依原句其實也可能是對的，或無法判定對錯；(c) 解說加了原句沒有的數字、理由或推論；
(d) 題幹情境不合理、與原句矛盾，或可能誘導危險行為；(e) 排序題的順序沒有原句依據。
沒有問題的題目不要列出。不要寫任何檔案，只輸出一個 JSON 陣列：[{{"no":題號,"problem":"a|b|c|d|e","detail":"具體說明"}}]；全部沒問題就輸出 []。

# 知識點原句
{kn}

# 題目
{chr(10).join(qs)}
"""
if agy_guard.blocked():
    raise SystemExit(f"agy_guard 擋下：{agy_guard.blocked()}")
(RAW / "crosscheck_prompt.txt").write_text(prompt, encoding="utf-8")
d = agy_meter.run(prompt, model="gemini-3.1-pro-high", timeout=900, note="emt-quiz 0930 交叉檢查主控自出題")
resp = d.get("response") or ""
(RAW / "crosscheck_gemini-3.1-pro-high.txt").write_text(resp, encoding="utf-8")
try:
    out = extract_json(resp) if resp.strip() != "[]" else []
except ValueError:
    out = []
(RAW / "crosscheck_gemini-3.1-pro-high.json").write_text(json.dumps({"status": d.get("status"), "usage": d.get("usage"), "findings": out}, ensure_ascii=False, indent=1), encoding="utf-8")
print(d.get("status"), json.dumps(out, ensure_ascii=False, indent=1))
