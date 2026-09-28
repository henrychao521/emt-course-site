"""程式繪製的示意圖（SVG，內嵌於頁面，顏色走 CSS 變數，深淺色都可讀）。
由 tools/img/insert_figures.py 放進 src/first-aid.html。文字全部是本站撰寫，可再編輯。"""

def marker(i, cls):
    return (f'<marker id="{i}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" class="{cls}"/></marker>')

EYE = f'''<svg viewBox="0 0 400 250" role="img" aria-labelledby="eye-t eye-d" xmlns="http://www.w3.org/2000/svg">
<title id="eye-t">沖洗眼睛的方向</title>
<desc id="eye-d">撐開上下眼瞼，水從靠鼻子的內眼角流向外眼角。</desc>
<defs>{marker("eye-a", "ah")}{marker("eye-g", "ahg")}</defs>
<path class="ln" d="M52,40 C62,90 60,150 40,200 C55,212 75,212 88,204"/>
<text class="t s" x="12" y="232">鼻子這側</text>
<path class="skin" style="fill:#fbfaf6" d="M100,130 Q205,58 310,130 Q205,196 100,130 Z"/>
<circle cx="205" cy="128" r="30" style="fill:#8a6a4a;stroke:#5a4630;stroke-width:2"/><circle cx="205" cy="128" r="12" style="fill:#222"/>
<path class="ln" d="M205,84 L205,50" marker-end="url(#eye-g)"/><path class="ln" d="M205,172 L205,206" marker-end="url(#eye-g)"/>
<text class="t s" x="215" y="58">撐開上眼瞼</text><text class="t s" x="215" y="206">撐開下眼瞼</text>
<path class="water" d="M84,74 C96,96 104,112 112,124"/>
<path class="ln acc" d="M116,118 C170,100 250,104 318,138" marker-end="url(#eye-a)"/>
<circle class="dot" cx="104" cy="130" r="6"/><circle class="dot" cx="306" cy="130" r="6"/>
<text class="t b" x="100" y="160" text-anchor="middle">內眼角</text>
<text class="t b" x="330" y="166" text-anchor="middle">外眼角</text>
<text class="t acc" x="200" y="24" text-anchor="middle">由內眼角 → 外眼角，緩慢沖洗</text>
<text class="t s" x="330" y="184" text-anchor="middle">水從這裡流走</text>
</svg>'''

CPR = f'''<svg viewBox="0 0 400 766" role="img" aria-labelledby="cpr-t cpr-d" xmlns="http://www.w3.org/2000/svg">
<title id="cpr-t">CPR 按壓位置與手勢</title>
<desc id="cpr-d">A 正面：掌根放在兩乳頭連線中央，也就是胸骨下半段。B 側面：手臂打直，下方手只有掌根貼在胸部，手指往上翹起、和胸部之間留有空隙；上方手疊在下方手的手背上。C 由上往下看：上方手的手指插進下方手的手指之間，十指交扣。</desc>
<defs>{marker("cpr-r", "ahr")}{marker("cpr-g", "ahg")}</defs>
<text class="t b" x="12" y="22">A　按壓位置（正面）</text>
<path class="skin" d="M125,44 Q200,30 275,44 L292,70 L284,196 L116,196 L108,70 Z"/>
<path class="ln" d="M170,40 Q200,56 230,40"/>
<rect class="hand2" x="194" y="52" width="12" height="104" rx="5"/>
<text class="t s" x="300" y="70">胸骨</text><path class="ln" d="M298,66 L210,80"/>
<line class="ln dash" x1="150" y1="118" x2="250" y2="118"/>
<circle cx="150" cy="118" r="4.5" style="fill:var(--ink-2)"/><circle cx="250" cy="118" r="4.5" style="fill:var(--ink-2)"/>
<text class="t s" x="300" y="122">兩乳頭連線</text><path class="ln" d="M298,118 L256,118"/>
<circle class="dot" cx="200" cy="120" r="13" style="opacity:.85"/>
<text class="t b" x="200" y="222" text-anchor="middle">● 掌根放在兩乳頭連線中央</text>
<text class="t s" x="200" y="240" text-anchor="middle">（胸骨下半段）</text>
<line class="ln" x1="0" y1="258" x2="400" y2="258" style="stroke:var(--rule)"/>

<text class="t b" x="12" y="282">B　手勢（側面）</text>
<rect class="hand" x="150" y="292" width="28" height="104" rx="8"/>
<rect class="hand2" x="176" y="292" width="28" height="100" rx="8"/>
<text class="t s" x="214" y="312">手臂打直</text>
<path class="hand" d="M148,392 L150,436 Q152,456 172,458 L194,458 Q206,456 214,446 L262,428 L330,402 Q340,398 336,390 Q332,384 322,386 L262,398 L206,396 Z"/>
<path class="hand2" d="M174,384 L206,386 L262,390 L318,378 Q328,376 330,384 Q330,390 322,392 L268,404 L214,414 Q178,418 172,402 Z"/>
<path class="ln" d="M16,460 Q200,452 384,460" style="stroke:var(--ink-2);stroke-width:4"/>
<text class="t s" x="16" y="484">胸部</text>
<ellipse cx="182" cy="459" rx="24" ry="6" class="dot" style="opacity:.8"/>
<text class="t red" x="100" y="500">只有掌根接觸</text><path class="ln red" d="M166,486 L176,466" style="stroke-width:2"/>
<path class="ln" d="M346,398 L346,452" marker-start="url(#cpr-g)" marker-end="url(#cpr-g)"/>
<text class="t b" x="392" y="488" text-anchor="end">手指翹起</text><text class="t s" x="392" y="506" text-anchor="end">不碰胸部（留空隙）</text><path class="ln" d="M352,472 L346,456" style="stroke-width:1.5"/>
<text class="t s" x="214" y="344">上方手疊在下方手的手背上</text><path class="ln" d="M290,350 L290,380" style="stroke-width:1.5"/>
<path class="ln red" d="M70,300 L70,440" marker-end="url(#cpr-r)"/>
<text class="t red" x="80" y="344">垂直</text><text class="t red" x="80" y="362">下壓</text>
<line class="ln" x1="0" y1="522" x2="400" y2="522" style="stroke:var(--rule)"/>

<text class="t b" x="12" y="540">C　十指交扣（由上往下看）</text>
<rect class="hand" x="96" y="566" width="120" height="132" rx="26"/>
<rect class="hand" x="206" y="566" width="104" height="20" rx="10"/>
<rect class="hand" x="206" y="604" width="116" height="20" rx="10"/>
<rect class="hand" x="206" y="642" width="110" height="20" rx="10"/>
<rect class="hand" x="206" y="680" width="92" height="18" rx="9"/>
<rect class="hand2" x="120" y="560" width="112" height="140" rx="26"/>
<rect class="hand2" x="222" y="585" width="96" height="18" rx="9"/>
<rect class="hand2" x="222" y="623" width="104" height="18" rx="9"/>
<rect class="hand2" x="222" y="661" width="98" height="18" rx="9"/>
<rect class="hand2" x="222" y="547" width="84" height="18" rx="9"/>
<text class="t s" x="176" y="636" text-anchor="middle">上方手</text>
<rect class="hand" x="40" y="720" width="18" height="14" rx="3"/><text class="t s" x="64" y="732">下方手（掌根貼胸）</text><rect class="hand2" x="210" y="720" width="18" height="14" rx="3"/><text class="t s" x="234" y="732">上方手</text>
<text class="t s" x="40" y="752">兩手手指交錯扣住（B、C 圖同色）</text>
<path class="ln" d="M340,595 L324,595 M340,633 L330,633 M340,671 L324,671" style="stroke-width:1.5"/>
<text class="t s" x="344" y="636">交錯</text>
</svg>'''

ROLES = f'''<svg viewBox="0 0 400 620" role="img" aria-labelledby="roles-t roles-d" xmlns="http://www.w3.org/2000/svg">
<title id="roles-t">發現有人倒下：叫叫壓電與分工</title>
<desc id="roles-d">確認現場安全，拍肩呼叫確認意識；沒有反應就大聲呼救並分工：你留在患者身旁，旁人甲打 119 並開擴音，旁人乙去拿 AED。確認呼吸，沒有、幾乎沒有或不確定就開始胸外按壓。AED 到了黏上貼片、開機、聽語音指示，之後立即恢復按壓，持續到救護人員抵達或患者有動作、正常呼吸。</desc>
<defs>{marker("rl-g", "ahg")}{marker("rl-a", "ah")}</defs>
<rect class="bx" x="40" y="8" width="320" height="40" rx="4"/><text class="t" x="200" y="33" text-anchor="middle">① 確認現場安全</text>
<path class="ln" d="M200,48 L200,64" marker-end="url(#rl-g)"/>
<rect class="bx" x="40" y="66" width="320" height="54" rx="4"/><text class="t" x="200" y="89" text-anchor="middle">② 拍肩呼叫「你怎麼了！」</text><text class="t s" x="200" y="109" text-anchor="middle">沒有反應 ↓</text>
<path class="ln" d="M200,120 L200,136" marker-end="url(#rl-g)"/>
<rect class="bx call" x="40" y="138" width="320" height="40" rx="4"/><text class="t b" x="200" y="163" text-anchor="middle">③ 大聲呼救，指定分工</text>
<path class="ln" d="M200,178 L200,196 M68,196 L332,196 M68,196 L68,210 M200,196 L200,210 M332,196 L332,210"/>
<rect class="bx key" x="8" y="212" width="120" height="76" rx="4"/><text class="t b" x="68" y="236" text-anchor="middle">你</text><text class="t s" x="68" y="256" text-anchor="middle">留在患者身旁</text><text class="t s" x="68" y="274" text-anchor="middle">繼續下一步</text>
<rect class="bx call" x="140" y="212" width="120" height="76" rx="4"/><text class="t b" x="200" y="236" text-anchor="middle">旁人甲</text><text class="t s" x="200" y="256" text-anchor="middle">打 119、開擴音</text><text class="t s" x="200" y="274" text-anchor="middle">聽從執勤人員指示</text>
<rect class="bx call" x="272" y="212" width="120" height="76" rx="4"/><text class="t b" x="332" y="236" text-anchor="middle">旁人乙</text><text class="t s" x="332" y="256" text-anchor="middle">拿 AED</text><text class="t s" x="332" y="274" text-anchor="middle">設法取得 AED</text>
<path class="ln" d="M68,288 L68,318" marker-end="url(#rl-g)"/>
<rect class="bx" x="8" y="320" width="300" height="54" rx="4"/><text class="t" x="16" y="343">④ 確認呼吸</text><text class="t s" x="16" y="363">沒有、幾乎沒有，或無法確定 → 立刻按壓</text>
<path class="ln" d="M68,374 L68,392" marker-end="url(#rl-g)"/>
<rect class="bx key" x="8" y="394" width="300" height="66" rx="4"/><text class="t b" x="16" y="417">⑤ 胸外按壓</text><text class="t s" x="16" y="437">掌根在兩乳頭連線中央｜5–6 公分</text><text class="t s" x="16" y="455">每分鐘 100–120 下｜每次完全回彈</text>
<path class="ln acc" d="M332,288 L332,512 L312,512" marker-end="url(#rl-a)"/>
<text class="t acc" x="340" y="390" transform="rotate(90 340 390)" text-anchor="middle">AED 送到</text>
<path class="ln" d="M68,460 L68,476" marker-end="url(#rl-g)"/>
<rect class="bx key" x="8" y="478" width="300" height="66" rx="4"/><text class="t b" x="16" y="501">⑥ AED：黏貼片、開機</text><text class="t s" x="16" y="521">聽從語音指示操作</text><text class="t s" x="16" y="539">之後立即恢復按壓</text>
<path class="ln" d="M68,544 L68,558" marker-end="url(#rl-g)"/>
<rect class="bx" x="8" y="560" width="384" height="54" rx="4"/><text class="t" x="16" y="583">⑦ 持續按壓，直到救護人員抵達</text><text class="t s" x="16" y="603">或患者開始有動作、有正常呼吸</text>
</svg>'''
