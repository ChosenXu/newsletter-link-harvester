# Newsletter Link Harvester

[English](README.md) | 简体中文

一个与 [Agent Skills](https://agentskills.io) 标准兼容的技能：**从订阅邮件（newsletter）中收集链接，连同作者自己的推荐语一起存入 [Raindrop.io](https://raindrop.io/) 收藏库**。适用于 Claude Code、Codex CLI、Gemini CLI、GitHub Copilot、Cursor 与 WorkBuddy。

设计/科技类周刊每周都读，但好链接都埋在邮箱里。本技能把每一期变成一套永久、可检索的书签：链接按发件人归入对应子收藏夹，备注携带 `via: <周刊> · <日期>`，并附上作者推荐它的一句话理由。

## 它做什么

1. **筛选** —— 按发件人白名单（主）与可选主题关键词（辅）搜索 Gmail，默认回看 7 天；明确点名某期旧刊时窗口按指令扩展。
2. **解析** —— 两条已实测的通道：Markdown 直链（Quail 类）与纯文本中转包装（SubStack 类 `[ 网址 ]` 记号，入库前全部还原为最终地址）。
3. **上下文** —— 提取每条链接的编辑语境：作者的原话介绍或推荐理由（取自链接所在句或相邻段落）。存下的链接永远带着「为什么推荐」。
4. **三层去重** —— 批量内（URL 归一化：www / utm / 尾斜杠 / fragment / 大小写）、跨期（本地状态文件记录已处理邮件 ID）、全库比对。
5. **确认 → 保存** —— 完整预览并确认子收藏夹命名；未经你明确批准不写任何数据。书签批量创建，备注为 `via:` 行 + 介绍。推广条目（自家产品、社媒渠道、退订）默认标出并剔除。

## 亮点

1. **零上下文库内比对** —— 全库书签经 HTTP 直接分页落到本地文件（1300 条库 9 次请求），书签数据从不经过模型对话。无论收藏库多大，token 开销都接近零。
2. **平台中立** —— Raindrop 令牌依次解析自 `RAINDROP_TOKEN`、`--token-file`、或首个匹配的 MCP 配置（WorkBuddy / Cursor / Gemini / Claude / 项目 `.mcp.json`）；状态存于 `~/.config/newsletter-link-harvester/`（附带裁剪脚本）。
3. **安全优先** —— Gmail 仅申请只读权限（`gmail.readonly`：只搜索、只读取，绝不发送/删除/修改——已对真实工具清单核验）；未经确认的预览不写任何数据；邮件原封不动。
4. **备注忠实** —— `via:` 行格式固定不变；第二行是作者原话。原文把两个链接写进同一句话时，两条书签如实共享该介绍。
5. **信任模式（可选）** —— 对已映射的老发件人，逐条预览可降为简短摘要；任何写入前的确认闸口永不移除。

## 安装

本技能遵循开放的 [Agent Skills](https://agentskills.io) 标准（`SKILL.md` + `scripts/` + `references/`）。把仓库克隆到你所用 Agent 的技能目录：

| Agent | 用户级目录 | 项目级目录 |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex CLI | `~/.agents/skills/` | `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| GitHub Copilot | `~/.copilot/skills/` | `.github/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` |
| WorkBuddy | `~/.workbuddy/skills/` | — |

提示：`~/.agents/skills/` 是跨 Agent 通用目录——Codex CLI、Gemini CLI、GitHub Copilot 与 Cursor 原生读取，Claude Code 也会兜底扫描。装一处，多端发现。

```bash
git clone https://github.com/ChosenXu/newsletter-link-harvester.git \
  ~/.agents/skills/newsletter-link-harvester
```

也可手动把文件夹复制到上述任意目录。

## 前置条件

- **Gmail（只读 MCP）** —— 邮件通道。完整分步配置（Google Cloud 项目、Gmail API、OAuth 权限页面、桌面客户端、一次性浏览器授权）见 [`references/setup-guide.md`](references/setup-guide.md)（中文）/ [`references/setup-guide.en.md`](references/setup-guide.en.md)（英文）。只申请 `https://www.googleapis.com/auth/gmail.readonly`——本技能绝不发送、删除或修改邮件。任何暴露 Gmail 搜索/读取工具的 MCP 客户端都可用；本地 stdio 服务器 `@klodr/gmail-mcp` 已实测可用。
- **Raindrop.io** —— 目标收藏库。在你的 Agent MCP 配置中注册 Raindrop MCP 服务器（官方端点 `https://api.raindrop.io/rest/v2/ai/mcp`），或仅为库导出通道提供 API 令牌（`RAINDROP_TOKEN` / `--token-file`）。测试令牌获取：[app.raindrop.io/settings/integrations](https://app.raindrop.io/settings/integrations) → For Developers。切勿在任何地方提交令牌。
- **Python 3.10+**（辅助脚本仅用标准库，无需 pip 安装）。
- 运行 `python3 scripts/check_environment.py` 可做只读就绪检查。

## 配置

填写 `assets/newsletter-rules.json`（已内置 `example@newsletter.com` 模板）：

```json
{
  "senders": ["digest@example-weekly.com"],
  "keywords": [],
  "sender_collection_map": {
    "digest@example-weekly.com": "Example Weekly"
  },
  "settings": {
    "parent_collection": "Newsletter",
    "days_back": 7,
    "max_emails": 20,
    "trust_mode": false
  }
}
```

技能检测到未配置的模板会拒绝运行——防止误扫整个邮箱。

## 用法

对你的订阅说一句意图，如「处理一下我的 newsletter」/ "process my newsletter"，技能会跑完整流程（筛选 → 解析 → 去重 → 预览 → 你的确认 → 保存 → 报告）。也可以点名具体期号补收超出回看窗口的旧刊（如「把 Dine #245 收了」）。每次执行报告会如实列出：命中邮件数、提取数量、各层去重结果、库导出请求次数、保存成败与介绍覆盖率。

## 目录结构

```
SKILL.md                        # 技能定义与工作流
assets/newsletter-rules.json    # 发件人白名单与子收藏夹映射（需自行填写）
references/setup-guide.md       # Gmail + Raindrop 配置指南（中文）
references/setup-guide.en.md    # 配置指南（英文）
scripts/check_environment.py    # 只读就绪检查（多配置扫描）
scripts/dedupe_links.py         # 归一化 + 批量内去重
scripts/extract_context.py      # 逐链接编辑语境（Markdown 与纯文本双模式）
scripts/fetch_library.py        # 零上下文全库导出（令牌解析链）
scripts/check_library.py        # 离线库内比对（接受 kept/links 两种输入）
scripts/prune_state.py          # 跨期状态治理（按龄/上限/干跑）
```

## 安全

- **Gmail 天生只读** —— 所需 scope 仅为 `gmail.readonly`；邮件只搜索、只读取，绝不修改、移动或删除。
- **无确认不写入** —— 子收藏夹命名、条目清单、剔除的推广项全部先展示。
- **令牌只留本机** —— 绝不打印、不写日志、不复制进本技能生成的任何文件。
- **状态可审查** —— 跨期去重文件是 `~/.config/newsletter-link-harvester/` 下的纯 JSON；`prune_state.py --dry-run` 可预览任何清理动作。

## 已知限制

- Google OAuth 应用处于「测试」状态时授权每 7 天过期（重跑一条命令即可重新授权）；发布应用以解除限制需要经过验证的域名。
- SubStack 类中转还原需要运行期网络；还原失败重试一次，仍失败则原样保留并在报告中标注。
- 作者把两个链接写进同一句话时，两条书签共享该句介绍——这是对原文的忠实反映，不是缺陷。

## 许可证

[MIT](LICENSE)
