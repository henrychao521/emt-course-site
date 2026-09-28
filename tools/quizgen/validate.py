"""題目格式驗收：格式、出處 key 存在且屬於該知識點、答案在選項內、無重複、台灣用語粗篩。"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from sources import SOURCES  # noqa: E402

KN = {k["id"]: k for k in json.loads((ROOT / "docs/quiz-bank-2026-09-29/knowledge.json").read_text(encoding="utf-8"))}
TYPES = {"single", "tf", "scenario", "order"}
# 常見簡體字（繁體不使用），出現即判不合格
SIMP = set("这们说时对应该发电伤压设备处员级证书医护术训练课报资为吗么这过还没从样问题开关节头脑脉将让给东车实习择项简动体经带热烫")
CN_WORDS = ["视频", "打印", "质量好", "网络", "软件", "信息", "默认", "急救包扎", "激活", "三维", "屏幕", "鼠标"]
TF = ["正確", "錯誤"]


def norm(s):
    return re.sub(r"[\s，。、？！：；「」（）()?,.:;!\"'A-Da-d．]", "", s)


def extract_json(text):
    """回應裡可能夾著中斷的前一段輸出，逐一嘗試每個 [ 起點，取題數最多的完整 JSON 陣列。"""
    dec = json.JSONDecoder(strict=False)
    best = None
    # agy 偶爾回傳串流拼接錯誤：字串中斷後插入「\n[\n」再接下去；先嘗試原文，再嘗試修補版
    fixed = re.sub(r'"[^"\n]*\n\[\n', '', text)
    for m in list(re.finditer(r"\[", text)) + [None] + list(re.finditer(r"\[", fixed)):
        if m is None:
            text = fixed
            continue
        try:
            obj, _ = dec.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
            if best is None or len(obj) > len(best):
                best = obj
    if best is None:
        raise ValueError("找不到完整的 JSON 陣列")
    return best


def check_item(q):
    errs = []
    for f in ("type", "difficulty", "chapter", "kp", "stem", "explain", "sources"):
        if f not in q:
            errs.append(f"缺欄位 {f}")
    if errs:
        return errs
    if q["type"] not in TYPES:
        errs.append(f"type 不合法：{q['type']}")
    if q["difficulty"] not in (1, 2, 3):
        errs.append("difficulty 必須是 1、2、3")
    kps = q["kp"] if isinstance(q["kp"], list) else [q["kp"]]
    allowed = set()
    for k in kps:
        if k not in KN:
            errs.append(f"知識點 id 不存在：{k}")
        else:
            allowed |= set(KN[k]["sources"])
            if KN[k]["chapter"] != q["chapter"]:
                errs.append(f"chapter {q['chapter']} 與知識點 {k} 的章節 {KN[k]['chapter']} 不符")
    if not q["sources"]:
        errs.append("sources 不可為空")
    for s in q["sources"]:
        if s not in SOURCES:
            errs.append(f"出處 key 不存在：{s}")
        elif allowed and s not in allowed:
            errs.append(f"出處 {s} 不屬於知識點 {kps} 的出處 {sorted(allowed)}")
    if len(q["stem"]) < 8:
        errs.append("題幹太短")
    if len(q["explain"]) < 15:
        errs.append("解說太短")
    t = q["type"]
    if t in ("single", "scenario"):
        o = q.get("options")
        if not isinstance(o, list) or len(o) != 4:
            errs.append("單選／情境題必須正好 4 個選項")
        else:
            if len({norm(x) for x in o}) != 4:
                errs.append("選項重複")
            if any(re.match(r"^\s*[A-Da-d][\.．、)]", x) for x in o):
                errs.append("選項不要加 A. B. 字首")
            if any(re.search(r"以上皆(是|非)|皆正確|皆錯誤", x) for x in o):
                errs.append("不可用「以上皆是／皆非」")
            if q.get("answer") not in o:
                errs.append("answer 必須與某個選項文字完全相同")
    elif t == "tf":
        if q.get("options") != TF:
            errs.append('是非題 options 必須是 ["正確","錯誤"]')
        if q.get("answer") not in TF:
            errs.append("是非題 answer 必須是「正確」或「錯誤」")
    elif t == "order":
        it = q.get("items")
        if not isinstance(it, list) or not 3 <= len(it) <= 6:
            errs.append("排序題 items 必須 3 到 6 項（依正確順序）")
        elif len({norm(x) for x in it}) != len(it):
            errs.append("排序題 items 重複")
    blob = json.dumps(q, ensure_ascii=False)
    bad = sorted({c for c in blob if c in SIMP})
    if bad:
        errs.append("出現簡體字：" + "".join(bad))
    for w in CN_WORDS:
        if w in blob:
            errs.append(f"中國用語：{w}")
    return errs


def check_batch(items, need=0, mins=None):
    """回傳 (是否通過, 錯誤列表, 合格題目)。"""
    errs, good, seen = [], [], set()
    if not isinstance(items, list):
        return False, ["輸出不是 JSON 陣列"], []
    for i, q in enumerate(items, 1):
        if not isinstance(q, dict):
            errs.append(f"第{i}題不是物件")
            continue
        e = check_item(q)
        key = norm(q.get("stem", ""))
        if key in seen:
            e.append("與本批另一題題幹重複")
        seen.add(key)
        if e:
            errs.append(f"第{i}題（{q.get('stem','')[:20]}…）：" + "；".join(e))
        else:
            good.append(q)
    if need and len(good) < need:
        errs.append(f"合格題數 {len(good)} 少於要求 {need}")
    for t, n in (mins or {}).items():
        c = sum(1 for q in good if q["type"] == t)
        if c < n:
            errs.append(f"{t} 題型合格 {c} 題，少於要求 {n}")
    for d in (1, 2, 3):
        if good and not any(q["difficulty"] == d for q in good):
            errs.append(f"缺少難度 {d}")
    return not errs, errs, good
