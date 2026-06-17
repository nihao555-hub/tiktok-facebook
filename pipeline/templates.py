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
研究来源(均为公开资料)：
- TikTok Shop 官方 shoppable 内容指南：3 段结构 hook(前 3-6s,必须与产品相关) → key message(中段卖点) →
  CTA(口播+屏幕文字双触点，照顾静音观看)；4 大内容风格(真人测评/前后对比/开箱/分步教程)。
- 公开的 40+ 钩子公式拆解 → 归纳成 6 大心理类别(好奇缺口/反常识/转变/POV/直接提问/数字冲击)。
- 工厂/B2B 出海爆款 genre(MIT Tech Review 2025、Rest of World 2024 报道)：把产线变内容工作室、
  『揭秘大牌成本/砍掉中间商/我们就是代工厂』、车间溯源走查、人格化口音销售(LC Sign)、
  『娱乐拉量 vs 商业转化』平衡、约 1000 播放≈1 条询盘。
- 五幕结构(hook→context→demo→social proof→CTA)、PAS 最高转化。
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
    {
        "id": "cost_exposed",
        "name": "Cost Breakdown / Price Exposé",
        "name_zh": "成本拆解·价格祛魅(揭秘大牌成本)",
        "applies_to": ["factory", "both"],
        "best_for": "工厂找买家——当下 TikTok 最火的『源头工厂揭秘成本』genre(DHgate 同款)。",
        "psychology": "买家最想要的是『我能拿到比别人低的源头价』。把一件产品的真实物料/工费拆给观众看，"
                      "再对比终端零售价的巨大差价 → 既证明你是真源头，又点燃『绕开溢价直接找你』的冲动。",
        "beats": [
            {"t": "0-3s", "goal": "抛出价格反差钩子", "shot": "手拿成品+旁边写着零售价的牌子/对比", "caption": "卖฿XXX的东西，成本其实…"},
            {"t": "3-10s", "goal": "拆解真实成本", "shot": "镜头逐一指向原料/配件/工序，标注各项成本", "caption": "料฿X+工฿X"},
            {"t": "10-18s", "goal": "亮出源头身份", "shot": "把同款产品放回正在运转的产线/打标机上", "caption": "我们就是做这个的厂"},
            {"t": "18s+", "goal": "邀约直供", "shot": "成品+批量码货", "caption": "源头价私信"},
        ],
        "hook_angles": ["『卖฿990的东西，成本你绝对想不到』", "『让我拆给你看这到底值多少钱』", "『中间商不想让你知道的真实成本』"],
        "cta_style": "B2B：『想拿源头价/批发价，私信报 MOQ』。用差价本身完成说服，别硬吹。",
        "pacing": "拆解段每项给特写+数字停顿；真实车间收尾增强可信，别像广告。",
        "platform": "TikTok 揭秘向极吃量；FB 商家页可加联系方式。注意别诋毁具体品牌(合规)。",
    },
    {
        "id": "same_supplier",
        "name": "We Make It For The Big Brands",
        "name_zh": "大牌同源·我们就是代工厂",
        "applies_to": ["factory", "both"],
        "best_for": "给知名品牌/大商家代工过的工厂，想用『同源同质』背书拉买家。",
        "psychology": "『和大牌同一条线、同一种料，只是不能打那个标』给买家瞬间质量背书+捡漏快感，"
                      "信任成本直接清零。",
        "beats": [
            {"t": "0-4s", "goal": "同源宣称钩子", "shot": "产线上同时摆着自有款与『大牌同规格』款", "caption": "同一条线做出来的"},
            {"t": "4-12s", "goal": "证明同工同料", "shot": "同种原料/同台设备/同套QC标准特写", "caption": "同料·同设备·同QC"},
            {"t": "12-20s", "goal": "差别只在标", "shot": "对比两者细节几乎一致", "caption": "区别只是那个logo"},
            {"t": "20s+", "goal": "邀约贴牌", "shot": "可贴牌/定制包装展示", "caption": "贴你的牌·私信"},
        ],
        "hook_angles": ["『你买的大牌，可能就是我们这条线出的』", "『同样的料同样的工，只是不能打那个标』", "『带你看大牌背后的真实工厂』"],
        "cta_style": "『可做 OEM/ODM 贴你自己的牌，私信谈』。强调同质+可定制。",
        "pacing": "对比要克制、真实，避免点名具体品牌做虚假宣称(合规红线)。",
        "platform": "TikTok/FB 通用；这是当前出口工厂最火的角度之一。",
    },
    {
        "id": "cut_middleman",
        "name": "Cut Out The Middleman",
        "name_zh": "砍掉中间商·源头直连",
        "applies_to": ["factory"],
        "best_for": "想强调『绕开贸易商/代理层层加价、直连工厂』的源头厂。",
        "psychology": "买家被中间商加价、信息不透明坑怕了；『直连源头省一层钱+更快响应』直击利润与掌控感。",
        "beats": [
            {"t": "0-3s", "goal": "戳中间商痛点", "shot": "画一条『工厂→贸易商→你』的加价链条", "caption": "你多付的钱去哪了"},
            {"t": "3-11s", "goal": "亮出工厂本体", "shot": "真实产线/门牌/营业执照一闪而过", "caption": "我们=源头工厂"},
            {"t": "11-19s", "goal": "直连的好处", "shot": "工程师直接对接/打样/改款画面", "caption": "直连·直报价·直改款"},
            {"t": "19s+", "goal": "邀约直连", "shot": "工厂联系人/微信二维码位(留白)", "caption": "跳过中间商私信"},
        ],
        "hook_angles": ["『别再被贸易商赚差价了』", "『你以为找的是工厂，其实是二道贩子』", "『源头直连能省多少，我算给你看』"],
        "cta_style": "『直接对接工厂，私信拿出厂价+样品』。",
        "pacing": "节奏明快、信息透明感强；露一点真实厂区/执照增强可信。",
        "platform": "TikTok/FB 通用；适合做账号定位置顶。",
    },
    {
        "id": "salesman_skit",
        "name": "Character Salesman Skit",
        "name_zh": "人格化销售·段子带货(娱乐×生意)",
        "applies_to": ["factory", "both"],
        "best_for": "想靠『有人味、好笑、记得住』的销售人设破圈拉询盘(参考 LC Sign 灯箱厂)。",
        "psychology": "纯硬广没量、纯搞笑没单；用一个夸张但讨喜的销售角色把产品演出来，娱乐拉量、"
                      "人设建立信任，留下询盘。『1000 播放≈1 条询盘』。",
        "beats": [
            {"t": "0-3s", "goal": "角色化开场钩子", "shot": "销售人设(夸张口吻/道具)直面镜头登场", "caption": "人设台词"},
            {"t": "3-12s", "goal": "用段子演产品卖点", "shot": "边演边把产品/产线当道具展示", "caption": "卖点融进梗里"},
            {"t": "12-20s", "goal": "梗收口+亮实力", "shot": "回到真实车间/产品收住", "caption": "其实我们很能打"},
            {"t": "20s+", "goal": "邀约", "shot": "角色眨眼邀约", "caption": "私信这位销售"},
        ],
        "hook_angles": ["夸张口音/角色开场『What's up homie, I'm…』", "把自己演成侦探/超级英雄查产品", "自嘲式『我老板逼我拍的』"],
        "cta_style": "角色化邀约：『私信我(这个憨憨销售)拿报价』。保持娱乐与生意的平衡。",
        "pacing": "节奏要有梗有反差，但别太闹以致掩盖产品；结尾一定要回到真实实力。",
        "platform": "TikTok/FB/IG 通用；人设可系列化做账号资产。",
    },
    {
        "id": "factory_day",
        "name": "A Day At Our Factory (BTS Vlog)",
        "name_zh": "工厂的一天·幕后日常",
        "applies_to": ["factory"],
        "best_for": "用『真实、有温度的幕后』建立长期信任，适合系列化更新。",
        "psychology": "买家想知道『跟我合作的是什么样的人和厂』。把一天的真实运转(开工/午饭/赶单/发货)"
                      "拍成 vlog，人味+确定性=愿意长期合作。",
        "beats": [
            {"t": "0-3s", "goal": "一天开始的钩子", "shot": "清晨工厂开灯/开机第一镜", "caption": "工厂的一天 6:30"},
            {"t": "3-12s", "goal": "真实运转剪影", "shot": "上料→生产→质检→打包 快剪带时间戳", "caption": "今天赶XX单"},
            {"t": "12-20s", "goal": "人和细节", "shot": "工人协作/午饭/老板巡线 等有温度画面", "caption": "我们这帮人"},
            {"t": "20s+", "goal": "发货收尾+邀约", "shot": "傍晚货车装柜出厂", "caption": "想合作来聊"},
        ],
        "hook_angles": ["『跟我过一天工厂生活』", "『赶一个泰国大单的一天』", "『带你看货是怎么从这里发出去的』"],
        "cta_style": "『想长期稳定供货的，私信认识一下』。柔性、关系导向。",
        "pacing": "vlog 节奏、时间戳、真实环境声；可系列连更养粉。",
        "platform": "TikTok/FB/IG 通用；连载性强、利于账号留存。",
    },
    {
        "id": "raw_to_finished",
        "name": "Raw Material → Finished Product",
        "name_zh": "从原料到成品·一镜到底全过程",
        "applies_to": ["factory", "both", "product"],
        "best_for": "工艺有观赏性/解压感的品类(金属/激光/注塑/食品/纺织)。展示真实制造力。",
        "psychology": "完整看到一块原料变成成品=极强的『真实制造』证据+满足感，停留与复播都高，"
                      "顺带证明产能与工艺。",
        "beats": [
            {"t": "0-2s", "goal": "原料起点钩子", "shot": "一块毫不起眼的原料特写", "caption": "它会变成什么?"},
            {"t": "2-16s", "goal": "工序逐步推进", "shot": "切割/成型/打标/抛光/组装 连续快剪(同期声)", "caption": "Step感/极简字"},
            {"t": "16-22s", "goal": "成品揭晓", "shot": "精致成品 hero，呼应开头原料", "caption": "成品就是它"},
            {"t": "22s+", "goal": "产能+邀约", "shot": "成批同款成品码货", "caption": "批量可做·私信"},
        ],
        "hook_angles": ["『一块铁→成品，看到最后』", "纯工艺声开场0解说", "『猜猜这堆料能做出啥』"],
        "cta_style": "看完工艺顺势『同款可批量定制，私信』。",
        "pacing": "保留真实机器/工艺同期声(ASMR感)，关键转变给特写定格。",
        "platform": "TikTok 解压/工艺向极吃量；Reels 同样有效。",
    },
    {
        "id": "moq_friendly",
        "name": "Small Orders Welcome (Low MOQ)",
        "name_zh": "小单也接·起订无压力",
        "applies_to": ["factory"],
        "best_for": "面向中小卖家/新品牌/想先试市场的买家，破除『工厂只接大单』顾虑。",
        "psychology": "很多买家想合作但怕 MOQ 太高、压货风险大；明确『小起订+可试单+可混款』直接拆掉最大门槛。",
        "beats": [
            {"t": "0-3s", "goal": "戳起订量焦虑", "shot": "对镜头『怕起订量太高不敢问?』", "caption": "怕MOQ太高?"},
            {"t": "3-11s", "goal": "给出低门槛", "shot": "展示小批量打包/可混款/试单", "caption": "MOQ低·可试单"},
            {"t": "11-19s", "goal": "试单也认真做", "shot": "小单同样过QC/同样品质", "caption": "小单一样全检"},
            {"t": "19s+", "goal": "邀约试单", "shot": "样品盒/小批成品", "caption": "先试一单·私信"},
        ],
        "hook_angles": ["『不用一上来就下大单』", "『新手卖家也能合作的工厂』", "『先试 X 件试市场，行了再加』"],
        "cta_style": "『先从小单/打样开始，私信报你的量』。降低决策压力。",
        "pacing": "真诚、解决顾虑导向；把数字(MOQ/打样周期)讲清楚。",
        "platform": "TikTok/FB 通用；适合承接评论区『MOQ多少』的高频问题。",
    },
    {
        "id": "sourcing_traps",
        "name": "Sourcing Mistakes / How To Spot A Real Factory",
        "name_zh": "采购避坑清单·怎么辨别真工厂",
        "applies_to": ["factory"],
        "best_for": "用『教买家避坑』的价值内容换信任，把自己立成『懂行、靠谱的源头』。",
        "psychology": "先给买家可执行的避坑知识(利他)→建立专家信任→结尾自然证明『我们正好就符合这些标准』。",
        "beats": [
            {"t": "0-3s", "goal": "清单承诺钩子", "shot": "对镜头/大字『进货前必看的X个坑』", "caption": "采购避坑3件事"},
            {"t": "3-9s", "goal": "坑1+怎么辨别", "shot": "演示辨别要点1(如要营业执照/验厂)", "caption": "1️⃣ 要看…"},
            {"t": "9-15s", "goal": "坑2", "shot": "辨别要点2(如样品与大货一致)", "caption": "2️⃣ 别踩…"},
            {"t": "15-21s", "goal": "坑3(最狠放最后)", "shot": "辨别要点3(如付款/交期陷阱)", "caption": "3️⃣ 最坑的是…"},
            {"t": "21s+", "goal": "我们正好达标+邀约", "shot": "亮出自家对应的证据", "caption": "我们都做到了·私信"},
        ],
        "hook_angles": ["『从中国/泰国进货前，这3个坑必看』", "『90%的新买家都被这个套路过』", "『教你一眼看穿假工厂』"],
        "cta_style": "『想找符合这些标准的源头，私信我』。先利他后邀约。",
        "pacing": "每条 4-6s、字幕标号、节奏快；最痛的坑压轴。",
        "platform": "TikTok/FB 通用；可保存/转发，长尾流量好。",
    },
    {
        "id": "qc_torture",
        "name": "QC Torture / Stress Test",
        "name_zh": "品控暴力测试·当面验质量",
        "applies_to": ["factory", "both", "product"],
        "best_for": "质量是核心卖点的品类；用『现场虐测』把质量可视化、可信化。",
        "psychology": "买家最怕『货到品质拉垮』。当面做跌落/拉力/防水/打标耐磨等测试，眼见为实，信任直接拉满。",
        "beats": [
            {"t": "0-3s", "goal": "虐测钩子", "shot": "手举产品准备施加暴力测试", "caption": "敢这样测吗?"},
            {"t": "3-13s", "goal": "现场测试", "shot": "跌落/拉扯/泡水/刮擦/称重 真实测试(安全合规)", "caption": "实测中"},
            {"t": "13-20s", "goal": "结果完好", "shot": "测试后产品完好特写", "caption": "毫发无伤"},
            {"t": "20s+", "goal": "品控承诺+邀约", "shot": "每批全检画面", "caption": "每批全检·私信"},
        ],
        "hook_angles": ["『拿我们的货来虐一下』", "『敢测才敢卖』", "『这质量，随便摔』"],
        "cta_style": "『质量看得见，私信拿样品自己测』。鼓励对方索样自测。",
        "pacing": "测试动作要真实、安全、不伤人(过安全过滤)；结果给停顿特写。",
        "platform": "TikTok/FB 通用；信任向，转化与收藏都不错。",
    },
    {
        "id": "capacity_flex",
        "name": "Capacity / Numbers Flex (Stat Shock)",
        "name_zh": "产能数字冲击·规模碾压开场",
        "applies_to": ["factory"],
        "best_for": "产能/设备/出口规模是硬实力的工厂；用大数字一秒建立『这家很能打』。",
        "psychology": "具体大数字=可信+震撼，瞬间筛出真正有量级需求的买家，并压制『你们做得了我的量吗』疑虑。",
        "beats": [
            {"t": "0-3s", "goal": "数字冲击钩子", "shot": "产线大全景+巨大数字浮现", "caption": "日产30,000+件"},
            {"t": "3-11s", "goal": "用画面坐实数字", "shot": "成排设备满负荷/堆到天花板的成品", "caption": "20+台设备"},
            {"t": "11-19s", "goal": "更多硬指标", "shot": "出口国地图/认证墙/仓储规模", "caption": "出口30+国"},
            {"t": "19s+", "goal": "承接大单邀约", "shot": "装柜出货", "caption": "大单交得了·私信"},
        ],
        "hook_angles": ["『一天能产 X 件』", "『X 台设备同时开工是什么概念』", "『X 个国家的买家都在我们这拿货』"],
        "cta_style": "『有量的买家直接私信，交期产能都顶得住』。",
        "pacing": "数字与画面强绑定、节奏震撼；别空喊数字，要有对应实拍。",
        "platform": "TikTok/FB 通用；适合做实力背书型内容。",
    },
    {
        "id": "client_visit",
        "name": "Real Buyer Visits The Factory",
        "name_zh": "海外买家验厂·客户来访(社会证明)",
        "applies_to": ["factory"],
        "best_for": "有真实客户来访/验厂/复购的工厂；用第三方背书打消信任顾虑。",
        "psychology": "『别人(尤其同类买家)已经来验过、已经在合作』是最强社会证明，让观望买家从众跟进。",
        "beats": [
            {"t": "0-3s", "goal": "来访钩子", "shot": "买家走进厂区/握手/参观第一镜", "caption": "又一个买家来验厂"},
            {"t": "3-12s", "goal": "带看产线", "shot": "陪同参观产线/看样/谈合作", "caption": "亲眼看产能"},
            {"t": "12-20s", "goal": "认可与下单", "shot": "看样满意/签约/装样品带走", "caption": "当场定了"},
            {"t": "20s+", "goal": "欢迎更多来访+邀约", "shot": "厂区门口欢迎牌", "caption": "欢迎来验厂·私信"},
        ],
        "hook_angles": ["『泰国买家专程飞来验厂』", "『又一个回头客来补单』", "『眼见为实，欢迎随时来看厂』"],
        "cta_style": "『想来验厂或视频看厂的，私信安排』。强调透明、可考察。",
        "pacing": "真实、自然，避免摆拍感；保护对方隐私(可不出正脸)。",
        "platform": "TikTok/FB 通用；社会证明型，信任转化高。",
    },
    {
        "id": "why_us_vs_platform",
        "name": "Why Buy Direct vs Alibaba / Middleman",
        "name_zh": "为什么直连我们而不是平台/中间商",
        "applies_to": ["factory"],
        "best_for": "对标买家既有的采购路径(B2B平台/贸易商)，论证直连工厂更优。",
        "psychology": "买家已有采购习惯(Alibaba/1688/展会/贸易商)，给出『直连更便宜/更快/更可改款』的清晰对照，"
                      "推动他换路径找你。",
        "beats": [
            {"t": "0-3s", "goal": "对照命题钩子", "shot": "左『平台/中间商』右『工厂直连』分屏", "caption": "平台 vs 源头"},
            {"t": "3-12s", "goal": "逐项对比", "shot": "价格/响应速度/改款/起订 并排对照", "caption": "价/速/改款"},
            {"t": "12-20s", "goal": "拉开优势", "shot": "工厂侧的优势证据(直报价/工程师)", "caption": "差距在这"},
            {"t": "20s+", "goal": "邀约直连", "shot": "工厂联系入口位(留白)", "caption": "直连更省·私信"},
        ],
        "hook_angles": ["『在Alibaba一年花฿X曝光，不如直连工厂』", "『中间商 vs 源头，差的不只是价格』", "『为什么聪明的买家都直接找厂』"],
        "cta_style": "『直连工厂，价格响应都更好，私信对比一下』。理性对照、不诋毁平台。",
        "pacing": "对照清晰、公平感；用并排分屏强化记忆。",
        "platform": "TikTok/FB 通用；适合承接『为什么选你们』的转化型内容。",
    },
]

# --------------------------------------------------------------------------
# 钩子公式库（hook bank）：6 大心理类别 × 多条可套用公式。
# 注入到 LLM 提示里做「钩子角度轮换」，是对抗多工厂同质化的关键之一。
# 研究来源：TikTok Shop 官方 shoppable 内容指南(hook 3-6s/key message/CTA)、
# 公开的 40+ 钩子公式拆解、对工厂/B2B 出海爆款(揭秘成本/大牌同源/砍中间商/口音段子)的归纳。
# --------------------------------------------------------------------------
HOOK_CATEGORIES: list[dict] = [
    {
        "id": "curiosity_gap",
        "name_zh": "好奇缺口",
        "why": "制造一个信息缺口，大脑本能想补全 → 留下来看答案。",
        "formulas": [
            "卖฿{price}的东西，成本其实是…(拆给你看)",
            "没人告诉你的{话题}，但它改变了一切",
            "大牌不想让你知道的{秘密}",
            "我花了{时长}搞懂{事}，直接讲给你",
        ],
    },
    {
        "id": "contrarian",
        "name_zh": "反常识/争议",
        "why": "挑战既有认知，观众停下来评估你的说法 → 听你讲理由。",
        "formulas": [
            "别再{常见做法}了，真正有用的是这个",
            "你买的大牌，可能就是我们这条线出的",
            "在{平台}花฿{钱}曝光，不如直接找工厂",
            "{大家都信的事}其实是反的，原因是…",
        ],
    },
    {
        "id": "transformation",
        "name_zh": "转变/前后",
        "why": "大脑对『落差/变化』反应最强，越大越想看。",
        "formulas": [
            "一块{原料}→成品，看到最后",
            "{糟糕现状}→{惊艳结果}，过程在这",
            "这堆料能做出什么?猜猜看",
            "{时长}里它变成了这样",
        ],
    },
    {
        "id": "pov_identity",
        "name_zh": "POV/身份代入",
        "why": "让目标买家在开头一秒认出『这说的就是我』。",
        "formulas": [
            "POV: 你是想找泰国市场货源的卖家",
            "如果你正在{买家处境}，这条必看",
            "做{某品类}的卖家都懂的痛",
            "怕MOQ太高不敢问工厂?这条给你",
        ],
    },
    {
        "id": "direct_question",
        "name_zh": "直接提问",
        "why": "抛一个观众不看完答不上的问题(且自以为知道答案)。",
        "formulas": [
            "你多付给中间商的钱，知道去哪了吗?",
            "怎么一眼辨别真工厂还是二道贩子?",
            "这质量你敢这样摔吗?",
            "同样的料同样的工，为什么价格差这么多?",
        ],
    },
    {
        "id": "stat_shock",
        "name_zh": "数字冲击",
        "why": "具体数字=可信+震撼，瞬间重塑认知。",
        "formulas": [
            "一天能产{数量}件是什么概念",
            "{数量}台设备同时开工",
            "{数量}个国家的买家都在我们这拿货",
            "{比例}的新买家都踩过这个坑",
        ],
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


def hook_bank() -> str:
    """钩子公式库 → 喂给 LLM 做『钩子角度轮换』，对抗多工厂/多片同质化。

    指示 LLM：每条片子从不同心理类别里挑一个钩子角度，台词现写、别套死公式。
    """
    lines = ["HOOK BANK — vary the opening hook EVERY video by rotating across these "
             "psychological categories (pick one that fits, then write a FRESH line in "
             "the target language; never reuse a canned formula verbatim):"]
    for c in HOOK_CATEGORIES:
        fs = " | ".join(c["formulas"])
        lines.append(f"  [{c['id']}] {c['name_zh']} — {c['why']}\n    e.g. {fs}")
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
