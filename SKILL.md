---
name: knowledge-base-pipeline
description: 把抖音视频和微信公众号文章自动收进本地 Markdown 知识库：抓取正文/取视频直链、GPU 语音转写、按模板生成带摘要和标签的条目标注、生成可双击打开的本地浏览页。Use when the user shares a Douyin video link or a WeChat article link and wants it archived, transcribed, summarized, or searchable in their own knowledge base.
---

# knowledge-base-pipeline

把「你发一条链接」变成「知识库里多一条可检索的笔记」。

## 什么时候用

- 用户发来抖音分享链接（`v.douyin.com/...`）或微信公众号文章链接（`mp.weixin.qq.com/s/...`）
- 用户想把收藏的视频/文章沉淀成可搜索的个人知识库
- 用户想批量整理历史收藏

## 能做什么

| 环节 | 抖音视频 | 公众号文章 |
|---|---|---|
| 抓取 | 浏览器取无水印直链（视频/音频分轨自动合并） | 直抓正文 + 图片存档，被验证码拦截时浏览器兜底 |
| 转文字 | faster-whisper large-v3（CUDA，约 2–5 倍实时速度） | 不需要 |
| 落库 | NAS/磁盘归档，文件名=视频标题 | 图片存 `_assets/`，正文全文入库 |
| 提炼 | AI 读逐字稿，回填「一句话总结 / 核心内容 / 金句」 | 同样回填，另加「对我的价值」 |
| 索引 | 更新 `INDEX.md`（倒序） | 同左 |
| 浏览 | `kb-build.py` 生成单文件 `index.html`，双击即可搜索浏览 | 同左 |

## 前置条件

- Windows + PowerShell 5.1+（抖音线用 PowerShell，公众号线用 Python）
- Python 3.10+，`pip install requests beautifulsoup4 lxml faster-whisper markdown`
- ffmpeg / ffprobe 在 PATH
- 抖音取流需要 `agent-browser`（`npm i -g agent-browser`）
- 可选：NVIDIA GPU（转写用，CPU 也能跑只是慢）

## 配置

复制 `config.example.json` 为 `config.json` 并改成本机路径；也可用环境变量覆盖（`KB_HOME`、`KB_MEDIA_DIR`、`KB_PYTHON`、`KB_FFMPEG`）。

```json
{
  "kb_home": "D:/knowledge-base",
  "media_dir": "Z:/douyin-media",
  "python": "python",
  "ffmpeg": "ffmpeg",
  "agent_browser_session": "kb-douyin",
  "whisper_model": "large-v3",
  "whisper_device": "cuda"
}
```

## 用法

```powershell
# 抖音：取流 → 下载/合并 → 转写 → 生成条目 + 索引
powershell -ExecutionPolicy Bypass -File scripts/douyin-ingest.ps1 -Url "https://v.douyin.com/xxxx/"

# 公众号
python scripts/wechat-ingest.py "https://mp.weixin.qq.com/s/xxxx"

# 重建本地浏览页
python scripts/kb-build.py
```

抖音脚本只生成**草稿**（逐字稿已内嵌、总结待填）。AI 接下来要做的收尾：

1. 读 `douyin/<视频ID>.md` 里的逐字稿
2. 回填「一句话总结」「核心内容」「金句 / 可复用片段」，把 `标签: []` 换成 3–6 个标签
3. 更新 `INDEX.md` 对应行的标题与标签，再跑一次 `kb-build.py`

## 输出结构

```
knowledge-base/
├── douyin/            # 每条视频一个 .md（逐字稿内嵌）
├── wechat/            # 每篇文章一个 .md（正文全文内嵌）
├── notes/             # 自己整理的对比/总结类笔记
├── _assets/wechat/    # 文章图片
├── _media/            # 转写用临时音频（可清理）
├── INDEX.md           # 总索引，入库时间倒序
└── index.html         # kb-build.py 生成的浏览页
```

## 条目模板

见 `templates/douyin.md` 与 `templates/wechat.md`。字段保持稳定，方便后续脚本和检索。

## 注意

- 只处理用户有权保存的内容，仅个人自用，不要再分发。
- 抖音 Web 端经常调整协议；`douyin-ingest.ps1` 依赖网络日志里的媒体直链，如果取不到，先确认 `agent-browser` 能正常打开视频页。
- 公众号被「环境异常」拦截时换 UA 重试，仍失败再用浏览器兜底。
- 批量抓取请放慢频率，避免触发风控。
