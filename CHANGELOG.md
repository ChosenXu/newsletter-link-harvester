# Changelog / 更新日志

All notable changes to this skill are documented in this file.
本文件记录本技能所有重要变更。

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).
格式参考 Keep a Changelog，版本号遵循语义化版本（SemVer）。

## [1.0.0] - 2026-09-18

First release. Battle-tested end-to-end on a real library (two newsletter platforms, six real issues, 205 links saved, zero failed writes, zero email mutations).
首个版本。在真实库上端到端实测（两个订阅平台、六期真实刊物、保存 205 条链接，零写入失败，邮件零改动）。

### Added / 新增

- Newsletter harvesting workflow: sender-whitelist Gmail filtering with a look-back window (explicitly naming an older issue extends it), two parsing channels — Markdown direct links (Quail-style) and SubStack-style plain-text `[ url ]` redirect wrappers with full resolution to final destinations before saving.
  订阅链接收取工作流：发件人白名单 Gmail 筛选与回看窗口（点名旧刊即扩展范围）；双解析通道——Markdown 直链（Quail 类）与 SubStack 类纯文本 `[ 网址 ]` 中转包装（入库前 100% 还原为最终地址）。
- Editorial context extraction: every saved link's note carries `via: <newsletter> · <date>` plus the author's own introduction (`scripts/extract_context.py`, Markdown and plain-text modes; bare-heading entries fall back to the following paragraph; list-segment splitting keeps sibling links from swapping intros).
  编辑语境提取：每条书签备注携带 `via: <周刊> · <日期>` 加作者原话介绍（`scripts/extract_context.py`，Markdown 与纯文本双模式；纯标题条目回退取下一段；列表分段切分避免同段链接互相串介绍）。
- Three-layer dedup: in-batch normalization (`scripts/dedupe_links.py` — www / utm / trailing slash / fragment / case), cross-run state file with housekeeping (`scripts/prune_state.py` — age/cap rules, dry-run, legacy-format tolerance), and whole-library compare (`scripts/fetch_library.py` + `scripts/check_library.py`).
  三层去重：批量内归一化（`scripts/dedupe_links.py`——www / utm / 尾斜杠 / fragment / 大小写）、跨期状态文件与治理（`scripts/prune_state.py`——按龄/上限裁剪、干跑预览、旧格式兼容）、全库比对（`scripts/fetch_library.py` + `scripts/check_library.py`）。
- Zero-context library export: the full Raindrop library is paged straight to a local file over HTTP via the Raindrop MCP gateway (stateless JSON-RPC, 1-based paging, 150 per page); bookmark payloads never pass through the model conversation — a 1,300-bookmark library costs 9 requests and near-zero token overhead, with a readback verification built into the flow.
  零上下文库导出：全库经 Raindrop MCP 网关按页直写本地文件（无状态 JSON-RPC、页码 1 起始、每页 150 条）；书签数据从不经过模型对话——1300 条库 9 次请求、token 开销接近零，流程内置写入后回查核验。
- Platform-neutral token resolution: `RAINDROP_TOKEN` env var → `--token-file` → auto-detection across common MCP configs (`~/.workbuddy/mcp.json`, `~/.cursor/mcp.json`, `~/.gemini/settings.json`, `~/.claude.json`, `./.mcp.json`); tokens are never printed or logged.
  平台中立的令牌解析：`RAINDROP_TOKEN` 环境变量 → `--token-file` → 常见 MCP 配置自动探测（`~/.workbuddy/mcp.json`、`~/.cursor/mcp.json`、`~/.gemini/settings.json`、`~/.claude.json`、`./.mcp.json`）；令牌绝不打印或记录。
- Readiness check (`scripts/check_environment.py`): Python version, gmail/raindrop MCP registration across the same config list, state-directory writability; statuses ready / partial / needs_setup / unavailable.
  就绪检查（`scripts/check_environment.py`）：Python 版本、跨配置列表的 gmail/raindrop 注册情况、状态目录可写性；状态分 ready / partial / needs_setup / unavailable。
- Confirmation gates throughout: full preview with per-sender sub-collection naming, promotional entries (self-promotion, social channels, game announcements, unsubscribe) flagged and excluded by default, and an optional trust mode that only shortens the preview for already-mapped senders — the pre-write confirmation is never removed.
  全程确认闸口：带子收藏夹命名的完整预览，推广条目（自家产品、社媒渠道、游戏推广、退订）默认标出剔除，可选信任模式仅为已映射发件人缩短预览——写入前确认永不移除。
- Setup guides in Chinese and English (`references/setup-guide.md` / `setup-guide.en.md`) covering the verified Gmail path (local stdio server, `gmail.readonly` scope only) and the Google-official remote MCP path (verified layer-by-layer; the Developer Preview enrollment gate blocks personal accounts), plus Raindrop integration and token hygiene.
  中英双语配置指南（`references/setup-guide.md` / `setup-guide.en.md`），覆盖实测可用的 Gmail 路径（本地 stdio 服务器、仅 `gmail.readonly` 权限）与 Google 官方远程 MCP 路径（逐层实测；Developer Preview 计划闸门挡住个人账号），以及 Raindrop 接入与令牌卫生。

### Verified / 实测验证（2026-09-17 ~ 09-18，真实库）

- Six real issues across two platforms: DEX 周刊 #364/#363/#362 (183 links, Quail Markdown channel) and Dine Digest #247/#246/#245 (22 links, SubStack redirect channel) — 205/205 saved, zero failures.
  两个平台六期真实刊物：DEX 周刊 #364/#363/#362（183 条，Quail Markdown 通道）与 Dine Digest #247/#246/#245（22 条，SubStack 中转通道）——205/205 保存成功，零失败。
- Cross-issue dedup caught a newsletter re-recommending a link (skydive.com in both #364 and #362) and a user-saved bookmark (StyleX UI); utm/WWW variants match reliably after normalization.
  跨期去重成功拦截周刊重复推荐（#364 与 #362 均含 skydive.com）与用户手动存过的书签（StyleX UI）；归一化后 utm/WWW 变体稳定匹配。
- Read-only Gmail isolation verified against the live tool list (10 tools, all read-type; no send/delete/move tools exposed).
  只读 Gmail 隔离经真实工具清单核验（10 个工具全为只读类；无发送/删除/移动工具暴露）。
- Google-official remote MCP path probed layer-by-layer: unauthenticated initialize/tools/list, Bearer token auth, per-project API enablement, and the final Developer Preview enrollment gate (documented in the setup guide).
  Google 官方远程 MCP 路径逐层探测：未认证 initialize/tools/list、Bearer 令牌认证、按项目 API 启用、最终的 Developer Preview 计划闸门（已写入配置指南）。

### Known limitations / 已知限制

- A Google OAuth app in "testing" status expires consent every 7 days; one command re-authorizes. Publishing the app requires a verified domain.
  Google OAuth 应用处于「测试」状态时授权每 7 天过期；重跑一条命令即可重新授权。发布应用需要经过验证的域名。
- The library-export channel talks to the Raindrop AI/MCP gateway; the general REST API is not usable with the same AI-integration token.
  库导出通道走 Raindrop AI/MCP 网关；同一枚 AI 集成令牌无法调用通用 REST API。
- Redirect resolution needs network access; a twice-failed resolution saves the wrapped URL and flags it in the report.
  中转还原需要网络；两次失败后原样保存包装网址并在报告中标注。
- Where an author places two links in one sentence, both bookmarks share that sentence as context.
  作者把两个链接写进同一句话时，两条书签共享该句介绍。

## [1.1.0] - 2026-09-20

### Added / 新增

- Optional Jev pre-classification (`scripts/classify_entries.py`): when a TypeSafe API key is configured (`TYPESAFE_API_KEY` env var or `~/.typesafe-api-key`), entries are pre-classified before the preview with two Noul judgments — "is this promotional" and "is the anchor text a usable title" (noul >= 0.9 marks "clear promotional, suggest excluding", <= 0.3 marks "clear content", in-between goes to human review). Calibrated on 2026-09-20 with real Chinese newsletter entries: 14/14 correct, perfect self-consistency (deviation <= 0.04).
  可选 Jev 预分类（`scripts/classify_entries.py`）：配置 TypeSafe API key（环境变量 `TYPESAFE_API_KEY` 或文件 `~/.typesafe-api-key`）后，预览前对每条条目做两个 Noul 判断——「是否推广」与「锚文本是否可作标题」（noul ≥0.9 标「明确推广，建议剔除」，≤0.3 标「明确内容」，中间地带交人工确认）。2026-09-20 以真实中文条目校准：14/14 正确，自一致性满分（极差 ≤0.04）。
- Soft-dependency design: without a key the script exits with code 3 and the skill behaves exactly like 1.0.0; a service outage skips annotations and keeps the full flow. The confirmation gate is never affected by annotations.
  软依赖设计：无 key 时脚本以退出码 3 结束，skill 行为与 1.0.0 完全一致；服务故障时跳过标注、主流程不受影响。标注永不影响确认闸口。
- Dependency manifest and bilingual setup guide updated with the optional `typesafe-jev` dependency (API key acquisition, storage, verification, rotation).
- 依赖清单与中英配置指南新增可选依赖 `typesafe-jev`（API key 获取、存储、验证与轮换说明）。

### Notes / 说明

- Version bumped 1.0.0 → 1.1.0 (MINOR: new compatible capability). Jev is an optional, env-gated dependency — the default workflow is unchanged without configuration.
- 版本 1.0.0 → 1.1.0（MINOR：新增兼容能力）。Jev 为可选、按环境变量启用的依赖——未配置时默认工作流不变。

## [Unreleased]

_Nothing yet._
_暂无。_
