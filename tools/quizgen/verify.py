"""逐題查證結果（Claude 對照權威來源逐題判定）→ docs/quiz-bank-2026-09-29/verified.json 與 assets/quiz-bank.json。
候選題 id：OR＝原本 10 題、CL＝Claude（opus-5-5）、GP＝gemini-3.1-pro-high、GF＝gemini-3.8-flash-high、
SN＝claude-sonnet-4-6、GO＝gpt-oss-120b-medium；編號為該模型採用回合的題目順序。
"""
import copy, json, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "docs/quiz-bank-2026-09-29/raw"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import KN, check_batch, check_item, extract_json, norm  # noqa: E402
from claude_batch import S  # noqa: E402

SETS = [  # 前綴, 模型, 採用回合檔
    ("OR", "original（網站原本 10 題）", RAW / "original_final.json"),
    ("CL", "claude-opus-5-5", RAW / "claude-opus-5-5_final.json"),
    ("GP", "gemini-3.1-pro-high", RAW / "gemini-3.1-pro-high_r3.txt"),
    ("GF", "gemini-3.8-flash-high", RAW / "gemini-3.8-flash-high_r1.txt"),
    ("SN", "claude-sonnet-4-6", RAW / "claude-sonnet-4-6_r1.txt"),
    ("GO", "gpt-oss-120b-medium", RAW / "gpt-oss-120b-medium_final.json"),
]

DUP = "語意重複"
WRONG = "答案或敘述與權威來源不符"
DISTR = "干擾選項有爭議或不合理"
ORDER = "排序或情境有爭議"
TRIVIA = "干擾選項無法查證／過於瑣碎"
# 修正類別
F_EXPL = "解說引用知識點代號、選項字母或來源未載明的推論"
F_PREC = "用詞不夠精確（依法規原文修正）"
F_STEM = "題幹情境不合理或會誤導"
F_TW = "用語修正（台灣用語／學校情境）"

DROP = {
    # 原因類別, 說明
    "CL01": (DUP, "與 SN01（成人 CPR 流程排序）重複，保留 SN01"),
    "CL03": (DUP, "與 GP25（斷指保存排序）重複，保留 GP25"),
    "CL07": (DUP, "與 GF17（先停機斷電）重複，保留 GF17"),
    "CL10": (DUP, "與 SN07（不會人工呼吸就持續按壓）重複"),
    "CL11": (DUP, "與 SN10（AED 到達後聽語音指示）重複"),
    "CL12": (DUP, "與 SN23（何時停止 CPR）重複"),
    "CL20": (DUP, "與 GF08（不要為找斷指延誤送醫）重複"),
    "CL22": (DUP, "與 SN16（沖洗方向）重複"),
    "CL23": (DUP, "與 SN14（插入眼睛的異物不可移除）重複"),
    "CL24": (DUP, "與 SN08（隱形眼鏡不應隨便拔除）重複"),
    "CL25": (DUP, "與 SN21（高壓電 10 公尺）重複"),
    "CL26": (DUP, "與 SN24（觸電後仍要送醫）重複"),
    "CL27": (DUP, "與 SN06（電燒傷入口出口）重複"),
    "CL28": (DUP, "與 GP05（救護技術員施行救護的地點）重複"),
    "CL31": (DUP, "與 GP12（初、中、高級救護項目比較）重複"),
    "CL39": (DUP, "與 GF06（緊急避難免責）重複"),
    "CL43": (DUP, "與 GF10（加壓至少五分鐘）重複"),
    "GP06": (DUP, "與 OR02（初級報名資格只規定學歷）重複"),
    "GP10": (DUP, "與 CL29（服兵役展延 1 年）重複；另「每次展延 3 年」干擾選項在一般展延時為真，易生爭議"),
    "GP11": (DUP, "與 CL30（降級發證）重複"),
    "GP15": (DUP, "與 OR01（初級總時數 56 小時）重複"),
    "GP22": (DUP, "與 OR04（繼續教育 24 小時含模組二、四、六 12 小時）重複"),
    "GP23": (DUP, "與 GF17（先停機斷電）重複"),
    "GP24": (DUP, "與 CL02（沖脫泡蓋送排序）重複"),
    "GP27": (DUP, "與 OR09（非高壓電以乾燥絕緣物撥離）重複"),
    "GP28": (DUP, "與 SN01（成人 CPR 流程排序）重複"),
    "GF01": (DUP, "與 CL02（沖脫泡蓋送排序）重複；且「送」寫成送往灼傷醫院，臺北市消防局原文為「嚴重時，打 119 求救」"),
    "GF02": (DUP, "與 GP25（斷指保存排序）重複"),
    "GF04": (DUP, "與 OR08（紗布浸透不移除）重複；解說「以免破壞已形成的凝血塊」為來源未載明的推論"),
    "GF07": (DUP, "與 CL13（化學粉末先刷除再沖水）重複"),
    "GF13": (DUP, "與 CL16（重度灼燙傷的情形）重複；正確選項文字拗口"),
    "GF15": (DUP, "與 CL42（沒受過訓練先直接加壓）重複"),
    "GF18": (DUP, "與 CL08（呼救分工）重複；干擾選項（騎機車送醫、要大家保持安靜）過於誇張"),
    "GF19": (DUP, "與 OR08（紗布浸透不移除）重複"),
    "GF20": (DUP, "與 CL41（插入的鋸片不要拔）重複；干擾選項「用鐵鎚將鋸片打入」不合理"),
    "GF21": (DUP, "與 CL14（衣物沾黏勿強行剝除）重複；干擾選項（牙膏、醬油）超出網站內容"),
    "GF22": (DISTR, "與 CL15（大面積燙傷注意保暖）重複；三個干擾選項都誇張到不需判斷"),
    "GF23": (DISTR, "與 OR10（斷指保存）重複；干擾選項「等全班下課再送醫」「塞入口袋搭公車」不合理"),
    "GF24": (DUP, "與 CL21（腔室症候群徵象）重複"),
    "SN02": (ORDER, "把「確認有無反應及呼吸」放在呼救之前，與衛福部摘要表「確認意識→求救→確認呼吸」順序不符；保留 CL05"),
    "SN03": (ORDER, "「立即以大量清水沖洗」與「撐開眼瞼由內往外沖洗」是同一動作，無法排序；把「確認化學物質」排第一可能被理解成先查成分再沖，延誤沖洗"),
    "SN04": (DUP, "與 OR09（非高壓電以乾燥絕緣物撥離）重複"),
    "SN05": (DUP, "與 SN21（高壓電 10 公尺情境題）重複"),
    "SN09": (DUP, "與 SN24（觸電後仍要送醫情境題）重複"),
    "SN12": (DUP, "與 OR05、OR06（按壓深度、速率）重複"),
    "SN20": (DISTR, "干擾選項「讓帶 AED 的同學操作，自己繼續不中斷按壓」正是臺北市消防局寫的做法（1 人持續壓胸、另 1 人開 AED），不能當錯誤選項"),
    "GO04": (TRIVIA, "干擾選項的課程代碼（B12、C07、D03）無法查證是否真實存在，且考代碼過於瑣碎"),
    "GO07": (DUP, "與 CL36（報名前查訓練機構與 56 小時）重複；干擾選項含網站列為需確認的「家長同意書」，且用了中國用語「筆記本電腦」"),
    "GO08": (DUP, "與 OR02 重複"),
    "GO09": (DUP, "與 OR03 重複"),
    "GO10": (DUP, "與 OR04 重複"),
    "GO11": (DUP, "與 GF17（先停機斷電）重複"),
    "GO12": (DUP, "與 GF17、GF03 重複；情境寫成「工廠、同事」不符學校情境；割傷一律先叫 119 與網站出血處置（危及生命或止不住才叫）不一致"),
    "GO13": (DUP, "與 OR08 重複"),
    "GO14": (DUP, "與 CL02（沖脫泡蓋送排序）重複"),
    "GO15": (DUP, "與 OR10（斷指保存）重複"),
    "GO17": (DUP, "與 SN01（成人 CPR 流程排序）重複"),
    "GO19": (DUP, "與 SN10（AED 到達後聽語音指示）重複"),
}

# 修正：欄位覆寫
FIX = {
    "GP07": ([F_PREC], {"options": ["報名中級須高級中等以上學校畢業或具同等學力，並領有效期內的初級證書", "報名高級只要有專科以上學歷即可，不需要其他證書",
                                    "從事初級救護技術員連續四年以上，可直接報名高級", "報名中級只需國中畢業，但必須有初級證書兩年以上"],
                        "answer": "報名中級須高級中等以上學校畢業或具同等學力，並領有效期內的初級證書"},
             "原正確選項寫「必須高中職以上畢業」漏了「或具同等學力」，依第 2 條原文補上"),
    "GP20": ([F_STEM], {"stem": "運動會上同時有同學急產、有同學被烤肉架燙傷。依《救護技術員管理辦法》第 13 條，下列哪一組救護項目都屬於初級救護技術員得施行的範圍？",
                        "explain": "第 13 條列出初級得施行的 20 項，給予氧氣、燒燙傷口處置、急產接生都在其中；依預立醫療流程給藥是第 15 條所列高級救護技術員的項目，初級不可施行。"},
             "原題幹寫「保健室護理師」（護理人員本身就是救護人員，與初級救護技術員身分混淆），改為直接問第 13 條範圍"),
    "GP26": ([F_EXPL], {"explain": "化學品入眼必須立即以大量清水沖洗，撐開上下眼瞼、由內眼角往外眼角緩慢沖洗，持續沖洗並儘速送醫。揉眼、擦拭眼球或自行點眼藥水都不是教材的處置。"},
             "解說「避免污染另一隻眼睛」為來源未載明的推論，刪除"),
    "GF05": ([F_EXPL], {"explain": "消防署教材：現場不需做脫臼或骨折復位，懷疑骨折的部位以原來姿勢固定、儘量減少移動。"}, "解說改以來源敘述"),
    "GF08": ([F_EXPL], {"explain": "消防署教材：不要為了找尋遺失的斷肢而延誤傷者送醫；找不到時，相關人員可留在現場協尋。"}, "解說改以來源敘述"),
    "GF09": ([F_EXPL], {"explain": "消防署教材的灼燙傷嚴重度分類：成人二度灼燙傷面積超過 25% 屬重度。"}, "解說改以來源敘述"),
    "GF10": ([F_EXPL], {"explain": "消防署教材：最有效的止血方式是加壓止血，至少五分鐘，讓傷口凝血達到止血效果。"},
             "原解說把 15、30 分鐘說成冰敷或泡水的時間，與網站數字（冰敷 15–20 分鐘、泡水 30 分鐘）不完全對應，刪除"),
    "GF11": ([F_EXPL], {"explain": "臺北市消防局「沖脫泡蓋送」：沖是用乾淨的冷水輕輕沖洗或浸泡 20 至 30 分鐘；泡是持續浸泡冷水 30 分鐘。"}, "解說改以來源敘述"),
    "GF12": ([F_EXPL], {"explain": "消防署教材的手掌原則：傷者手掌（含五指）約占全身體表面積 1%。9%、18% 是另一種「九的原則」裡各部位的比例，不是手掌。"}, "解說改以來源敘述"),
    "GF14": ([F_EXPL], {"explain": "臺北市消防局在扭傷處置的建議：每次冰敷 15 至 20 分鐘後休息約 5 至 10 分鐘，冰敷袋外層用毛巾包覆，避免凍傷。"}, "解說改以來源敘述"),
    "GF16": ([F_EXPL], {"difficulty": 2, "explain": "臺北市消防局：患肢如沒有骨折，可考慮抬高。消防署教材：懷疑骨折的部位都當作骨折處理，以原來姿勢固定、儘量減少患處移動，現場不需做復位。"},
             "解說改以來源敘述；只需區辨兩條原則，難度由 3 調為 2"),
    "GF17": ([F_EXPL], {"explain": "任何傷害都先確認現場安全：在工場就是先讓機具停止、切斷電源，再處理傷者；有出血再照割傷出血直接加壓。"}, "刪除來源未載明的推論"),
    "SN01": ([F_EXPL], {"explain": "衛福部民眾版 CPR 摘要表的成人流程：確認現場安全→確認意識（拍肩呼喚）→大聲呼救、打 119、取得 AED→確認呼吸→胸部按壓→AED 到達後黏上貼片、依語音指示操作，之後立即恢復 CPR。"}, "解說原本引用知識點代號，改寫"),
    "SN06": ([F_EXPL], {"explain": "消防署教材：電燒傷常有「入口」與「出口」兩處傷口，外表看不出全部傷害。所以觸電後即使外觀還好，也應送醫評估。"}, "解說原本引用知識點代號，改寫"),
    "SN07": ([F_EXPL], {"explain": "衛福部摘要表：施救者若不操作人工呼吸，則持續作胸部按壓。不要因為不會人工呼吸就不救。"}, "解說原本引用知識點代號，改寫"),
    "SN08": ([F_EXPL], {"explain": "消防署教材：眼睛受傷時不應隨便拔除隱形眼鏡；只有被化學品灼傷時，才在醫療指導醫師指示下拔除。"}, "刪除知識點代號與來源未載明的「二次傷害」推論"),
    "SN10": ([F_EXPL], {"explain": "衛福部摘要表：AED 到達後黏上貼片、打開機器，聽從 AED 指示操作，之後立即恢復 CPR；不要自行判斷。按壓儘量避免中斷，中斷時間不超過 10 秒。"}, "解說原本引用選項字母（選項會打亂），改寫"),
    "SN11": ([F_EXPL], {"explain": "衛福部摘要表：掌根放在兩乳頭連線中央（胸骨下半段）。「左胸心臟正上方」是常見的誤解。"}, "解說原本引用選項字母並含來源未載明的推論，改寫"),
    "SN13": ([F_EXPL], {"explain": "臺北市消防局：心跳停止後，要儘快在黃金 4 分鐘內透過胸外按壓維持血液循環，避免腦部因缺氧而造成永久傷害。"}, "解說原本引用知識點代號，改寫"),
    "SN14": ([F_STEM, F_EXPL], {"stem": "工場課中，一小段尖細的木屑插進同學的眼睛組織裡。下列哪個處置最正確？",
                                "explain": "消防署教材：有異物插入組織時，不可強行移除，應固定後儘速送醫；有異物插入眼睛或眼周組織，屬於要叫 119 的情形。用水沖出、用棉棒夾出都是在移除異物；固定也不是用力壓迫。"},
             "題幹「削尖的木料刺入眼球」描述較驚悚，改寫；解說刪除選項字母與推論"),
    "SN15": ([F_EXPL], {"explain": "《緊急醫療救護法》第 14-1 條：中央衛生主管機關公告的公共場所，應置有 AED 或其他必要之緊急救護設備；相關辦法由中央衛生主管機關訂定。所以不是「所有」公共場所、不由地方政府自訂，也不只設在醫院和消防局。設置地點可在衛福部 AED 急救資訊網查詢。"}, "解說原本引用知識點代號，改寫並補法條依據"),
    "SN16": ([F_EXPL], {"explain": "消防署教材：撐開上下眼瞼，由內眼角往外眼角緩慢沖洗，持續沖洗並儘速送醫。"}, "刪除選項字母與「推向鼻淚管」「水壓過大」等來源未載明的推論"),
    "SN17": ([F_EXPL], {"explain": "網站第四章：工場裡的預防方法，是操作機具時依工場規定配戴護目鏡。備好清水是受傷後的處置，不是防護；隱形眼鏡不是護具；閉著眼睛操作機具本身就很危險。"}, "解說原本引用選項字母，改寫"),
    "SN18": ([F_EXPL], {"explain": "任何傷害都先確認現場安全：在工場就是先切斷電源，電源沒切斷前抱起或按壓，施救者也可能觸電。觸電者還要注意是否從高處摔落、合併骨折，尤其是頸部。"}, "解說原本引用知識點代號與選項字母，改寫"),
    "SN19": ([F_EXPL], {"explain": "衛福部摘要表的成人流程：一確認沒有反應，就大聲呼救、打 119、設法取得 AED（成人是先打 119 求援），接著確認呼吸並開始胸部按壓。先按一輪、先吹氣或等待觀察都不符合成人流程。"}, "解說原本引用知識點代號與選項字母，改寫"),
    "SN21": ([F_EXPL], {"explain": "消防署教材：高壓電要離開至少 10 公尺才能接近，未斷電前絕不要進入區域，也不要嘗試用任何東西移除電線或移動傷者，請專業人員斷電。用乾燥絕緣物撥離電源，只適用於非高壓電。"}, "解說原本引用知識點代號與選項字母，改寫"),
    "SN22": ([F_EXPL], {"explain": "化學品入眼要立即以大量清水沖洗（甲）；有異物插入組織時不可強行移除，應固定後儘速送醫（乙）。兩種情況處置不同，所以要先看清楚進入眼睛的是什麼；但化學品入眼不能為了查成分而延誤沖洗。"}, "刪除知識點代號與「沖洗可能讓碎片移位」等推論"),
    "SN23": ([F_EXPL], {"explain": "衛福部摘要表：持續高品質 CPR，直到救護人員抵達，或患者開始有動作或有正常呼吸。按壓時間長短、手痠或膚色改變都不是停止的時機。"}, "解說原本引用知識點代號與選項字母，改寫"),
    "SN24": ([F_EXPL], {"explain": "消防署教材：恢復心跳的傷者仍可能再次心跳停止，需要持續監測心電圖；觸電後即使看起來沒事，也應送醫評估。"}, "解說原本引用知識點代號與選項字母，改寫"),
    "GO01": ([F_STEM, WRONG], {"stem": "依《救護技術員管理辦法》第 4 條，下列哪一個單位「可以」辦理初級救護技術員訓練？",
                               "options": ["縣市衛生局", "高級中等學校（高中職）的健康中心", "一般診所（不是急救責任醫院）", "未經中央衛生主管機關認可的民間補習班"],
                               "answer": "縣市衛生局", "difficulty": 2,
                               "explain": "第 4 條限定四類：各級衛生、消防主管機關；設有醫療、衛生、消防等相關科系所的專科以上學校；符合條件的急救責任醫院；其他經中央衛生主管機關認可的機關、機構、法人或團體。高中職不是專科以上學校，一般診所不是急救責任醫院，未經認可的補習班也不在其中。"},
             "原正確選項把四類全文列出、一眼可辨；干擾選項「外國救護組織」若經認可並非絕對不行，改寫成四個可明確判斷的單位"),
    "GO02": ([WRONG], {"stem": "由經中央衛生主管機關認可的法人團體辦理初級救護技術員訓練，每次辦訓前都要把計畫書送中央衛生主管機關，經審查核准後才能開課。",
                       "explain": "第 6 條：辦訓前應檢具計畫書向中央衛生主管機關提出，經審查核准後始得為之；只有衛生、消防主管機關與相關科系的專科以上學校辦理初、中級訓練得免予申請。認可的法人團體不在免申請之列。"},
             "原題「辦訓前必須送計畫書審核」寫成全稱，但衛生、消防主管機關與學校可免申請，原答案「正確」不成立；改成指定法人團體"),
    "GO05": ([WRONG, F_EXPL], {"stem": "依網站第二章，消防機關開辦的救護訓練，主要對象是哪些人？",
                               "options": ["消防機關自己的救護人員與救護義消", "全體民眾，不需任何條件", "醫院的醫師", "大學學生"],
                               "answer": "消防機關自己的救護人員與救護義消",
                               "explain": "消防主管機關是法規明列可辦訓的單位，但它的救護訓練主要對象是自己的救護人員與救護義消；以臺北市消防局為例，救護人員主要由具中級以上資格的消防人員擔任，另由具初級以上資格的救護義消協助。一般民眾能不能參加，依各消防局公告規定。",
                               "sources": ["EMTR4", "TPTRAIN"]},
             "原解說把「主要對象是救護人員與救護義消」說成管理辦法的規定，實際出自網站整理與臺北市消防局；補出處 TPTRAIN"),
    "GO06": ([WRONG, F_EXPL], {"options": ["公開在消防署網站上，可以線上閱讀", "只能到實體書店購買", "只能透過學校圖書館借閱", "要向國外出版社訂購"],
                               "answer": "公開在消防署網站上，可以線上閱讀",
                               "explain": "內政部消防署編印的救護技術員教科書公開在消防署網站上（電子書），可以當作延伸閱讀。"},
             "原答案寫「公開下載」，實際是網站上的電子書，改為「線上閱讀」；刪除「供任何人下載使用」"),
    "GO16": ([F_TW, F_EXPL], {"stem": "電源還沒切斷或隔開之前，不可以直接用手碰觸觸電的同學。",
                              "explain": "消防署教材：電源還沒隔開前，不要直接用手碰傷者；非高壓電而無法切開電源時，才用乾燥的絕緣物把傷者的肢體拖離電源。"},
             "「受電者」改為一般用語；解說改以來源敘述"),
    "GO18": ([F_EXPL], {"explain": "衛福部摘要表：沒有呼吸或幾乎沒有呼吸（或無法確定）才開始胸外按壓；呼吸正常時持續監測，等候救護人員到場。"},
             "原解說「待呼吸停止或無效時」的「無效」不在來源中，並提到不存在的「選項」，改寫"),
}

# Claude 查證後新增的一題：補第二章排序題
EXTRA = [
    ("CL44", S("order", 1, "ch2", ["W02"], "經中央衛生主管機關認可的法人團體想開一班初級救護技術員訓練，下列步驟的先後順序是？",
               ["準備計畫書（寫明師資、課程大綱與時數、場所、訓練器材、收費方式等）", "把計畫書送中央衛生主管機關", "經審查核准", "開始招生、開課"], None,
               "《救護技術員管理辦法》第 6 條：辦訓前應檢具計畫書向中央衛生主管機關提出，經審查核准後始得開課；計畫書要寫明實施期間、師資、課程大綱與時數、場所、訓練器材與設備、收費方式等。",
               ["EMTR6"])),
]

LINT = [(re.compile(r"選項\s*[A-DＡ-Ｄ]"), "解說引用選項字母"), (re.compile(r"\b[EWUGBRCYSP]\d{2}\b"), "出現知識點代號"),
        (re.compile(r"清單"), "出現「清單」"), (re.compile(r"《[A-Z0-9]+》"), "出現出處代碼")]


def load():
    cands = []
    for pre, model, f in SETS:
        items = json.loads(f.read_text()) if f.suffix == ".json" else extract_json(f.read_text())
        for i, q in enumerate(items, 1):
            q = {k: v for k, v in q.items() if k != "model"}
            cands.append((f"{pre}{i:02d}", model, q))
    for cid, q in EXTRA:
        cands.append((cid, "claude-opus-5-5", q))
    return cands


def main():
    cands = load()
    ids = {c[0] for c in cands}
    for k in list(DROP) + list(FIX):
        assert k in ids, f"查證表的 id 不存在：{k}"
    records, bank = [], []
    for cid, model, q in cands:
        rec = {"cand_id": cid, "model": model, "original": q}
        if cid in DROP:
            cat, note = DROP[cid]
            rec.update(verdict="刪除", reason_category=cat, note=note)
            records.append(rec)
            continue
        fq = copy.deepcopy(q)
        if cid in FIX:
            cats, patch, note = FIX[cid]
            fq.update(patch)
            rec.update(verdict="修正後採用", fix_category=cats, note=note)
        else:
            rec.update(verdict="採用", note="答案、解說與干擾選項逐一對照出處原文無誤，情境不誘導危險行為")
        errs = check_item(fq)
        blob = fq["explain"] + fq["stem"]
        errs += [m for r, m in LINT if r.search(blob)]
        if errs:
            raise SystemExit(f"{cid} 最終驗收未過：{errs}")
        rec["checked_against"] = {s: KN_SRC.get(s, "") for s in fq["sources"]}
        rec["final"] = fq
        records.append(rec)
        bank.append((cid, model, fq))
    # 去重最終檢查（正規化題幹）
    seen = Counter(norm(q["stem"]) for _, _, q in bank)
    dup = [s for s, c in seen.items() if c > 1]
    assert not dup, dup
    # 依章節、題型排序並編號
    tord = {"single": 0, "tf": 1, "scenario": 2, "order": 3}
    bank.sort(key=lambda x: (x[2]["chapter"], x[2]["difficulty"], tord[x[2]["type"]], x[0]))
    out = []
    for n, (cid, model, q) in enumerate(bank, 1):
        qid = f"q{n:03d}"
        for r in records:
            if r["cand_id"] == cid:
                r["bank_id"] = qid
        out.append({"id": qid, **{k: q[k] for k in ("chapter", "type", "difficulty", "kp", "stem") }, 
                    **({"items": q["items"]} if q["type"] == "order" else {"options": q["options"], "answer": q["answer"]}),
                    "explain": q["explain"], "sources": q["sources"], "model": model, "cand_id": cid})
    ok, errs, good = check_batch([{k: v for k, v in q.items() if k not in ("id", "model", "cand_id")} for q in out])
    assert not [e for e in errs if "缺少難度" not in e], errs
    (ROOT / "assets/quiz-bank.json").write_text(json.dumps({"version": "2026-09-29", "questions": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    summ = summarize(records, out)
    summ["出題過程"] = generation()
    (ROOT / "docs/quiz-bank-2026-09-29/verified.json").write_text(
        json.dumps({"date": "2026-09-29", "method": METHOD, "summary": summ, "records": records}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1))


METHOD = ("每題由 Claude 回到 tools/sources.py 登錄的權威來源（全國法規資料庫條文與附表 PDF、衛福部民眾版 CPR 摘要表 PDF、"
          "消防署 2025 救護技術員教科書電子書頁、臺北市消防局防災教育雲原文）逐句核對：正確答案有原文支持、每個干擾選項依原文確實錯、"
          "解說不含來源未載明的推論、情境不誘導危險行為、台灣用語；再以知識點與題意去除語意重複題。原文於 2026-09-29 以 curl 下載核對。")

KN_SRC = {}


def generation():
    """各模型出題回合、自動驗收結果與 agy 帳本用量（額度差值受同時段其他工作影響，只能當上限）。"""
    led = [json.loads(l) for l in Path("/Users/Shared/antigravity-bridge/ledger.jsonl").read_text().splitlines()
           if '"emt-quiz 出題' in l]
    out = {}
    for m in ("gemini-3.1-pro-high", "gemini-3.8-flash-high", "claude-sonnet-4-6", "gpt-oss-120b-medium"):
        log = json.loads((RAW / f"{m}_log.json").read_text())
        rounds = []
        for r in log["rounds"]:
            txt = (RAW / f"{m}_r{r['round']}.txt").read_text()
            try:
                ok2, errs2, good2 = check_batch(extract_json(txt))
                offline = {"合格題數": len(good2), "題數": len(extract_json(txt))}
            except Exception as e:
                offline = {"錯誤": str(e)}
            L = next((x for x in led if x["model"] == m and x["note"].endswith(f"r{r['round']}")), {})
            rounds.append({"回合": r["round"], "agy狀態": r["status"], "秒數": r["secs"], "當時驗收": "通過" if r.get("ok") else "退回",
                           "當時驗收錯誤": r.get("errors", [])[:8], "事後以修補版解析重驗": offline,
                           "tokens": (L.get("usage") or {}).get("total_tokens"), "額度差值_上限_pct": L.get("quota_delta_pct")})
        out[m] = {"回合": rounds}
    out["gemini-3.1-pro-high"]["備註"] = ("三回合 agy 皆回 status ERROR，回應中有串流拼接錯誤（字串中斷後插入「\\n[\\n」），"
                                         "當時的解析器判為 JSON 失敗；事後加入修補後，第 3 回合 28 題全部通過格式驗收，採用第 3 回合")
    out["gpt-oss-120b-medium"]["備註"] = "三回合都差 1 題未達 20 題門檻（出處 key 誤用、排序題超過 6 項），用滿 3 回合後採用合格題最多的第 1 回合 19 題"
    return out


def summarize(records, out):
    by_model = {}
    for r in records:
        m = by_model.setdefault(r["model"], {"出題": 0, "採用": 0, "修正後採用": 0, "刪除": 0, "刪除原因": Counter()})
        m["出題"] += 1
        m[r["verdict"]] += 1
        if r["verdict"] == "刪除":
            m["刪除原因"][r["reason_category"]] += 1
    for m in by_model.values():
        m["通過查證"] = m["採用"] + m["修正後採用"]
        m["刪除原因"] = dict(m["刪除原因"])
    cross = Counter((q["chapter"], q["type"], q["difficulty"]) for q in out)
    return {"題庫總數": len(out), "各模型": by_model,
            "章節": dict(Counter(q["chapter"] for q in out)), "題型": dict(Counter(q["type"] for q in out)),
            "難度": dict(Counter(q["difficulty"] for q in out)),
            "章節x題型x難度": {f"{c}|{t}|{d}": n for (c, t, d), n in sorted(cross.items())},
            "淘汰原因合計": dict(Counter(r["reason_category"] for r in records if r["verdict"] == "刪除")),
            "修正類別合計": dict(Counter(c for r in records if r["verdict"] == "修正後採用" for c in r["fix_category"]))}


if __name__ == "__main__":
    kn = json.loads((ROOT / "docs/quiz-bank-2026-09-29/knowledge.json").read_text())
    sys.path.insert(0, str(ROOT / "tools"))
    from sources import SOURCES
    for s in SOURCES:
        KN_SRC[s] = SOURCES[s][1]
    main()
