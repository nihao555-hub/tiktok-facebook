# tiktok-facebook 投流视频流水线

一条可在 **Linux 无界面环境直接跑通** 的 TikTok / Facebook 投流视频流水线：

```
选题脚本(LLM) → 文生图/图生图(超写实) → 图生视频 → 配音(TTS) → 字幕(ASR 词级时间戳)
   → 原生混剪 + 平台装饰(FFmpeg) → 可编辑 CapCut 草稿(pyJianYingDraft) → 发布(TikTok/Facebook)
```

设计原则：**每一步都有"零 key 也能跑通"的默认实现**，你自己的 API key 通过 `.env` 注入后即切换为真实能力。
渲染核心是 FFmpeg（Linux 可直接出 MP4）；同时额外导出一份 **剪映/CapCut 可编辑草稿**，方便你在桌面端套原生模板/转场/热门音乐再精修。

**已接线的默认真实能力栈**（在 `.env` 填好对应 key 即生效）：

| 能力 | 服务 | 模型 |
|---|---|---|
| 文案/分镜脚本 | grsai（OpenAI 兼容） | `gpt-5.5` |
| 文生图 / 图生图（超写实） | grsai | `gpt-image-2` |
| 图生视频 / 文生视频 | 无垠科技 wuyinkeji | `video_google_omni` |
| 配音 TTS | ElevenLabs | `eleven_multilingual_v2` |

图生图会吃 `media/refs/` 里你的真实商品/工厂图，强约束"100% 真实世界质感、看不出 AI"；
生成视频右下角的 AI 角标会用 `delogo` 自动抹掉。

> 内容打法（买家画像 / 痛点公式 / 两套分镜脚本模板 / TikTok·FB 原生形式差异）见 [`docs/STRATEGY.md`](docs/STRATEGY.md)。
> 流水线里 `prompts/factory_persona.md`（工厂展示·B2B）与 `prompts/product_persona.md`（单品带货·B2C）就是这套打法喂给 LLM 的角色提示。

## 目录结构

```
pipeline/
  config.py           读取 YAML 任务配置 + .env 密钥
  script_model.py     分镜脚本数据结构
  providers/
    llm.py            文案/分镜脚本（grsai gpt-5.5；OpenAI 兼容；无 key 用模板兜底）
    imagegen.py       文生图/图生图（grsai gpt-image-2，超写实，吃 media/refs 真实素材）
    clipgen.py        AI 片段生成（wuyinkeji 图生视频默认；local 零key兜底；replicate/kling/... 预留）
    tts.py            配音（elevenlabs 默认；edge 免 key 兜底；openai/azure 可选）
  subtitles.py        faster-whisper 词级时间戳 → TikTok 风格逐词字幕 + 大钩子 + CTA (ASS)
  mixer.py            FFmpeg 混剪 + 进度条 + logo + BGM
  capcut_export.py    pyJianYingDraft 导出可编辑剪映/CapCut 草稿
  publish/
    tiktok.py         TikTok Content Posting API
    facebook.py       Facebook Graph API（Reels / Feed）
  run.py              编排 CLI
prompts/              两条业务线的买家画像/形式指南（喂 LLM）
media/refs/           放你的真实商品/工厂图（图生图参考；不入库）
media/clips/          放你的素材（图片/视频）；为空时自动合成占位片段
media/bgm/            背景音乐
output/<project>/     产物：final.mp4 / variant_*.mp4 / script.json / capcut_draft/
config.example.yaml   任务配置模板
.env.example          密钥模板
```

## 安装

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 需要系统已安装 ffmpeg / ffprobe
```

## 快速开始（零 key 也能出片）

```bash
cp config.example.yaml config.yaml      # 改成你的产品/工厂信息
python -m pipeline.run --config config.yaml
```

不填任何 key 时：用模板文案 + edge-tts 配音 + whisper 字幕 + 占位片段，直接产出 `output/<project>/final.mp4`。
把素材放进 `media/clips/` 后，会自动用你的素材替代占位片段做混剪。

## 接你自己的 key

复制 `.env.example` 为 `.env` 按需填写（都可选）：

| 能力 | 变量 | 说明 |
|---|---|---|
| 文案 LLM | `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | grsai 默认（`gpt-5.5`）；OpenAI 兼容，也支持 OpenAI / DeepSeek / 通义 / 豆包 / Gemini |
| 文生图/图生图 | `IMAGE_PROVIDER` / `GRSAI_API_KEY` / `IMAGE_MODEL` | provider: `grsai`(默认 `gpt-image-2`)；吃 `media/refs/` 做图生图 |
| AI 片段生成 | `CLIPGEN_PROVIDER` / `WUYIN_API_KEY` / `WUYIN_ENDPOINT` | provider: `wuyinkeji`(默认 `video_google_omni`) / `local` / `replicate` / `kling` / `openai_video` / `runway` |
| 配音 TTS | `TTS_PROVIDER` / `TTS_VOICE` / `TTS_API_KEY` | provider: `elevenlabs`(默认) / `edge`(免key) / `openai` / `azure` |
| 发布 TikTok | `TIKTOK_ACCESS_TOKEN` | Content Posting API（默认关闭） |
| 发布 Facebook | `FB_PAGE_ID` / `FB_PAGE_ACCESS_TOKEN` | Graph API（Reels/Feed，默认关闭） |

> 在线片段生成 provider（replicate/kling/openai_video/runway）在 `pipeline/providers/clipgen.py`
> 里预留了函数位：确认你用哪个服务后，在对应 `_gen_*` 函数里补上请求即可（统一返回下载到本地的视频路径）。

## A/B 多版本（投流测素材）

`config.yaml` 的 `variants.hooks` / `variants.bgms` 各填多个，会复用同一份底片+配音，
只替换钩子文案 / 背景音乐，批量产出 `variant_*.mp4`，用于投流跑量测试。

## 发布

```bash
# 在 config.yaml 把 publish.tiktok / publish.facebook 置 true，并在 .env 配好 token
python -m pipeline.run --config config.yaml --publish
```

TikTok 默认以 `SELF_ONLY`（自见/草稿）发布，确认无误后在 `pipeline/publish/tiktok.py` 改为 `PUBLIC_TO_EVERYONE`。

## 关于剪映/CapCut 草稿

`pipeline/capcut_export.py` 会把分镜片段/配音/大字按时间轴写成 `output/<project>/capcut_draft/draft_content.json`。
**Linux 上的成片由 FFmpeg 完成**；草稿是额外提供的"原生可编辑工程"路径——
导出的草稿在你自己电脑的 剪映/CapCut 里打开，可套原生模板、转场、贴纸、平台热门音乐后再导出（这一步需要桌面端，无法在本机无界面渲染）。
`--no-capcut` 可跳过草稿导出。
