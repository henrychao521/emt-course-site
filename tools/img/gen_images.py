"""EMT 網站操作示意圖批次生圖驅動器（改自 rc-car-materials/dispatch/gen_images.py）

與參考版的差異（依規範第十一節補強）：
  1. 成功只看 steps 的最終 state 與檔案；每張圖的 ACTIVE→DONE/ERROR 兩筆會去重。
  2. 任何 429：立刻停、解析 quotaResetTimeStamp、印出台灣時間、結束碼 3，不重試。
  3. 驗收長寬比、Prompt 前 512 字元逐字比對。
  4. --max 限制本次最多幾張（預設 3，另一專案要用配額）。
用法：python3 gen_images.py 名稱1,名稱2 [--max 3]
"""
import sys, os, re, json, glob, shutil, time
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/Users/Shared/antigravity-bridge"); sys.path.insert(0, os.path.dirname(__file__))
import agy_meter as m
from image_spec import IMAGES, ASPECT
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "..", "images", "ai-raw")
TRACE = os.path.join(HERE, "traces")
BRAIN = os.path.expanduser("~/.gemini/antigravity-cli/brain")
TW = timezone(timedelta(hours=8))

def prompt_for(items):
    lines = [f"請依序呼叫 generate_image 工具，每一項呼叫一次，共 {len(items)} 次。",
             "規則：ImageName 參數用我給的名稱；Prompt 參數**逐字照抄**下面的英文提示詞，不要改寫、不要增刪。",
             "除了 generate_image 之外不要使用任何其他工具。全部完成後只回覆一行：DONE", ""]
    for n in items:
        lines += [f"### ImageName: {n}", IMAGES[n], ""]
    return "\n".join(lines)

def reset_time(err):
    m1 = re.search(r'quotaResetTimeStamp"?\s*:\s*"([^"]+)"', err or "")
    if m1:
        t = datetime.fromisoformat(m1.group(1).replace("Z", "+00:00"))
        return t.isoformat(), t.astimezone(TW).strftime("%Y-%m-%d %H:%M:%S（台灣）")
    m2 = re.search(r"reset after ([0-9hms]+)", err or "")
    return None, ("約 " + m2.group(1) + " 後") if m2 else "未知"

def aspect_ok(size, want):
    w, h = size
    return abs(w / h - (16 / 9)) < 0.08 if want == "16:9" else abs(w - h) <= 2

def main(names, cap):
    if len(names) > cap:
        sys.exit(f"本次要求 {len(names)} 張，超過上限 {cap}，拒絕送出。")
    t0 = time.time()
    r = m.run_with_tools(prompt_for(names), model="gemini-3.8-flash-high", timeout=2700,
                         print_timeout="40m", note="emt images " + ",".join(names))
    conv = r.get("conversation_id") or ""
    final, errors = {}, []
    for s in r.get("steps", []):
        if s.get("tool") != "generate_image":
            continue
        name = (s.get("params") or {}).get("ImageName")
        if s.get("state") in ("DONE", "ERROR"):
            final[name] = s                                   # 去重：只留最終狀態
        if s.get("state") == "ERROR":
            errors.append((name, s.get("error") or ""))
    out = {"conv": conv, "status": r.get("status"), "secs": round(time.time() - t0),
           "agy_response_ignored": (r.get("response") or "")[:200], "items": {}, "quota": None}
    hit429 = [e for e in errors if "429" in e[1] or "RESOURCE_EXHAUSTED" in e[1]]
    if hit429:
        iso, tw = reset_time(hit429[0][1])
        out["quota"] = {"hit": True, "reset_utc": iso, "reset_tw": tw}
    for n in names:
        s = final.get(n)
        if not s:
            out["items"][n] = {"ok": False, "why": "沒有任何最終狀態的 generate_image 呼叫"}; continue
        if s["state"] == "ERROR":
            out["items"][n] = {"ok": False, "why": (s.get("error") or "")[:160].replace("\n", " ")}; continue
        files = sorted([f for f in glob.glob(os.path.join(BRAIN, conv, "*.*")) if os.path.basename(f).lower().startswith(n.lower() + "_")], key=os.path.getmtime)  # ImageName 會被轉小寫
        if not files:
            out["items"][n] = {"ok": False, "why": "state=DONE 但找不到輸出檔"}; continue
        dst = os.path.join(RAW, n + os.path.splitext(files[-1])[1])
        if os.path.exists(dst):                                # 原圖不覆寫，保留追溯
            dst = os.path.splitext(dst)[0] + time.strftime("_%H%M%S") + os.path.splitext(dst)[1]
        shutil.copy2(files[-1], dst)
        size = Image.open(dst).size
        sent = (s.get("params") or {}).get("Prompt", "")
        out["items"][n] = {"ok": True, "file": dst, "size": size,
                           "aspect_ok": aspect_ok(size, ASPECT[n]),
                           "prompt_verbatim_512": sent.rstrip("…").strip()[:512] == IMAGES[n][:512].strip()[:len(sent.rstrip("…").strip()[:512])]}
    os.makedirs(TRACE, exist_ok=True); path = os.path.join(TRACE, "gen_trace_" + time.strftime("%m%d_%H%M%S") + f"_{os.getpid()}.json")
    json.dump({**out, "steps": [{k: v for k, v in st.items() if k != "output"} for st in r.get("steps", [])]},
              open(path, "w"), ensure_ascii=False, indent=1, default=str)
    ok = [n for n, v in out["items"].items() if v["ok"]]
    print(f"成功 {len(ok)} / {len(names)}　耗時 {out['secs']} 秒　軌跡 {os.path.basename(path)}")
    for n, v in out["items"].items():
        print("  ", n, "→", (f"{v['size']} 長寬比{'✓' if v['aspect_ok'] else '✗'} 逐字{'✓' if v['prompt_verbatim_512'] else '✗'}" if v["ok"] else v["why"]))
    print("   agy 回應（不採信）：", repr(out["agy_response_ignored"][:60]))
    if out["quota"]:
        print(f"429 配額用盡 → 停止，不重試。重置時間：{out['quota']['reset_tw']}")
        sys.exit(3)

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cap = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 3
    main(args[0].split(",") if args else list(IMAGES), cap)
