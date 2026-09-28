#!/usr/bin/env python3
"""把 src/*.html 的主文套上共用書眉、目錄、聲明與頁尾，輸出到網站根目錄。
主文中 {{c:ID}} 或 {{c:ID|文字}} 會展開成出處連結；{{refs}} 展開成完整資料來源清單。
用法：python3 tools/build.py
"""
import html
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
    ("quiz.html", "五", "小測驗", "EMT 觀念測驗", "十題觀念測驗，每題附解說與出處"),
    ("sources.html", "六", "資料來源", "資料來源", "本站引用的全部法規、指引與官方資料，含存取日期"),
]

CITE_RE = re.compile(r"\{\{c:([A-Z0-9]+)(?:\|([^}]*))?\}\}")


def cite(m):
    sid, text = m.group(1), m.group(2)
    if sid not in SOURCES:
        raise SystemExit(f"未登錄的出處代碼：{sid}")
    short, full, org, url, _ = SOURCES[sid]
    label = text or short
    return (f'<a class="cite" href="{html.escape(url)}" target="_blank" rel="noopener" '
            f'title="{html.escape(full)}">{html.escape(label)}</a>')


def refs_html():
    groups = [
        ("法規與課程基準（全國法規資料庫）", lambda k: k.startswith(("EMSA", "EMTR", "T", "SCH")) and not k.startswith(("TB", "TP"))),
        ("衛生福利部", lambda k: k in ("CPR21", "DOMA", "EMS", "AEDNET", "VID")),
        ("內政部消防署（2025 救護技術員教科書）", lambda k: k.startswith(("NFA", "TB"))),
        ("縣市消防局", lambda k: k.startswith(("TP", "KH"))),
        ("中華民國紅十字會", lambda k: k.startswith("RC")),
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
    <p>本站內容整理自衛生福利部、內政部消防署、全國法規資料庫、縣市消防局與中華民國紅十字會公開資料，所有具體數字皆附出處連結；資料存取日期 {accessed}。法規或指引若有修正，以主管機關最新公告為準。</p>
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


def main():
    for i, (fn, no, short, title, desc) in enumerate(PAGES):
        body = (ROOT / "src" / fn).read_text(encoding="utf-8")
        body = body.replace("{{refs}}", refs_html())
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
