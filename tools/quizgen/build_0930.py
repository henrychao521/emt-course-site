"""2026-09-30 題庫擴充組裝：候選題 → 自動驗收 → 套用逐題查證結論 → 去重 → 編號 q104 起 → 寫回題庫與 verified.json。

自動驗收（每題）：validate.check_item（格式、出處 key 存在且屬於知識點、答案在選項內、簡體字／中國用語）、
LINT（解說不得出現知識點代號、選項字母、出處代碼）、知識點必須 quiz_ok、與既有 98 題及其他新題的題幹去重
（正規化後完全相同＝重複；difflib 相似度 ≥ 0.72 列入近似清單，由主控逐一判定，判定寫在 verdicts_0930.py）。
既有 98 題補上 variant_group（預設＝第一個知識點；EXISTING_VG 可覆寫）。
用法：python3 tools/quizgen/build_0930.py [--dry]
"""
import copy, difflib, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "docs/quiz-bank-2026-09-30/raw"
OUTD = ROOT / "docs/quiz-bank-2026-09-30"
BANK = ROOT / "assets/quiz-bank.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))
from validate import KN, check_item, norm  # noqa: E402
from verify import LINT  # noqa: E402
from sources import SOURCES  # noqa: E402
from verdicts_0930 import VERDICT, CHECKED_OK, EXISTING_FIX, EXISTING_VG, METHOD, CLEAN_EXPL, GENERATION  # noqa: E402

SETS = [("GP", "gemini-3.1-pro-high"), ("GF", "gemini-3.8-flash-high"), ("SN", "claude-sonnet-4-6"), ("CL", "claude-opus-5-5")]
CH, TY, DF = ("ch1", "ch2", "ch3", "ch4"), ("single", "tf", "scenario", "order"), (1, 2, 3)
FIRST_NEW = 104
FAIL = []
KEEP = ("chapter", "type", "difficulty", "kp", "variant_group", "stem")


def load_cands():
    out = []
    for pre, model in SETS:
        f = RAW / f"{model}_final.json"
        if not f.exists():
            continue
        for i, q in enumerate(json.loads(f.read_text(encoding="utf-8")), 1):
            out.append((f"{pre}{i:02d}", model, {k: v for k, v in q.items() if k not in ("model", "slot")}))
    return out


def _model_stat(records, m):
    rs = [r for r in records if r["model"] == m]
    passed = [r for r in rs if r["verdict"] != "刪除" or r.get("trim")]
    return {"候選": len(rs), "查證通過": len(passed), "查證通過率": round(len(passed) / max(1, len(rs)), 3),
            "查證原樣正確": sum(1 for r in rs if r["verdict"] == "採用" or (r.get("trim") and "原樣正確" in r["note"])),
            "查證需修正": sum(1 for r in rs if r["verdict"] == "修正後採用" or (r.get("trim") and "修正後可用" in r["note"])),
            "查證刪除": sum(1 for r in rs if r["verdict"] == "刪除" and not r.get("trim")),
            "控制規模刪除": sum(1 for r in rs if r.get("trim")), "最終入庫": sum(1 for r in rs if r["verdict"] != "刪除")}


def matrix(qs):
    c = Counter((q["chapter"], q["type"], q["difficulty"]) for q in qs)
    return {f"{ch}|{t}|{d}": c[(ch, t, d)] for ch in CH for t in TY for d in DF}


def key(q):
    ans = " ".join(q["items"]) if q["type"] == "order" else q.get("answer", "")
    return norm(q["stem"]) + "|" + norm(ans)


def main(dry=False):
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    old = [q for q in bank["questions"] if int(q["id"][1:]) < FIRST_NEW]
    # 既有題：套用小修正、補 variant_group
    for q in old:
        if q["id"] in EXISTING_FIX:
            q.update(EXISTING_FIX[q["id"]][1])
        q["variant_group"] = EXISTING_VG.get(q["id"], q["kp"][0])
        e = check_item(q)
        if e:
            raise SystemExit(f"既有題 {q['id']} 驗收未過：{e}")
    cands = load_cands()
    ids = {c[0] for c in cands}
    for k in VERDICT:
        assert k in ids, f"查證表的 id 不存在：{k}"
    records, new = [], []
    pool = [(q["id"], key(q)) for q in old]
    near = []
    for cid, model, q in cands:
        rec = {"cand_id": cid, "model": model, "original": q, "auto_check": check_item(q)}
        v = VERDICT.get(cid, ("採用", "", CHECKED_OK.get(cid, "逐題核對原文，答案、干擾選項與解說均有原文依據"), None))
        rec.update(verdict=v[0], category=v[1], note=v[2])
        if v[2].startswith("控制題庫規模"):
            rec["trim"] = True
        if v[0] == "刪除":
            records.append(rec)
            continue
        fq = copy.deepcopy(q)
        if v[3]:
            fq.update(v[3])
        fq = CLEAN_EXPL(fq)
        fq["variant_group"] = fq["kp"][0] if fq.get("variant_group") not in fq["kp"] else fq["variant_group"]
        if fq["type"] == "tf":
            fq["options"] = ["正確", "錯誤"]
        errs = check_item(fq) + [m for r, m in LINT if r.search(fq["explain"] + fq["stem"])]
        bad_kp = [k for k in fq["kp"] if not KN[k]["quiz_ok"] and k not in ("W07",)]
        if bad_kp:
            errs.append(f"使用不出題的知識點 {bad_kp}")
        if fq["variant_group"] not in fq["kp"]:
            errs.append("variant_group 必須是題目的知識點之一")
        if errs:
            FAIL.append(f"{cid} 最終驗收未過：{errs}")
            continue
        k2 = key(fq)
        for pid, pk in pool:
            if pk == k2:
                raise SystemExit(f"{cid} 與 {pid} 題幹＋答案完全相同")
            r = difflib.SequenceMatcher(None, pk, k2).ratio()
            if r >= 0.72:
                near.append((cid, pid, round(r, 2)))
        pool.append((cid, k2))
        rec["checked_against"] = {s: SOURCES[s][1] for s in fq["sources"]}
        rec["final"] = fq
        records.append(rec)
        new.append((cid, model, fq))
    if FAIL:
        raise SystemExit("\n".join(FAIL))
    tord = {"single": 0, "tf": 1, "scenario": 2, "order": 3}
    new.sort(key=lambda x: (x[2]["chapter"], x[2]["difficulty"], tord[x[2]["type"]], x[0]))
    out = list(old)
    for n, (cid, model, q) in enumerate(new, FIRST_NEW):
        qid = f"q{n:03d}"
        for r in records:
            if r["cand_id"] == cid:
                r["bank_id"] = qid
        out.append({"id": qid, **{k: q[k] for k in KEEP},
                    **({"items": q["items"]} if q["type"] == "order" else {"options": q["options"], "answer": q["answer"]}),
                    "explain": q["explain"], "sources": q["sources"], "model": model, "cand_id": cid})
    # 最終全庫檢查
    seen = Counter(norm(q["stem"]) for q in out)
    assert not [s for s, c in seen.items() if c > 1], "題幹重複"
    vg = Counter(q["variant_group"] for q in out)
    summ = {
        "題庫總數": {"擴充前": len(old), "擴充後": len(out), "新增": len(new)},
        "各模型": {m: _model_stat(records, m) for _, m in SETS},
        "淘汰原因（查證未通過）": dict(Counter(r["category"] for r in records if r["verdict"] == "刪除" and not r.get("trim"))),
        "淘汰原因（控制題庫規模）": dict(Counter(r["category"] for r in records if r.get("trim"))),
        "修正類別": dict(Counter(r["category"] for r in records if r["verdict"] == "修正後採用")),
        "章節": dict(Counter(q["chapter"] for q in out)),
        "題型": dict(Counter(q["type"] for q in out)),
        "難度": dict(Counter(q["difficulty"] for q in out)),
        "variant_group": {"組數": len(vg), "題數分布": dict(sorted(Counter(vg.values()).items())),
                          "一組多題的組數": sum(1 for c in vg.values() if c > 1)},
        "近似題幹（主控已逐一判定）": near,
    }
    if dry:
        print(json.dumps({k: v for k, v in summ.items()}, ensure_ascii=False, indent=1))
        return
    bank["version"] = "2026-09-30"
    bank["questions"] = out
    BANK.write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")
    OUTD.joinpath("verified.json").write_text(json.dumps({
        "date": "2026-09-30", "task": "題庫擴充 98→約 200 題（同一知識點多情境變體＋variant_group）", "method": METHOD,
        "generation": GENERATION, "summary": summ, "matrix_before": matrix(old), "matrix_after": matrix(out),
        "existing_adjustments": {k: {"reason": v[0], "change": v[1]} for k, v in EXISTING_FIX.items()},
        "records": records}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summ.items() if k != "近似題幹（主控已逐一判定）"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main("--dry" in sys.argv)
