#!/usr/bin/env python3
"""把 src/*.html 的主文套上共用書眉、目錄、聲明與頁尾，輸出到網站根目錄。
主文中 {{c:ID}} 或 {{c:ID|文字}} 會展開成出處連結；{{refs}} 展開成完整資料來源清單。
作答紀錄接收網址與口令在 tools/site_config.json（SHEET_ENDPOINT 空字串＝不送）；
環境變數 EMT_SHEET_ENDPOINT／EMT_SHEET_TOKEN 可暫時覆蓋（測試用）。
用法：python3 tools/build.py
"""
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import SOURCES, ACCESSED  # noqa: E402

PAGES = [
    # 檔名, 章號, 目錄短名, <title>, 說明
    ("index.html", "", "導讀", "EMT 課程導讀", "高中生活科技課：從工場安全延伸認識初級救護技術員（EMT-1）課程"),
    ("emt.html", "一", "EMT 是什麼", "EMT 是什麼", "初級、中級、高級救護技術員的法源、報名資格、訓練時數、證照效期與繼續教育"),
    ("where.html", "二", "哪裡上課", "哪裡上 EMT 課", "在台灣可以查詢與報名初級救護技術員訓練的官方管道"),
    ("units.html", "三", "課程單元", "EMT-1 課程單元", "依救護技術員管理辦法附表一整理的初級救護技術員訓練課程模組與時數"),
    ("first-aid.html", "四", "工場傷害處置", "工場傷害處置", "割傷出血、燙傷、夾壓傷、異物入眼、觸電、昏倒的第一時間處置"),
    ("quiz.html", "五", "小測驗", "EMT 觀念測驗", "從題庫依章節與難度平衡隨機抽十題的觀念測驗，每題附解說與出處；另有教師版全部題目"),
    ("sources.html", "六", "資料來源", "資料來源", "本站引用的全部法規、指引與官方資料，含存取日期"),
]

CITE_RE = re.compile(r"\{\{c:([A-Z0-9]+)(?:\|([^}]*))?\}\}")


def cite(m):
    return cite_html(m.group(1), m.group(2))


def cite_html(sid, text=None):
    if sid not in SOURCES:
        raise SystemExit(f"未登錄的出處代碼：{sid}")
    short, full, org, url, _ = SOURCES[sid]
    label = text or short
    return (f'<a class="cite" href="{html.escape(url)}" target="_blank" rel="noopener" '
            f'title="{html.escape(full)}">{html.escape(label)}</a>')


def refs_html():
    groups = [
        ("法規與課程基準（全國法規資料庫）", lambda k: k.startswith(("EMSA", "EMTR", "T", "SCH")) and not k.startswith(("TB", "TP"))),
        ("衛生福利部", lambda k: k in ("CPR21", "DOMA", "EMS", "AEDNET", "AEDEDU", "VID")),
        ("內政部消防署（2025 救護技術員教科書）", lambda k: k.startswith(("NFA", "TB"))),
        ("縣市消防局", lambda k: k.startswith(("TP", "KH"))),
        ("中華民國紅十字會", lambda k: k.startswith("RC")),
        ("醫學中心衛教（臺大醫院）", lambda k: k.startswith("NTUH")),
        ("學會與國際指引（延伸閱讀）", lambda k: k in ("SEM", "AHA25")),
    ]
    out = []
    for title, pred in groups:
        out.append(f'<h3>{html.escape(title)}</h3>\n<ol class="refs">')
        for k, (short, full, org, url, note) in SOURCES.items():
            if not pred(k):
                continue
            note_html = f"；{html.escape(note)}" if note else ""
            out.append(
                f'<li id="ref-{k}">{html.escape(full)}<span class="meta">{html.escape(org)}｜存取日期 {ACCESSED}{note_html}</span>'
                f'<a class="url" href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(url)}</a></li>')
        out.append("</ol>")
    return "\n".join(out)


HEAD = """<!doctype html>
<html lang="zh-Hant-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='2' fill='%231f4e79'/%3E%3Cpath d='M6 3h4v3h3v4h-3v3H6v-3H3V6h3z' fill='%23f7f4ec'/%3E%3C/svg%3E">
<script>try{{var t=localStorage.getItem("emt-theme");if(t==="dark"||t==="light")document.documentElement.setAttribute("data-theme",t);}}catch(e){{}}</script>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<a class="skip" href="#main">跳到主要內容</a>
<header class="masthead">
  <div class="masthead-inner">
    <a class="brand" href="index.html">從工場安全到 EMT-1<small>高中生活科技｜初級救護技術員課程介紹</small></a>
    <button class="theme-btn" id="theme-btn" type="button">深淺色</button>
  </div>
  <nav class="toc" aria-label="章節">
    <ol>
{nav}
    </ol>
  </nav>
</header>
<div class="notice" role="note"><p><strong>重要聲明</strong>　本網站是課程介紹與觀念教學，<strong>不能取代實際受訓</strong>；急救技能需經合格課程的實作訓練。遇到緊急狀況請立即撥打 119，並聽從 119 執勤人員指示。</p></div>
<main id="main" class="page">
"""

FOOT = """{pager}
</main>
<footer class="colophon">
  <div>
    <p>本站內容整理自衛生福利部、內政部消防署、全國法規資料庫、縣市消防局、中華民國紅十字會與臺大醫院健康電子報公開資料，所有具體數字皆附出處連結；資料存取日期 {accessed}。法規或指引若有修正，以主管機關最新公告為準。</p>
    <p>本網站是課程介紹與觀念教學，不能取代實際受訓；急救技能需經合格課程實作訓練。</p>
  </div>
</footer>
<script src="assets/app.js"></script>
</body>
</html>
"""


def nav_html(active):
    items = []
    for fn, no, short, *_ in PAGES:
        cur = ' aria-current="page"' if fn == active else ""
        n = f'<span class="n">{no}</span>' if no else ""
        items.append(f'      <li><a href="{fn}"{cur}>{n}{short}</a></li>')
    return "\n".join(items)


def pager_html(i):
    prev = PAGES[i - 1] if i > 0 else None
    nxt = PAGES[i + 1] if i + 1 < len(PAGES) else None
    left = f'<a href="{prev[0]}">← {prev[1] + "、" if prev[1] else ""}{prev[2]}</a>' if prev else "<span></span>"
    right = f'<a href="{nxt[0]}">{nxt[1]}、{nxt[2]} →</a>' if nxt else "<span></span>"
    return f'<nav class="pager" aria-label="上下頁">{left}{right}</nav>'


CH_NAME = {"ch1": "第一章 EMT 是什麼", "ch2": "第二章 哪裡上課", "ch3": "第三章 課程單元", "ch4": "第四章 工場傷害處置"}
TYPE_NAME = {"single": "單選", "tf": "是非", "scenario": "情境判斷", "order": "排序"}
DIFF_NAME = {1: "基礎", 2: "進階", 3: "挑戰"}


def load_bank():
    p = ROOT / "assets" / "quiz-bank.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"questions": []}


def quiz_all_html(bank):
    """教師版：全部題目靜態輸出（免 JavaScript 也能看、能列印）。"""
    esc = html.escape
    out = []
    for ch, name in CH_NAME.items():
        qs = [q for q in bank["questions"] if q["chapter"] == ch]
        if not qs:
            continue
        out.append(f'<h3 class="bank-ch">{esc(name)}（{len(qs)} 題）</h3>')
        for q in qs:
            meta = f'{TYPE_NAME[q["type"]]}｜{DIFF_NAME[q["difficulty"]]}（難度 {q["difficulty"]}）'
            out.append(f'<article class="qa" id="{esc(q["id"])}"><h4><span class="qid">{esc(q["id"])}</span>{esc(q["stem"])}</h4>'
                       f'<p class="qa-meta">{esc(meta)}</p>')
            if q["type"] == "order":
                out.append('<p class="qa-ans">正確順序：</p><ol class="qa-order">'
                           + "".join(f"<li>{esc(x)}</li>" for x in q["items"]) + "</ol>")
            elif q["type"] == "tf":
                out.append(f'<p class="qa-ans">答案：<strong>{esc(q["answer"])}</strong></p>')
            else:
                lis = []
                for o in q["options"]:
                    if o == q["answer"]:
                        lis.append(f'<li class="is-ans"><strong>{esc(o)}</strong>（答案）</li>')
                    else:
                        lis.append(f"<li>{esc(o)}</li>")
                out.append('<ol class="qa-opts" type="A">' + "".join(lis) + "</ol>")
            cites = "".join(cite_html(s) for s in q["sources"])
            out.append(f'<div class="explain"><p>{esc(q["explain"])}</p><p>{cites}</p></div></article>')
    return "\n".join(out)


def quiz_stats(bank):
    from collections import Counter
    qs = bank["questions"]
    c = Counter(q["type"] for q in qs)
    d = Counter(q["difficulty"] for q in qs)
    return ("題型：" + "、".join(f"{TYPE_NAME[t]} {c[t]}" for t in TYPE_NAME if c[t])
            + "；難度：" + "、".join(f"{DIFF_NAME[k]} {d[k]}" for k in (1, 2, 3) if d[k]) + "。")


def site_config():
    p = ROOT / "tools" / "site_config.json"
    cfg = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    ep = os.environ.get("EMT_SHEET_ENDPOINT", cfg.get("SHEET_ENDPOINT", "")).strip()
    tok = os.environ.get("EMT_SHEET_TOKEN", cfg.get("SHEET_TOKEN", "")).strip()
    if ep and not re.match(r"^https?://[^\s\"'<>]+$", ep):
        raise SystemExit(f"SHEET_ENDPOINT 格式不對：{ep}")
    if not re.match(r"^[\x21-\x7e]{0,64}$", tok):
        raise SystemExit("SHEET_TOKEN 只能是 64 字以內的英數符號（不可有空白或中文）")
    return {"SHEET_ENDPOINT": ep, "SHEET_TOKEN": tok}


def q_hash(q):
    """題目內容指紋：題幹、選項、答案、排序項目有任何改動，指紋就會變，分析時新舊版分開算。"""
    core = {k: q.get(k) for k in ("type", "stem", "options", "answer", "items")}
    return hashlib.sha1(json.dumps(core, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:8]


REPORT_NOTE_OFF = "成果報告（含你填的班級座號）只在你的瀏覽器裡產生，不會上傳。"
REPORT_NOTE_ON = ("成果報告圖片只在你的瀏覽器裡產生，不會上傳；但按下「成果報告產生」時，你填的班級與座號會和這一組的作答紀錄一起送給老師"
                  "（每組只送第一次產生報告時填的班級座號）。")


def sheet_notes(cfg):
    """回傳（學生頁說明、成果報告說明、教師版資料流向）。"""
    if cfg["SHEET_ENDPOINT"]:
        student = ('<p class="data-note" id="data-note"><strong>作答紀錄說明</strong>　完成一組後，會送出各題對錯與所選答案給老師；'
                   '<strong>按「成果報告產生」時，填寫的班級座號也會一起送給老師</strong>，用於學習紀錄與題目分析。'
                   '成果報告圖片本身只在你的瀏覽器裡產生，不會上傳。</p>')
        teacher = ('<p class="data-flow">資料流向：學生每完成一組 10 題，網站會把各題題號、對錯與所選答案送到老師的 Google 試算表'
                   '（選擇題記錄選項代號，對應本頁各題 A、B、C、D 的順序；是非題記錄「正確／錯誤」；排序題記錄依序點選的步驟序號）。'
                   '學生若按「成果報告產生」，當時填的班級與座號會再送一次，補進同一組的紀錄（每組只收第一次）；沒有產生報告的組別不含班級座號。'
                   '成果報告圖片只在學生的瀏覽器裡產生，不會上傳。</p>')
        report = REPORT_NOTE_ON
    else:
        student = ""
        teacher = '<p class="data-flow">資料流向：目前未設定作答紀錄接收網址，網站不會送出任何作答資料；成果報告只在學生的瀏覽器裡產生。</p>'
        report = REPORT_NOTE_OFF
    return student, report, teacher


OPT_CODES = "ABCDEF"


def bank_index(bank):
    """給 Apps Script importBank() 用的題庫索引：題號→題幹、教師版順序的選項代號、正解代號。"""
    out = []
    for q in bank["questions"]:
        e = {"id": q["id"], "h": q_hash(q), "type": q["type"], "chapter": q["chapter"],
             "difficulty": q["difficulty"], "stem": q["stem"]}
        if q["type"] == "order":
            e["options"] = []
            e["steps"] = list(q["items"])
            e["answer"] = ">".join(str(i + 1) for i in range(len(q["items"])))
        elif q["type"] == "tf":
            e["options"] = [{"code": o, "text": o} for o in q["options"]]
            e["answer"] = q["answer"]
        else:
            if len(q["options"]) > len(OPT_CODES):
                raise SystemExit(f"{q['id']} 選項超過 {len(OPT_CODES)} 個")
            e["options"] = [{"code": OPT_CODES[i], "text": o} for i, o in enumerate(q["options"])]
            e["answer"] = OPT_CODES[q["options"].index(q["answer"])]
        out.append(e)
    return {"version": str(bank.get("version", "")), "count": len(out), "questions": out}


def quiz_config(cfg):
    txt = json.dumps(cfg, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" id="quiz-config">{txt}</script>'


def quiz_data(bank):
    used = sorted({s for q in bank["questions"] for s in q["sources"]})
    for s in used:
        if s not in SOURCES:
            raise SystemExit(f"題庫用了未登錄的出處代碼：{s}")
    data = {"questions": [{k: q[k] for k in ("id", "chapter", "type", "difficulty", "kp", "variant_group", "stem",
                                                "options", "answer", "items", "explain", "sources") if k in q} | {"h": q_hash(q)} for q in bank["questions"]],
            "version": str(bank.get("version", "")),
            "sources": {s: [SOURCES[s][0], SOURCES[s][3], SOURCES[s][1]] for s in used}}
    txt = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" id="quiz-bank">{txt}</script>'


def main():
    bank = load_bank()
    cfg = site_config()
    student_note, report_note, teacher_note = sheet_notes(cfg)
    (ROOT / "assets" / "quiz-bank-index.json").write_text(
        json.dumps(bank_index(bank), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("寫出 assets/quiz-bank-index.json")
    for i, (fn, no, short, title, desc) in enumerate(PAGES):
        body = (ROOT / "src" / fn).read_text(encoding="utf-8")
        body = body.replace("{{refs}}", refs_html())
        if fn == "quiz.html":
            body = (body.replace("{{quizall}}", quiz_all_html(bank)).replace("{{quizdata}}", quiz_data(bank))
                    .replace("{{quizcount}}", str(len(bank["questions"]))).replace("{{quizstats}}", quiz_stats(bank))
                    .replace("{{sheetnote}}", student_note).replace("{{reportnote}}", report_note).replace("{{dataflow}}", teacher_note)
                    .replace("{{quizconfig}}", quiz_config(cfg)))
        body = CITE_RE.sub(cite, body)
        if "{{" in body:
            raise SystemExit(f"{fn} 有未展開的樣板標記")
        page = (HEAD.format(title=html.escape(title), desc=html.escape(desc), nav=nav_html(fn))
                + body
                + FOOT.format(pager=pager_html(i), accessed=ACCESSED))
        (ROOT / fn).write_text(page, encoding="utf-8")
        print("寫出", fn)


if __name__ == "__main__":
    main()
