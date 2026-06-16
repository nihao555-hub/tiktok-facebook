"""可插拔的外部能力 provider：文案(LLM)、片段生成(clipgen)、配音(TTS)。

设计原则：每个能力都有一个"零 key 也能跑"的默认实现，真实 key 通过 .env 注入后切换。
"""
