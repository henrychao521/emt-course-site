"""（改自 rc-car-materials/dispatch/gen_ref.py）帶參考圖的生圖驅動器：generate_image 的 ImagePaths（最多 3 張）。
成功只看 steps 裡該 ImageName 的最終 state 與檔案；軌跡存 gen_ref_trace_*.json。遇 429 停。"""
import sys, os, json, glob, shutil, time, re
sys.path.insert(0, "/Users/Shared/antigravity-bridge")
import agy_meter as m
BRAIN = os.path.expanduser("~/.gemini/antigravity-cli/brain")
RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "images", "ai-raw")
JOBS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref_jobs.json"), encoding="utf-8"))

def wrap(items):
    L = [f"請依序呼叫 generate_image 工具，每一項呼叫一次，共 {len(items)} 次。",
         "規則：ImageName 用我給的名稱；Prompt 參數逐字照抄下面的英文提示詞，不要改寫、不要增刪；",
         "ImagePaths 參數一定要帶，內容就是我列出的絕對路徑（照順序）；AspectRatio 用我給的值。",
         "除了 generate_image 之外不要使用任何其他工具。全部完成後只回覆一行：DONE", ""]
    for j in items:
        L += [f"### ImageName: {j['name']}", f"AspectRatio: {j['aspect']}", "ImagePaths:"] + [f"- {p}" for p in j["refs"]] + ["Prompt:", j["prompt"], ""]
    return "\n".join(L)

names = sys.argv[1:]
items = [dict(JOBS[n], name=n) for n in names]
for j in items:
    assert len(j["prompt"]) <= 500, (j["name"], len(j["prompt"]))
    assert all(os.path.isabs(p) and os.path.exists(p) for p in j["refs"]) and len(j["refs"]) <= 3, j["name"]
t = time.time()
r = m.run_with_tools(wrap(items), model="gemini-3.8-flash-high", timeout=2700, print_timeout="40m", note="emt ref " + ",".join(names))
conv = r.get("conversation_id") or ""
final = {}
for s in r.get("steps", []):
    if s.get("tool") == "generate_image" and s.get("state") in ("DONE", "ERROR"):
        final[((s.get("params") or {}).get("ImageName") or "").lower()] = s
res, hit = {}, None
for j in items:
    n = j["name"]; s = final.get(n.lower()); prm = (s or {}).get("params") or {}
    err = str((s or {}).get("error") or "")
    if s and s["state"] == "ERROR" and ("429" in err or "RESOURCE_EXHAUSTED" in err):
        hit = re.search(r"quotaResetTimeStamp\\?\"?:\s*\\?\"([^\"\\]+)", err); res[n] = {"ok": False, "why": "429"}; continue
    if not s or s["state"] != "DONE":
        res[n] = {"ok": False, "why": "沒有成功的呼叫 " + err[:200]}; continue
    fs = sorted([f for f in glob.glob(os.path.join(BRAIN, conv, "*")) if os.path.basename(f).lower().startswith(n.lower() + "_")], key=os.path.getmtime)
    if not fs:
        res[n] = {"ok": False, "why": "DONE 但找不到檔案"}; continue
    dst = os.path.join(RAW, n + os.path.splitext(fs[-1])[1])
    if os.path.exists(dst):
        dst = os.path.join(RAW, f"{n}_{time.strftime('%H%M%S')}{os.path.splitext(fs[-1])[1]}")
    shutil.copy2(fs[-1], dst)
    from PIL import Image
    prm = dict(prm)
    tf = os.path.join(BRAIN, conv, ".system_generated", "logs", "transcript_full.jsonl")
    if os.path.exists(tf):   # stream-json 只列 ImageName/Prompt，完整參數要從 agy 自己的逐字紀錄讀
        for line in open(tf, encoding="utf-8"):
            try: ev = json.loads(line)
            except Exception: continue
            for tc in ev.get("tool_calls") or []:
                a = tc.get("args") or {}
                if tc.get("name") == "generate_image" and (a.get("ImageName") or "").lower() == n.lower():
                    prm.update(a)
    res[n] = {"ok": True, "file": dst, "size": Image.open(dst).size,
              "refs_sent": prm.get("ImagePaths"), "refs_match": prm.get("ImagePaths") == j["refs"],
              "aspect_sent": prm.get("AspectRatio"), "prompt_match": (prm.get("Prompt") or "").strip()[:500] == j["prompt"].strip()[:500]}
trace = {"conv": conv, "secs": round(time.time() - t), "agy_response_ignored": r.get("response"), "items": res,
         "quota_hit": hit.group(1) if hit else None,
         "steps": [{k: v for k, v in st.items() if k != "output"} for st in r.get("steps", [])]}
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traces", "gen_ref_trace_" + time.strftime("%m%d_%H%M%S") + f"_{os.getpid()}.json")
json.dump(trace, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str)); print("TRACE", path)
sys.exit(3 if hit else 0)
