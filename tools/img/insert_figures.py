#!/usr/bin/env python3
"""把操作示意圖插入 src/first-aid.html（可重複執行：先移除舊的 <!--fig:...--> 區塊再插入）。"""
import re, sys, os
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from diagrams import EYE, CPR, ROLES
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(ROOT, "src", "first-aid.html")
AI = "圖片：AI 生成（Google Gemini 圖像模型，經 Antigravity）；中文標註為本站後製。"
PROG = "圖：本站以程式繪製（SVG）。"

def photo(name, no, title, alt, items, basis):
    w, h = Image.open(os.path.join(ROOT, "assets", "img", name + ".webp")).size
    li = "".join(f"<li>{x}</li>" for x in items)
    return (f'<!--fig:{name}-->\n<figure class="fig" id="fig-{name}">\n'
            f'  <img src="assets/img/{name}.webp" width="{w}" height="{h}" alt="{alt}" loading="lazy" decoding="async">\n'
            f'  <figcaption><b>圖 {no}　{title}</b><ol>{li}</ol>動作依據：{basis}<span class="credit">{AI}</span></figcaption>\n'
            f'</figure>\n<!--/fig:{name}-->\n')

def dia(name, no, title, svg, text, basis):
    return (f'<!--fig:{name}-->\n<figure class="fig dia" id="fig-{name}">\n{svg}\n'
            f'  <figcaption><b>圖 {no}　{title}</b>　{text}動作依據：{basis}<span class="credit">{PROG}</span></figcaption>\n'
            f'</figure>\n<!--/fig:{name}-->\n')

F = {
 "bleed": photo("bleed_press", "4-1", "直接加壓止血",
   "戴手套的手掌平放在紗布上往下壓，紗布蓋住前臂上的傷口",
   ["紗布（或乾淨布料）蓋住整個傷口。", "手掌直接往下加壓，至少 5 分鐘。", "紗布浸濕時不要拿掉，直接在上面再加紗布、再加壓。"],
   "{{c:TPBLEED}}、{{c:TB140}}、{{c:TB259}}"),
 "burn": photo("burn_cool", "4-2", "燙傷第一步：沖",
   "手背的燙傷處放在溫和的冷水水流下沖洗；右上角是沖、脫、泡、蓋、送五個步驟，目前是沖",
   ["用乾淨的冷水輕輕沖洗，不要強力沖擊。", "沖洗或浸泡 20 至 30 分鐘，接著脫、泡、蓋、送。"],
   "{{c:TPBURN}}"),
 "crush": photo("amputation_bag", "4-3", "斷肢保存：隔水保冰",
   "小塑膠袋裝著用紗布包好的東西，放在裝了冰塊的大塑膠袋裡，冰塊只在大袋內",
   ["斷肢用生理食鹽水潤濕的無菌紗布包好，放進乾淨塑膠袋。", "另一個塑膠袋放冰塊或冰敷包，把第一個袋子放進去：隔水保冰，不要直接冷凍。",
    "在最外層袋子標記斷肢部位、時間與傷者姓名，和傷者一起送醫。"],
   "{{c:TB287}}、{{c:TB288}}"),
 "eye": dia("eye_flush", "4-4", "沖洗眼睛的方向", EYE,
   "撐開患側上下眼瞼，由靠鼻子的內眼角往外眼角緩慢沖洗。", "{{c:TB183}}"),
 "shock": photo("shock_broom", "4-5", "觸電：用乾燥絕緣物移開",
   "施救者站在乾燥木板上，戴手套的手只握著乾的木棍，用木棍末端把倒地者的手推離破損電線",
   ["先切斷電源。非高壓電、又無法切斷時，才站在木箱、橡皮墊等乾燥絕緣體上。", "用乾的掃把、竹竿或木椅，把傷者的肢體拖離電源。",
    "高壓電：離開至少 10 公尺，不要靠近，等專業人員斷電。"],
   "{{c:TB370}}"),
 "roles": dia("cpr_roles", "4-6", "發現有人倒下：叫叫壓電與分工", ROLES,
   "有旁人時指定一人打 119、另一人去拿 AED；施救者儘量不要離開患者。", "{{c:CPR21}}、{{c:TPCPR}}、{{c:AEDEDU}}（PDF 第 14 頁）"),
 "cprpos": dia("cpr_hands", "4-7", "CPR 按壓位置與手勢", CPR,
   "A：掌根放在兩乳頭連線中央（胸骨下半段）。B：手臂打直，只有掌根接觸胸部，下方手的手指往上翹起、不碰胸部。C：另一手疊在下方手的手背上，十指交扣。", "{{c:CPR21}}、{{c:AEDEDU}}（PDF 第 18–19 頁）、{{c:TB117}}"),
 "posture": photo("cpr_posture", "4-8", "CPR 姿勢：手臂打直、垂直下壓",
   "施救者跪在練習用假人身側，手臂打直、肩膀在雙手正上方，垂直往下按壓假人胸部中央",
   ["手肘打直。", "肩膀前傾，位於雙手正上方，用上半身重量往下壓。", "垂直下壓 5 至 6 公分，每分鐘 100 至 120 下，每次讓胸部完全回彈。",
    "兩膝打開與肩同寬，跪在患者身側、儘量靠近。",
    '<b>手勢以圖 4-7 為準：</b>本圖只示範身體姿勢；圖中下方手的手指貼著胸部，是 AI 繪圖畫不出來的細節。正確做法是下方手手指翹起、只有掌根接觸胸部，請看<a href="#fig-cpr_hands">圖 4-7 B</a>。'],
   "{{c:CPR21}}、{{c:AEDEDU}}（PDF 第 17 頁）、{{c:TB117}}"),
 "aed": photo("aed_pads", "4-9", "AED 電擊貼片位置（成人）",
   "練習用假人胸前貼著兩片 AED 貼片：一片在右鎖骨正下方，一片在左胸外側、左乳頭側邊，導線接到 AED 主機",
   ["拉開衣服，貼在裸露的胸壁上，依貼片上的圖示貼。", "一片在右鎖骨正下方。", "一片在左側乳頭側邊。", "貼好、開機後聽從 AED 語音指示。"],
   "{{c:AEDEDU}}（PDF 第 28 頁）、{{c:CPR21}}"),
}

t = open(SRC, encoding="utf-8").read()
t = re.sub(r"\n*<!--fig:[a-z_]+-->.*?<!--/fig:[a-z_]+-->\n", "", t, flags=re.S)

def after(anchor, block):
    global t
    i = t.index(anchor) + len(anchor)
    t = t[:i] + "\n" + block + t[i:]

after('<h2>割傷出血：直接加壓止血</h2>', F["bleed"])
after('<h2>燙傷：沖、脫、泡、蓋、送</h2>', F["burn"])
after('<h2>夾傷／壓傷：先停機，再止血與固定</h2>', F["crush"])
after('<h2>異物入眼：沖洗，插入物不要拔</h2>', F["eye"])
after('<h2>觸電：先斷電，別讓自己變成第二個傷者</h2>', F["shock"])
i = t.index('<ol class="flow">'); j = t.index("</ol>", i) + len("</ol>")
t = t[:j] + "\n" + F["roles"] + F["cprpos"] + F["posture"] + F["aed"] + t[j:]
open(SRC, "w", encoding="utf-8").write(t)
print("ok")
