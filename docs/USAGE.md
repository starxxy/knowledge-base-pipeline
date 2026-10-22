# 知识库使用说明（网页版 / API / MCP）

> 个人知识库：Markdown 条目 + 图片资产 + 单文件网页查看器 + 登录服务 + MCP/HTTP 双通道。
> 数据源：`E:\deepseek\knowledge-base`（Windows 开发机），网页版部署在飞牛 NAS。

## 1. 网页版（人看）

- 地址：<http://192.168.15.100:8899>（同一局域网）
- 登录：`stary` / 密码见微信（30 天免登录）；右上角可退出
- 界面：Docmost 风格三栏（左侧导航/标签/用户，中间目录，右侧正文），支持深色模式与手机端抽屉
- 发布：本地改动后跑 `powershell -File scripts/kb-publish.ps1`（构建 + scp + 拉起服务）

## 2. 入库方式（agent 做）

把链接直接发给 DSH 助手即可，流水线自动处理：

| 平台 | 支持形式 | 脚本 |
|---|---|---|
| 抖音 | 分享短链 | `scripts/douyin-ingest.ps1`（下载视频 + GPU 转写） |
| 微信公众号 | 文章链接 / 分享页 | `scripts/wechat-ingest.py` / `scripts/kb-ingest-wechat-share.py` |
| 小红书 | xhslink 短链 | `scripts/kb-ingest-xhs.py` |
| B站 | b23.tv 短链 | `scripts/kb-ingest-bili.py`（yt-dlp 下载 + 转写） |

条目统一结构：frontmatter（类型/标题/来源/标签）+ 一句话总结 + 核心内容 + 金句 + 资源清单 + 图片存档 + 逐字稿/原文。

## 3. HTTP API（agent 远程调用）

基地址 `http://192.168.15.100:8899`，鉴权二选一：网页登录 Cookie，或 `Authorization: Bearer <token>`。

获取 token（NAS 上执行）：

```bash
python3 /vol1/1000/kb-server/kb-server.py \
  --root /vol1/1000/kb-web --users /vol1/1000/kb-server/kb-users.json --show-token
```

| 端点 | 参数 | 说明 |
|---|---|---|
| `GET /api/stats` | — | 总数与各来源数量 |
| `GET /api/search` | `q` 关键词、`type` 可选（抖音视频/微信公众号/小红书/哔哩哔哩视频/笔记）、`limit` 默认 10 | 全文检索，返回路径/标题/片段 |
| `GET /api/entry` | `id` 条目相对路径 | 返回 frontmatter + 完整 Markdown |

示例：

```bash
curl -H "Authorization: Bearer $TOKEN" "http://192.168.15.100:8899/api/search?q=三角洲&limit=5"
curl -H "Authorization: Bearer $TOKEN" "http://192.168.15.100:8899/api/entry?id=bili/BV1tFJ26bEeQ_p1.md"
```

## 4. MCP（agent 标准接入）

服务器：`scripts/kb-mcp.py`（stdio，无第三方依赖）。工具四个：
`kb_search(query, type?, limit?)`、`kb_get(path)`、`kb_list(type?)`、`kb_stats()`。

注册示例：

```jsonc
// Claude Code: claude mcp add kb -- python E:\deepseek\kb-tools\kb-mcp.py
// 通用 JSON（Cursor / Cline / DSH 等）：
{
  "mcpServers": {
    "kb": { "command": "python", "args": ["E:\\deepseek\\kb-tools\\kb-mcp.py"] }
  }
}
```

CLI 直用（不配 MCP 也能调）：

```bash
python scripts/kb-mcp.py --cli search "三角洲" --limit 5
python scripts/kb-mcp.py --cli get "bili/BV1tFJ26bEeQ_p1.md"
python scripts/kb-mcp.py --cli stats
```

远程机器可把 `KB_HOME` 指向挂载盘，或改用 HTTP API。

## 5. 备份与恢复

| 仓库 | 内容 | 地址 |
|---|---|---|
| `knowledge-base-pipeline` | 网页代码 + 脚本 + 文档（本仓库） | 飞牛 Gitea `stary/knowledge-base-pipeline`（另有 GitHub 镜像） |
| `knowledge-base-data` | 知识库数据全量（条目 + 图片资产 + 索引） | 飞牛 Gitea `stary/knowledge-base-data` |

恢复：`git clone` 对应仓库即可；网页服务重建 = `scp scripts/kb-server.py` 到 NAS 后按 §3 启动。

## 6. 服务管理（NAS）

```bash
pgrep -af kb-server.py                 # 状态
pkill -f kb-server.py                  # 停止
setsid nohup python3 /vol1/1000/kb-server/kb-server.py \
  --root /vol1/1000/kb-web --port 8899 \
  --users /vol1/1000/kb-server/kb-users.json > /vol1/1000/kb-server/server.log 2>&1 &
```
