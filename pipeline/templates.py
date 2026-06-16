"""爆款视频「通用接口模版」库 (Viral video template library).

这里把 TikTok / Facebook(Reels) 带货爆款最常见、被验证过的拍摄结构沉淀成一组
可复用的「模版接口」。每个模版描述了：适用场景、买家心理、逐段节奏(beats)、
钩子角度、CTA 形式、节奏与平台差异。

用途：
- 脚本生成时(llm.py)把模版库当作「菜单」喂给 LLM：让 AI 选最契合本产品/受众的
  一个结构，然后在该结构内自由发挥(变钩子角度/台词/画面)——既踩在爆款骨架上，
  又不会同质化。
- 也可以在 config.yaml 用 `viral_template: <id>` 钉死某个结构做 A/B 对比。

数据是纯 Python，可被程序读取/遍历，所以这就是「通用接口」本身。
研究来源：TikTok Shop 官方 shoppable 内容指南(hook 3-6s / key message / CTA 双触点)、
对 100 条百万级 GMV 视频的结构拆解(PAS 最高转化)、UGC 脚本 10 大钩子公式、
五幕结构(hook→context→demo→social proof→CTA) 等。
"""

from __future__ import annotations

# 每个模版的 applies_to: "product"=单品带货(B2C)  "factory"=工厂展示(B2B)  "both"=两者皆可
VIRAL_TEMPLATES: list[dict] = [
    {
        "id": "pas",
        "name": "Problem–Agitate–Solve (PAS)",
        "name_zh": "痛点-放大-解决",
        "applies_to": ["product", "both"],
        "best_for": "痛点清晰、能被一眼看懂的单品。转化最高、最通用的结构。",
        "psychology": "先让观众在自己身上认出这个痛点并感同身受，再把产品当成『救星角色』自然登场，证据替你卖货。",
        "beats": [
            {"t": "0-3s", "goal": "点名痛点(像在说观众自己)", "shot": "真人手机视角拍下那个糟心瞬间/失败的旧办法", "caption": "一句话痛点"},
            {"t": "3-8s", "goal": "放大痛点，让人难受", "shot": "特写问题细节、情绪反应、试过的无效替代品", "caption": "放大痛感"},
            {"t": "8-15s", "goal": "产品像不经意被发现", "shot": "顺手拿起产品开始用(『后来朋友给我推了这个…』)", "caption": "产品名/卖点1"},
            {"t": "15-22s", "goal": "演示+真实结果", "shot": "before/after、实拍演示、真实反应", "caption": "具体结果/数据"},
            {"t": "22s+", "goal": "软性号召", "shot": "产品 hero 镜头", "caption": "购物入口提示"},
        ],
        "hook_angles": ["POV 你每天都被这事烦", "直接质问『你是不是也…』", "一句让人扎心的大实话", "中途插入式开场(说半句)"],
        "cta_style": "软 CTA：『链接在小黄车 / 想试的话商店里有』。证据已经卖完货，不要硬推。",
        "pacing": "前 3 秒必须出痛点，不要先展示产品。一个核心信息、一个 CTA。",
        "platform": "TikTok 15-21s；FB/Reels 9-15s，更早亮出解决方案。",
    },
    {
        "id": "before_after",
        "name": "Before / After Transformation",
        "name_zh": "前后对比·视觉证据机",
        "applies_to": ["product", "both"],
        "best_for": "效果肉眼可见的品类(清洁、收纳、美妆、身材、空间改造、装修)。",
        "psychology": "人脑对『变化』的反应最强；直接给视觉落差，省去说服。",
        "beats": [
            {"t": "0-2s", "goal": "先甩出强烈的『前』状态", "shot": "脏乱/糟糕的现状特写", "caption": "Before"},
            {"t": "2-6s", "goal": "承诺转变", "shot": "产品入场、开始动手", "caption": "看好了"},
            {"t": "6-15s", "goal": "过程(常用快剪/延时)", "shot": "使用/施工/改造过程", "caption": "步骤感"},
            {"t": "15-22s", "goal": "戏剧化揭晓『后』", "shot": "干净/惊艳的结果", "caption": "After 🤯"},
            {"t": "22s+", "goal": "并排对比+购物入口", "shot": "before/after 同框", "caption": "购物入口"},
        ],
        "hook_angles": ["先放结果再倒回去", "『我不敢相信这是同一个…』", "把最脏/最糟一帧顶在最前"],
        "cta_style": "并排对比时浮出购物条，让落差替你成交。",
        "pacing": "过程段用快节奏剪辑，揭晓那一刻给一个停顿+音效。",
        "platform": "TikTok/Reels 通用；竖屏满构图，对比同框时上下分屏。",
    },
    {
        "id": "i_tested_it",
        "name": "Skeptic Review / I Tested It",
        "name_zh": "质疑式测评(我亲自试了)",
        "applies_to": ["product", "both"],
        "best_for": "网红爆品、看起来『太好以至于不真』的产品；高客单需要信任。",
        "psychology": "先替观众说出怀疑，把自己放在『和你一样不信』的位置，测完反转→可信。",
        "beats": [
            {"t": "0-3s", "goal": "表达怀疑", "shot": "真人对镜头吐槽『我赌它没用』", "caption": "我才不信"},
            {"t": "3-10s", "goal": "上手实测", "shot": "真实使用、不打光、不摆拍", "caption": "实测中"},
            {"t": "10-20s", "goal": "反转(诚实优缺点)", "shot": "结果反应、镜头怼脸惊讶", "caption": "等等…真的行?"},
            {"t": "20s+", "goal": "结论+号召", "shot": "产品+真实表情", "caption": "购物入口"},
        ],
        "hook_angles": ["『大家都在刷它，我赌它是智商税』", "『第 X 天测评说真话』", "『花了我自己的钱来测』"],
        "cta_style": "诚实背书后再给链接，留一句小缺点更可信。",
        "pacing": "刻意低制作感(UGC)，越像真人随手拍越好。",
        "platform": "TikTok 原生 UGC 最吃；FB 可加字幕条强调『真实测评』。",
    },
    {
        "id": "unboxing",
        "name": "Unboxing / First Impression",
        "name_zh": "开箱·第一印象",
        "applies_to": ["product", "both"],
        "best_for": "包装精致、质感强、有惊喜感的产品；新品认知。",
        "psychology": "拆箱制造期待与代入感，展示做工与配置，降低『买回来不一样』的顾虑。",
        "beats": [
            {"t": "0-3s", "goal": "收到的兴奋", "shot": "手捧包裹/盒子特写", "caption": "终于到了"},
            {"t": "3-12s", "goal": "逐层拆解", "shot": "拆封、内含物、质感特写", "caption": "里面有啥"},
            {"t": "12-20s", "goal": "首次上手/装好", "shot": "组装、第一次使用", "caption": "上手感受"},
            {"t": "20s+", "goal": "总体感受+号召", "shot": "成品摆好的 hero", "caption": "购物入口"},
        ],
        "hook_angles": ["『等了两周终于到了』", "『打开瞬间我愣住』", "ASMR 拆封音效开场"],
        "cta_style": "展示完质感顺势给链接，强调到手即用。",
        "pacing": "拆封节奏配音效，关键细节给特写定格。",
        "platform": "TikTok/Reels 通用；竖屏俯拍开箱最常见。",
    },
    {
        "id": "wait_for_it",
        "name": "Wait For It / Suspense Loop",
        "name_zh": "悬念循环(等一下…)",
        "applies_to": ["product", "both"],
        "best_for": "有『惊艳一刻』或反转效果的产品；冲完播率与复播。",
        "psychology": "先给被遮挡/模糊的结果制造好奇缺口，逼观众看到揭晓，结尾勾回开头形成循环。",
        "beats": [
            {"t": "0-2s", "goal": "先闪一下最终效果(模糊/遮挡/快切)", "shot": "结果的局部/虚化", "caption": "等一下…"},
            {"t": "2-5s", "goal": "倒回开头", "shot": "『让我从头给你看』", "caption": "从头说"},
            {"t": "5-18s", "goal": "逐步推进、兴趣升级", "shot": "过程逐步加料", "caption": "步骤"},
            {"t": "18s+", "goal": "完整揭晓+触发复播", "shot": "完整结果，呼应开头", "caption": "购物入口"},
        ],
        "hook_angles": ["『先别划走，看到最后』", "把高潮帧顶在第一帧", "『你绝对猜不到结果』"],
        "cta_style": "揭晓后给链接，可口播『想要同款评论区/小黄车』。",
        "pacing": "中段保持悬念，不要提前剧透；结尾干净利落。",
        "platform": "TikTok 完播向，控制在 15-25s；Reels 更短更快。",
    },
    {
        "id": "listicle",
        "name": "Listicle (X reasons / X things)",
        "name_zh": "清单式(X 个理由/X 件事)",
        "applies_to": ["product", "both"],
        "best_for": "卖点多、需要快速堆价值的产品；信息密度高。",
        "psychology": "数字承诺给确定性，逐条快节奏推进，每条都是一个钩子。",
        "beats": [
            {"t": "0-3s", "goal": "抛出清单承诺", "shot": "真人/产品+大字数字", "caption": "买它的 3 个理由"},
            {"t": "3-9s", "goal": "理由 1", "shot": "对应卖点演示", "caption": "1️⃣ 卖点"},
            {"t": "9-15s", "goal": "理由 2", "shot": "对应卖点演示", "caption": "2️⃣ 卖点"},
            {"t": "15-21s", "goal": "理由 3(最强放最后)", "shot": "最强卖点演示", "caption": "3️⃣ 卖点"},
            {"t": "21s+", "goal": "收束+号召", "shot": "产品 hero", "caption": "购物入口"},
        ],
        "hook_angles": ["『X 个你需要它的理由』", "『别买它，除非你想要这 3 点』", "『刷到就是缘分，X 个理由』"],
        "cta_style": "列完最后一条直接给链接，节奏不停。",
        "pacing": "每条 4-6s，统一转场，最强卖点压轴。",
        "platform": "TikTok/Reels 通用；大字编号要在安全区内。",
    },
    {
        "id": "pov_story",
        "name": "POV / Mini-story (I wish I knew sooner)",
        "name_zh": "POV 小故事(早知道就好了)",
        "applies_to": ["product", "both"],
        "best_for": "和生活方式/情绪强相关的产品；建立共鸣与代入。",
        "psychology": "用第一人称代入与微型故事弧线，让产品成为故事里的转折点而非广告。",
        "beats": [
            {"t": "0-3s", "goal": "设定 POV 情境", "shot": "代入式第一人称画面", "caption": "POV: …"},
            {"t": "3-10s", "goal": "故事冲突/小尴尬", "shot": "情境展开", "caption": "然后…"},
            {"t": "10-18s", "goal": "产品成为转折", "shot": "产品自然介入解决", "caption": "转折点"},
            {"t": "18s+", "goal": "情绪收尾+号召", "shot": "满意结局画面", "caption": "购物入口"},
        ],
        "hook_angles": ["『POV: 你终于…』", "『早知道就好了』", "『没人告诉我这个，所以我来说』"],
        "cta_style": "情绪到位后轻轻给链接，像分享给朋友。",
        "pacing": "故事感优先，台词口语化、有人味。",
        "platform": "TikTok 叙事向；Reels 节奏更紧。",
    },
    {
        "id": "comparison",
        "name": "Side-by-Side Comparison / VS",
        "name_zh": "对比 PK(VS 替代品)",
        "applies_to": ["product", "both"],
        "best_for": "明显优于旧方案/竞品的产品；性价比、效率类。",
        "psychology": "直接给对照组，落差替你证明价值，规避空口吹嘘。",
        "beats": [
            {"t": "0-3s", "goal": "抛出对比命题", "shot": "两者同框", "caption": "便宜 vs 贵?"},
            {"t": "3-12s", "goal": "同条件对照演示", "shot": "并排操作/计时/计量", "caption": "同时测"},
            {"t": "12-20s", "goal": "拉开差距", "shot": "结果差异特写", "caption": "差距出来了"},
            {"t": "20s+", "goal": "结论+号召", "shot": "胜出产品 hero", "caption": "购物入口"},
        ],
        "hook_angles": ["『$12 的对比 $80 的』", "『大牌 vs 平替，结果意外』", "『我同时买了两个来对比』"],
        "cta_style": "胜负分明后给链接，强调省钱/更好。",
        "pacing": "并排同框、相同条件，公平感很重要。",
        "platform": "TikTok/Reels 通用；上下/左右分屏对比。",
    },
    {
        "id": "tutorial",
        "name": "Tutorial / How-To",
        "name_zh": "教程·How-To",
        "applies_to": ["product", "both"],
        "best_for": "有使用门槛或多场景玩法的产品；提供实用价值换信任。",
        "psychology": "先给可执行价值(教会你一件事)，产品作为完成它的关键工具自然带出。",
        "beats": [
            {"t": "0-3s", "goal": "承诺一个结果/时间", "shot": "成品预览", "caption": "30 秒学会…"},
            {"t": "3-18s", "goal": "分步教学", "shot": "逐步操作，产品贯穿其中", "caption": "Step 1/2/3"},
            {"t": "18s+", "goal": "成果+号召", "shot": "完成效果 hero", "caption": "购物入口"},
        ],
        "hook_angles": ["『教你 30 秒搞定 X』", "『99% 的人都做错了这步』", "『保存起来照着做』"],
        "cta_style": "教完顺势『同款工具在小黄车』。",
        "pacing": "步骤清晰、字幕标号，节奏明快。",
        "platform": "TikTok 可稍长(教学完播高)；Reels 精简到 3 步内。",
    },
    {
        "id": "satisfying_asmr",
        "name": "Oddly Satisfying / ASMR Demo",
        "name_zh": "解压·ASMR 演示",
        "applies_to": ["product", "both"],
        "best_for": "有满足感/声音/质感的产品(清洁、厨具、文具、收纳、美妆)。",
        "psychology": "纯感官愉悦带来高停留与重复观看，弱化推销感。",
        "beats": [
            {"t": "0-3s", "goal": "立刻给最爽的一下", "shot": "解压瞬间特写+原声", "caption": "(原声)"},
            {"t": "3-15s", "goal": "连续满足画面", "shot": "多个满足感镜头串联", "caption": "极简文字"},
            {"t": "15s+", "goal": "产品点名+号召", "shot": "产品 hero", "caption": "购物入口"},
        ],
        "hook_angles": ["纯声音/纯画面开场，0 解说", "『把声音打开』", "最满足的一帧顶前面"],
        "cta_style": "字幕极少，结尾轻点产品与链接。",
        "pacing": "保留真实环境音(ASMR)，少配乐或低配乐。",
        "platform": "TikTok 原声向最佳；Reels 同样吃满足感画面。",
    },
    {
        "id": "factory_tour",
        "name": "Factory Tour / Source Direct (B2B)",
        "name_zh": "工厂溯源·源头直供",
        "applies_to": ["factory", "both"],
        "best_for": "工厂展示，找代理/批发/OEM/ODM 买家(B2B)。",
        "psychology": "买家要的是『真实产能+可信赖+能合作』。亲眼看到产线、QC、仓储=信任，绕开中间商=利润。",
        "beats": [
            {"t": "0-3s", "goal": "震撼产线开场(像真在厂里)", "shot": "产线大全景/机器轰鸣推进", "caption": "真·工厂直拍"},
            {"t": "3-10s", "goal": "产能规模", "shot": "多条产线满负荷、工人作业", "caption": "月产能 XX"},
            {"t": "10-16s", "goal": "品控与认证", "shot": "QC 质检特写、证书、原材料", "caption": "严格 QC·CE/ISO"},
            {"t": "16-22s", "goal": "合作门槛(打动 B2B)", "shot": "打样/定制包装/小起订展示", "caption": "低起订·OEM/ODM"},
            {"t": "22s+", "goal": "发货实力+号召询盘", "shot": "仓库满货、集装箱装柜", "caption": "立即询盘"},
        ],
        "hook_angles": ["『带你进我们自己的工厂』", "『没有中间商，源头直供』", "『一天能产 X 件』数字开场"],
        "cta_style": "B2B 号召：『私信/评论 inquiry 拿报价和样品』，强调起订量与定制。",
        "pacing": "真实车间感>精致；同期声(机器声)增强可信。",
        "platform": "TikTok/FB 通用；FB 对 B2B 商家页更友好，可加联系方式字幕。",
    },
    {
        "id": "founder_direct",
        "name": "Founder Direct-to-Camera (B2B)",
        "name_zh": "老板/创始人 出镜直说(B2B)",
        "applies_to": ["factory", "both"],
        "best_for": "工厂/品牌方建立人格信任，拉代理与长期合作。",
        "psychology": "真人老板出镜=负责、可对接、有底气；人对人的信任高于对工厂的信任。",
        "beats": [
            {"t": "0-3s", "goal": "老板对镜头抛钩子", "shot": "老板站在产线前开口", "caption": "工厂老板亲述"},
            {"t": "3-12s", "goal": "我们做什么/凭什么", "shot": "边走边说，背景是产线", "caption": "我们自己造"},
            {"t": "12-20s", "goal": "给合作方的承诺", "shot": "样品/质检/交期展示", "caption": "起订/交期/定制"},
            {"t": "20s+", "goal": "直接邀约", "shot": "老板看镜头邀约", "caption": "私信谈合作"},
        ],
        "hook_angles": ["『我是这家工厂的老板』", "『别再找中间商了』", "『想做我们的代理看完这条』"],
        "cta_style": "第一人称邀约：『私信我谈代理/拿样品/报价』。",
        "pacing": "口语、真诚、有底气；一镜到底或少量切镜更可信。",
        "platform": "TikTok/FB 通用；适合做主页置顶建立信任。",
    },
]

_BY_ID = {t["id"]: t for t in VIRAL_TEMPLATES}


def ids() -> list[str]:
    return [t["id"] for t in VIRAL_TEMPLATES]


def get(template_id: str) -> dict | None:
    return _BY_ID.get((template_id or "").strip().lower())


def for_persona(persona: str) -> list[dict]:
    """按 persona(product|factory) 过滤适用的模版。"""
    p = (persona or "product").strip().lower()
    return [t for t in VIRAL_TEMPLATES if p in t["applies_to"] or "both" in t["applies_to"]]


def menu(persona: str) -> str:
    """给 LLM 的『菜单』：精简列出可选模版，让它选一个最契合的并按其 beats 拍。"""
    lines = []
    for t in for_persona(persona):
        beats = " → ".join(b["goal"] for b in t["beats"])
        hooks = " / ".join(t["hook_angles"][:3])
        lines.append(
            f"[{t['id']}] {t['name']} — {t['best_for']}\n"
            f"    structure: {beats}\n"
            f"    hook angles: {hooks}\n"
            f"    CTA: {t['cta_style']}"
        )
    return "\n".join(lines)


def spec(template_id: str) -> str:
    """钉死某个模版时，给 LLM 的详细 beat 说明。"""
    t = get(template_id)
    if not t:
        return ""
    beats = "\n".join(
        f"    {b['t']}: {b['goal']} | shot: {b['shot']} | caption: {b['caption']}"
        for b in t["beats"]
    )
    return (
        f"USE THIS STRUCTURE — [{t['id']}] {t['name']} ({t['name_zh']})\n"
        f"  best for: {t['best_for']}\n"
        f"  buyer psychology: {t['psychology']}\n"
        f"  beats:\n{beats}\n"
        f"  hook angles to vary from: {' / '.join(t['hook_angles'])}\n"
        f"  CTA style: {t['cta_style']}\n"
        f"  pacing: {t['pacing']}\n"
        f"  platform: {t['platform']}"
    )
