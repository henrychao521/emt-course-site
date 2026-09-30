#!/usr/bin/env python3
"""把 AI 原圖（images/ai-raw/）加上本站後製的中文標註、編號、箭頭，輸出網頁用 WebP（assets/img/）。

原則：AI 只負責「像」；文字、編號、箭頭、方向一律在這裡畫，保證正確。
座標以原圖 1376×768 為準，最後縮到 OUT_W 寬。
用法：python3 tools/img/compose.py [名稱 ...]
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW = os.path.join(ROOT, "images", "ai-raw")
OUT = os.path.join(ROOT, "assets", "img")
OUT_W = 1100
Q = 68

FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
NAVY = (31, 78, 121)
GREEN = (47, 93, 52)
RED = (155, 44, 31)
AMBER = (138, 90, 0)
WHITE = (255, 255, 255)
INK = (31, 35, 40)

# 驗收通過的原圖（同名重生時檔名帶時間戳，這裡指定採用哪一張）
APPROVED = {
    "bleed_press": "bleed_press_184920.jpg",  # R2-20 徒手版（舊版戴手套：bleed_press_025856.jpg）
    "burn_cool": "burn_cool.jpg",
    "amputation_bag": "amputation_bag.jpg",
    "shock_broom": "shock_broom_025728.jpg",
    "cpr_posture": "cpr_posture_025728.jpg",
    "aed_pads": "aed_pads.jpg",
}

_fc = {}


def font(s):
    if s not in _fc:
        _fc[s] = ImageFont.truetype(FONT, s)
    return _fc[s]


def badge(d, xy, n, color=NAVY, r=30):
    x, y = xy
    d.ellipse((x - r, y - r, x + r, y + r), fill=color)
    d.text((x, y + 1), str(n), font=font(int(r * 1.35)), fill=WHITE, anchor="mm")


def label(d, xy, text, color=NAVY, size=38, anchor="lm", pad=(16, 10), lpad=0):
    """白底圓角標籤，文字用主題色。lpad：左側再留空間放編號圓點。"""
    f = font(size)
    l, t, r, b = d.textbbox(xy, text, font=f, anchor=anchor)
    box = (l - pad[0] - lpad, t - pad[1], r + pad[0], b + pad[1])
    d.rounded_rectangle((box[0] + 3, box[1] + 4, box[2] + 3, box[3] + 4), 12, fill=(0, 0, 0, 70))
    d.rounded_rectangle(box, 12, fill=(255, 255, 255, 238), outline=color, width=4)
    d.text(xy, text, font=f, fill=color, anchor=anchor)
    return box


def line(d, p1, p2, color=NAVY, w=6, dot=True):
    d.line((p1, p2), fill=WHITE, width=w + 6)
    d.line((p1, p2), fill=color, width=w)
    if dot:
        x, y = p2
        d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=WHITE)
        d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=color)


def arrow(d, p1, p2, color=NAVY, w=10, head=30):
    import math
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    base = (p2[0] - head * math.cos(ang), p2[1] - head * math.sin(ang))
    left = (base[0] + head * 0.6 * math.sin(ang), base[1] - head * 0.6 * math.cos(ang))
    right = (base[0] - head * 0.6 * math.sin(ang), base[1] + head * 0.6 * math.cos(ang))
    for c, ww, grow in ((WHITE, w + 8, 5), (color, w, 0)):
        d.line((p1, base), fill=c, width=ww)
        if grow:
            g = [(p2[0] + grow * math.cos(ang), p2[1] + grow * math.sin(ang)),
                 (left[0] - grow * math.cos(ang), left[1] - grow * math.sin(ang)),
                 (right[0] - grow * math.cos(ang), right[1] - grow * math.sin(ang))]
            d.polygon(g, fill=c)
        else:
            d.polygon([p2, left, right], fill=c)


def callout(d, n, text_xy, target, text, color=NAVY, anchor="lm", size=38):
    """編號＋標籤＋引線：引線從標籤邊緣畫到目標點。"""
    r = int(size * 0.5)
    lp = 2 * r + 8
    text_xy = (text_xy[0] + lp, text_xy[1])  # 座標指的是整個標籤左緣
    box = label(d, text_xy, text, color=color, size=size, anchor=anchor, lpad=lp)
    # 引線起點取標籤最靠近目標的邊
    cx = min(max(target[0], box[0]), box[2])
    cy = min(max(target[1], box[1]), box[3])
    line(d, (cx, cy), target, color=color)
    label(d, text_xy, text, color=color, size=size, anchor=anchor, lpad=lp)  # 標籤蓋在引線上
    badge(d, (box[0] + 12 + r, (box[1] + box[3]) / 2), n, color=color, r=r)


def band(im, text, color=NAVY, size=36, where="bottom"):
    """圖下（或圖上）加一條說明帶。"""
    w, h = im.size
    bh = size + 34
    d = ImageDraw.Draw(im, "RGBA")
    y0 = h - bh if where == "bottom" else 0
    d.rectangle((0, y0, w, y0 + bh), fill=color + (232,))
    d.text((w // 2, y0 + bh // 2), text, font=font(size), fill=WHITE, anchor="mm")


# ─────────── 每張圖的標註（座標：原圖 1376×768） ───────────

def f_bleed_press(im, d):
    callout(d, 1, (70, 650), (640, 495), "紗布蓋住整個傷口", GREEN)
    callout(d, 2, (960, 150), (780, 290), "手掌直接往下加壓", GREEN)
    arrow(d, (720, 30), (720, 225), GREEN)
    band(im, "加壓至少 5 分鐘｜紗布浸濕不要拿掉，直接再加一層", GREEN)


def f_burn_cool(im, d):
    callout(d, 1, (70, 130), (598, 250), "乾淨冷水輕輕沖", NAVY)
    callout(d, 2, (820, 600), (655, 385), "沖 20–30 分鐘", NAVY)
    # 沖脫泡蓋送：第一步高亮
    w, h = im.size
    steps = ["沖", "脫", "泡", "蓋", "送"]
    bw, gap, y = 92, 14, 18
    x0 = w - (bw * 5 + gap * 4) - 30
    for i, s in enumerate(steps):
        x = x0 + i * (bw + gap)
        on = i == 0
        d.rounded_rectangle((x, y, x + bw, y + bw), 14, fill=(NAVY if on else WHITE) + (240,),
                            outline=NAVY, width=4)
        d.text((x + bw / 2, y + bw / 2), s, font=font(52), fill=WHITE if on else NAVY, anchor="mm")


def f_amputation_bag(im, d):
    callout(d, 1, (860, 150), (690, 470), "內袋：濕紗布包好的斷肢", NAVY, size=34)
    callout(d, 2, (40, 230), (420, 390), "外袋：冰塊或冰敷包", NAVY, size=34)
    callout(d, 3, (960, 520), (910, 380), "標記部位、時間、姓名", NAVY, size=30)
    band(im, "隔水保冰：冰塊不直接碰斷肢，不要直接冷凍", NAVY)


def f_shock_broom(im, d):
    band(im, "先切斷電源；非高壓電又切不斷時，才這樣做", AMBER, where="top")
    callout(d, 1, (60, 650), (470, 565), "站在乾燥木板上", AMBER)
    callout(d, 2, (780, 150), (625, 190), "只握乾的木柄", AMBER)
    callout(d, 3, (820, 700), (1050, 590), "把傷者的手移離電源", AMBER)


def f_cpr_posture(im, d):
    # 肩膀→手 的垂直參考線
    for y in range(40, 430, 26):
        d.line(((700, y), (700, y + 13)), fill=WHITE, width=6)
    callout(d, 1, (160, 150), (655, 310), "手肘打直", NAVY)
    callout(d, 2, (160, 60), (700, 40), "肩膀在手的正上方", NAVY)
    arrow(d, (590, 330), (590, 470), RED)
    callout(d, 3, (60, 390), (560, 400), "垂直下壓 5–6 公分", RED)
    callout(d, 4, (1000, 690), (1010, 470), "跪在身側", NAVY)


def f_aed_pads(im, d):
    callout(d, 1, (60, 150), (548, 262), "右鎖骨正下方", RED)
    callout(d, 2, (960, 590), (842, 480), "左乳頭側邊", RED)
    band(im, "拉開衣服，貼在裸露胸壁；依貼片上的圖示", RED)


FN = {k[2:]: v for k, v in globals().items() if k.startswith("f_")}


def make(name):
    src = os.path.join(RAW, APPROVED[name])
    im = Image.open(src).convert("RGB")
    assert im.size == (1376, 768), im.size
    d = ImageDraw.Draw(im, "RGBA")
    FN[name](im, d)
    h = round(OUT_W * im.size[1] / im.size[0])
    out = im.resize((OUT_W, h), Image.LANCZOS)
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name + ".webp")
    out.save(p, "WEBP", quality=Q, method=6)
    print(f"{name}: {APPROVED[name]} → {os.path.relpath(p, ROOT)} {out.size} {os.path.getsize(p)//1024} KB")


if __name__ == "__main__":
    for n in (sys.argv[1:] or list(APPROVED)):
        make(n)
