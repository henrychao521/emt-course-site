# EMT 網站第四章操作示意圖：AI 生圖規格（Claude 撰寫，派給 Antigravity generate_image）
# 規範第十一節：英文、<=500 字元、關鍵動作寫在前面、結尾固定禁字句、共用風格尾綴、人物不露臉。
# ImageName 一律小寫（agy 會把檔名轉小寫）。
# 每張圖的「動作依據」與「檢核表」寫在 BASIS／CHECK，驗收時逐項人工判定。

STYLE = "Photorealistic instructional photo, soft daylight, crisp focus."
TAIL = "Generic unbranded objects. Absolutely no text, no letters, no numbers, no labels, no logos, no watermark."
W169 = "Wide 16:9 landscape"

IMAGES = {
 # 割傷出血：直接加壓止血（TPBLEED；消防署教科書頁 140、259）
 "bleed_press": (
  W169 + " close-up: first aid on a forearm resting on a light wood workbench. A large folded white gauze pad fully hides a small injury; no red on the skin. A helper's hand in a blue nitrile glove lies flat on top of the pad, the whole palm centered on it, pressing straight down. Only hands and forearms, no face."
  + " " + STYLE + " " + TAIL),
 # 燙傷：沖（TPBURN）
 "burn_cool": (
  W169 + " photo: a teenager's hand and forearm in a short sleeve held under a gentle stream of clean cool tap water at a plain stainless steel workshop sink, cooling a small reddened patch of skin on the back of the hand. The water flows softly over it, not a hard jet. No ice. Only hand and forearm, no face."
  + " " + STYLE + " " + TAIL),
 # 斷肢保存：隔水保冰（消防署教科書頁 287–288）
 "amputation_bag": (
  W169 + " photo on a clean white table: a small sealed clear zip bag holding a bundle wrapped in moist white gauze "
  "sits inside a larger clear zip bag. Ice cubes fill the larger bag around the small bag; ice never touches the "
  "gauze. Nothing visible inside the gauze. Blank white sticker on the outer bag. "
  + STYLE + " " + TAIL),
 # 觸電：站在乾燥絕緣物上，用乾木柄把肢體移離電源（消防署教科書頁 370）
 "shock_broom": (
  W169 + " dry workshop concrete floor: a rescuer stands on a dry wooden board, gloved hands only on a long dry wooden broom handle. The broom head pushes a person's limp hand and wrist away from a damaged black power cord. Show the rescuer's legs, shoes and hands, and the person's forearm. No faces."
  + " " + STYLE + " " + TAIL),
 # CPR 手的位置與手勢（衛福部摘要表 2021；公共場所民眾 CPR+AED 教材；消防署教科書頁 117）
 "cpr_hands": (
  W169 + " side close-up at chest height: CPR on a plain beige adult CPR manikin torso, no head. Heel of one hand on the center of the chest; the other hand on top, fingers interlaced and pulled upward, so the lower hand's fingers are lifted with a clear gap above the chest surface. Only the palm heel touches."
  + " " + STYLE + " " + TAIL),
 # CPR 姿勢：手臂打直、肩在手的正上方、垂直下壓（公共場所民眾 CPR+AED 教材；消防署教科書頁 117）
 "cpr_posture": (
  W169 + " indoor side view: CPR manikin lies across the image, head at left. Rescuer kneels on its far side beside its chest. Arms vertical, elbows locked, shoulders above hands. Only the lower palm heel touches the chest center; fingers interlocked, raised off the chest. Rescuer's head out of frame."
  + " " + STYLE + " " + TAIL),
 # CPR 手勢特寫：掌根接觸、十指交扣、下方手指翹起（公共場所民眾 CPR+AED 教材 PDF 第 19 頁；教科書頁 117）
 "cpr_grip": (
  W169 + ' close-up side view at chest level: two stacked hands doing CPR on a smooth plastic beige training manikin. Only the lower palm heel touches; all fingers interlaced and bent upward like a hook, fingertips 3 cm above the plastic chest, clear gap. Both forearms straight vertical.'
  + " " + STYLE + " " + TAIL),
 # AED 貼片位置（公共場所民眾 CPR+AED 教材：左乳頭側邊、右鎖骨正下方）
 "aed_pads": (
  W169 + " top-down: beige adult CPR manikin torso face up, neck at top edge, no head. Two white AED pads with grey wires on its chest. Pad 1: just below the manikin's right collarbone, image LEFT. Pad 2: manikin's left lower chest, on the side ribs below the armpit, image RIGHT. Wires to a plain grey AED box."
  + " " + STYLE + " " + TAIL),
}
ASPECT = {k: "16:9" for k in IMAGES}

# 動作依據（出處代碼對應 tools/sources.py）
BASIS = {
 "bleed_press": ["TPBLEED", "TB140", "TB259"],
 "burn_cool": ["TPBURN"],
 "amputation_bag": ["TB287", "TB288"],
 "shock_broom": ["TB370"],
 "cpr_hands": ["CPR21", "AEDEDU", "TB117"],
 "cpr_posture": ["AEDEDU", "TB117"],
 "cpr_grip": ["AEDEDU", "TB117"],
 "aed_pads": ["AEDEDU", "CPR21"],
}

# 人工驗收檢核表（每張逐項判定；任何一項不過即同名重生，不修圖）
COMMON = ["只見手、前臂、軀幹或腿，沒有臉", "手指數量與關節自然（每手五指、無多餘手指）",
          "圖上沒有任何文字、字母、數字、商標", "沒有危險的錯誤示範"]
CHECK = {
 "bleed_press": ["紗布完整蓋住傷口", "手掌平貼、直接往下壓在紗布上（不是捏、不是只用指尖）",
                 "按壓位置就在傷口正上方", "沒有止血帶、沒有拔異物等其他動作", "血量不驚悚"] + COMMON,
 "burn_cool": ["燙傷處在水流下方", "水流溫和，不是強力沖擊", "只有清水：沒有冰塊、沒有塗抹物",
               "皮膚紅，但沒有畫成破皮大面積重度燒傷"] + COMMON,
 "amputation_bag": ["小袋密封、裡面是濕紗布包好的物品", "小袋整個放在大袋裡", "冰塊只在大袋內、小袋外，碰不到紗布",
                    "看不到斷肢本體（紗布包住）", "外袋貼紙空白（標註由本站後製）"] + COMMON,
 "shock_broom": ["施救者雙腳站在乾燥木板上", "施救者的手只握木柄", "用木柄末端把傷者的手移離電線",
                 "施救者身體其他部位不碰傷者也不碰電線", "地面乾燥、沒有積水"] + COMMON,
 "cpr_hands": ["下方手的掌根在胸部正中央、兩乳頭連線中點（胸骨下半段）", "不在腹部、不在劍突、不偏向一側肋骨",
               "兩手重疊、十指交扣", "下方手的手指翹起、不壓在胸壁上", "假人無頭部入鏡"] + COMMON,
 "cpr_grip": ["只有下方手掌根接觸胸部", "下方手手指翹起、與胸部之間看得到空隙", "兩手重疊、十指交扣", "手腕與手臂打直、垂直往下", "手在胸部中央（非腹部、非上胸）"] + COMMON,
 "cpr_posture": ["下方手手指翹起、不碰胸部，只有掌根接觸", "手肘打直鎖住", "肩膀在雙手正上方（手臂垂直地面）", "跪在假人身側、膝蓋靠近",
                 "按壓位置在胸部中央", "施救者頭部不入鏡"] + COMMON,
 "aed_pads": ["貼片 1 在假人右鎖骨正下方（影像左上）", "貼片 2 在假人左胸外側、左乳頭側邊（影像右側偏下）",
              "兩片不重疊、都不在胸骨正中央", "胸部裸露、貼片直接貼皮膚", "導線接到 AED 本體", "假人無頭部入鏡"] + COMMON,
}

for k, v in IMAGES.items():
    assert len(v) <= 495, (k, len(v))
    assert k == k.lower()
