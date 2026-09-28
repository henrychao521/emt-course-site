#!/usr/bin/env python3
"""檢查網站所有外部連結（curl -L），並產生 docs/SOURCES.md 與 docs/link-check.tsv。
law.moj.gov.tw 若憑證驗證失敗，改用 -k 重試並在結果註記。
用法：python3 tools/check_links.py
"""
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import SOURCES, ACCESSED  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def curl(url, insecure=False):
    cmd = ["curl", "-sL", "-o", "/dev/null", "-A", UA, "--max-time", "40", "-w", "%{http_code}", url]
    if insecure:
        cmd.insert(1, "-k")
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip() or "000", r.returncode


def check(url):
    code, rc = curl(url)
    note = ""
    if code != "200" and "law.moj.gov.tw" in url:
        code2, _ = curl(url, insecure=True)
        if code2 == "200":
            code, note = code2, "憑證驗證失敗，以 curl -k 取得"
    if code == "203" and "ncbi.nlm.nih.gov" in url:
        pmid = re.search(r"(\d{6,})", url).group(1)
        ec, _ = curl(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&rettype=abstract&retmode=text")
        note = f"NCBI 固定回 203（2xx，頁面內容正常）；同一筆書目以 E-utilities efetch 取得 {ec}"
    return url, code, note


def main():
    urls = set()
    for f in ROOT.glob("*.html"):
        for u in re.findall(r'href="(https?://[^"]+)"', f.read_text(encoding="utf-8")):
            urls.add(unescape(u))
    for v in SOURCES.values():
        urls.add(v[3])
    with ThreadPoolExecutor(6) as ex:
        res = sorted(ex.map(check, sorted(urls)))
    status = {u: (c, n) for u, c, n in res}
    bad = [(u, c) for u, c, n in res if c != "200" and not (c == "203" and "NCBI" in n)]

    (ROOT / "docs").mkdir(exist_ok=True)
    with open(ROOT / "docs" / "link-check.tsv", "w", encoding="utf-8") as fh:
        fh.write("status\tnote\turl\n")
        for u, c, n in res:
            fh.write(f"{c}\t{n}\t{u}\n")

    # 引用次數
    pages = {f.name: f.read_text(encoding="utf-8") for f in ROOT.glob("*.html")}
    lines = [
        "# 資料來源清單（SOURCES）",
        "",
        f"存取日期：{ACCESSED}。狀態欄為當日以 `curl -L`（瀏覽器 User-Agent）實測的 HTTP 狀態碼。",
        "此檔由 `tools/check_links.py` 產生；出處登錄表在 `tools/sources.py`。",
        "",
        "| 代碼 | 出處 | 發布機關 | 狀態 | 引用頁面 | 網址 |",
        "|---|---|---|---|---|---|",
    ]
    for k, (short, full, org, url, note) in SOURCES.items():
        c, n = status.get(url, ("?", ""))
        used = [p for p, t in pages.items() if url.replace("&", "&amp;") in t or url in t]
        st = c + (f"（{n}）" if n else "")
        extra = f"<br>備註：{note}" if note else ""
        lines.append(f"| {k} | {full}{extra} | {org} | {st} | {', '.join(sorted(used))} | {url} |")
    lines += [
        "",
        "## 查過但未採用的來源",
        "",
        "| 來源 | 原因 |",
        "|---|---|",
        "| 衛生福利部中央健康保險署「民眾緊急狀況處理」系列（nhi.gov.tw） | 網站以 Cloudflare 驗證頁擋下 curl（HTTP 403），無法依規定確認 200，改用消防署教科書與臺北市消防局 |",
        "| AHA 官網與 Circulation 期刊頁（cpr.heart.org、ahajournals.org） | 自動化存取回 403；僅以 PubMed 書目頁列為延伸閱讀，CPR 數字一律取衛福部摘要表 |",
        "| 臺北市政府消防局「常見問答－燒燙傷處置」（119.gov.taipei） | 頁面內文由 JavaScript 載入，無法以原始碼核對，改用同局防災教育雲同名文章 |",
        "| 臺中市沙鹿區衛生所「遠離燒燙傷」 | 沖水時間寫 15-30 分鐘，與臺北市消防局 20 至 30 分鐘不同；本站統一採消防局版本，不混用 |",
        "",
        "## 其他頁面內連結檢查",
        "",
        "| 狀態 | 網址 |",
        "|---|---|",
    ]
    src_urls = {v[3] for v in SOURCES.values()}
    for u, c, n in res:
        if u not in src_urls:
            lines.append(f"| {c}{'（' + n + '）' if n else ''} | {u} |")
    (ROOT / "docs" / "SOURCES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for u, c, n in res:
        print(c, n, u)
    print(f"\n共 {len(res)} 個連結，非 200：{len(bad)}")
    for u, c in bad:
        print("  ", c, u)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
