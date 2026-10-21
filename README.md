# knowledge-base-pipeline

把抖音视频和微信公众号文章，自动收进你自己的本地 Markdown 知识库。

> 一条链接进去，一条可以搜索、可以问 AI 的笔记出来。

## 它做什么

```
分享链接 ──► 抓取 ──► 转写/正文 ──► AI 提炼 ──► Markdown 条目 ──► 索引 + 本地浏览页
```

| 环节 | 抖音视频 | 公众号文章 |
|---|---|---|
| 抓取 | 浏览器取无水印直链，视频/音频分轨自动合并 | 直抓正文 + 图片存档 |
| 转文字 | faster-whisper large-v3（GPU） | — |
| 落库 | 视频存 NAS/磁盘，文件名=视频标题 | 图片存 `_assets/`，正文全文入库 |
| 提炼 | AI 回填总结/要点/金句 | 同左，另加「对我的价值」 |
| 浏览 | 生成单文件 `index.html`，双击即用 | 同左 |

**实测速度**：公众号文章 3–8 秒；2 分钟左右的抖音视频约 30–40 秒（含下载、合并、GPU 转写）。

## 快速开始

```bash
# 1. 依赖
pip install requests beautifulsoup4 lxml faster-whisper markdown
npm i -g agent-browser          # 抖音取流用
ffmpeg -version                 # 需要 ffmpeg / ffprobe

# 2. 配置
cp config.example.json config.json   # 改成你自己的路径

# 3. 用
powershell -ExecutionPolicy Bypass -File scripts/douyin-ingest.ps1 -Url "https://v.douyin.com/xxxx/"
python scripts/wechat-ingest.py "https://mp.weixin.qq.com/s/xxxx"
python scripts/kb-build.py
```

抖音脚本产出的是**草稿**：逐字稿已在正文里，把「一句话总结 / 核心内容 / 金句」交给 AI 填，再跑一次 `kb-build.py` 就有可搜索的浏览页了。

## 目录结构

```
knowledge-base/
├── douyin/            # 每条视频一个 .md
├── wechat/            # 每篇文章一个 .md
├── notes/             # 自己整理的笔记（可选）
├── _assets/wechat/    # 文章图片
├── _media/            # 转写临时音频
├── INDEX.md           # 总索引，倒序
└── index.html         # 浏览页（kb-build.py 生成）
```

## 配置项

`config.json`（或环境变量，同名大写加 `KB_` 前缀）：

| 键 | 说明 |
|---|---|
| `kb_home` | 知识库根目录 |
| `media_dir` | 视频/大文件归档目录（可以是 NAS 挂载盘） |
| `python` | Python 解释器路径 |
| `agent_browser_session` | agent-browser 会话名，用于复用浏览器 |
| `whisper_model` / `whisper_device` | 转写模型与设备（`cuda` / `cpu`） |

## 设计取舍

- **Markdown 优先**：文件即数据，不锁定任何软件；Obsidian、思源、VS Code 都能直接读。
- **大文件分离**：视频留在 NAS/磁盘，知识库只存文字与图片，方便同步与备份。
- **能不用服务就不用服务**：没有常驻后端，脚本跑完就退出。
- **取流而不是下载收藏夹**：抖音 Web 端会变协议，脚本用「页面时长校验」确认拿到的是本视频，避免把上一条的内容写进新条目。

## 已知限制

- 抖音 Web 端协议可能随时变化；取不到直链时先确认 `agent-browser` 能正常打开视频页。
- 公众号被「环境异常」拦截时换 UA 重试，仍失败需浏览器兜底。
- 转写在 CPU 上会明显变慢；建议用 CUDA。
- 仅用于个人自用，请遵守平台条款与版权规定。

## Roadmap

- [ ] 浏览器兜底抓公众号的独立脚本
- [ ] 思源笔记 / Obsidian 增量同步
- [ ] 视频号、B 站、YouTube 适配

## License

MIT
