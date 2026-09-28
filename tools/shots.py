#!/usr/bin/env python3
"""每頁截圖（桌機 1440 寬、手機 375 寬；淺色＋深色）並檢查橫向溢出與 console 錯誤。
用法：python3 tools/shots.py http://localhost:8947
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["index.html", "emt.html", "where.html", "units.html", "first-aid.html", "quiz.html", "sources.html"]
VIEWS = {"desktop": dict(viewport={"width": 1440, "height": 900}),
         "mobile": dict(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True, device_scale_factor=2)}


async def main(base):
    out = ROOT / "docs" / "shots"
    out.mkdir(parents=True, exist_ok=True)
    problems = []
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        for vname, opts in VIEWS.items():
            for scheme in ("light", "dark"):
                ctx = await b.new_context(color_scheme=scheme, **opts)
                for pg in PAGES:
                    page = await ctx.new_page()
                    errs = []
                    page.on("console", lambda m, errs=errs: errs.append(m.text) if m.type == "error" else None)
                    page.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
                    await page.goto(f"{base}/{pg}", wait_until="networkidle")
                    ov = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                    if ov > 0:
                        problems.append(f"{vname}/{scheme} {pg} 橫向溢出 {ov}px")
                    if errs:
                        problems.append(f"{vname}/{scheme} {pg} console 錯誤：{errs}")
                    if scheme == "light" or pg in ("index.html", "first-aid.html"):
                        name = f"{vname}-{scheme}-{pg.replace('.html', '')}.png"
                        await page.screenshot(path=str(out / name), full_page=True)
                    await page.close()
                await ctx.close()
        await b.close()
    print("\n".join(problems) if problems else "無橫向溢出、無 console 錯誤")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8947")))
