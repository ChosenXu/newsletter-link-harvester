# Changelog / 更新日志

All notable changes to this skill are documented in this file.
本文件记录本技能所有重要变更。

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).
格式参考 Keep a Changelog，版本号遵循语义化版本（SemVer）。

## [1.3.0] - 2026-09-28

### Added / 新增

- fetch_library.py: `--max-pages` safety cap (default 200) stops runaway pagination with an explicit truncation warning; HTTP 429 responses now honor the server's `Retry-After` header (clamped to 1.5-30s) instead of a fixed 1.5s sleep.
  fetch_library.py：新增 `--max-pages` 保险丝（默认 200）终止失控分页并输出明确的截断警告；HTTP 429 响应现遵循服务端 `Retry-After` 头（钳制在 1.5-30 秒），不再固定睡 1.5 秒。

### Changed / 变更

- dedupe_links.py: URL normalization accepts uppercase schemes (`HTTPS://`) instead of discarding the link as non-web; rejects URLs without a host; the tracking param `si` is now stripped only on `open.spotify.com` (it is a legitimate parameter on other hosts and was silently deforming those URLs).
  dedupe_links.py：URL 归一化接受大写 scheme（`HTTPS://`）而非当作非网页链接丢弃；拒绝无 host 的 URL；跟踪参数 `si` 改为仅在 `open.spotify.com` 上剥离（它在其他站点是合法参数，此前会被误删导致网址变形）。
- check_environment.py: server matching is now restricted to the entry name and URL field — a "gmail"/"raindrop" substring buried elsewhere in an unrelated server entry no longer reads as configured.
  check_environment.py：服务器匹配收窄到条目名称与 URL 字段——埋在无关服务器条目其他位置的「gmail」/「raindrop」字样不再被误判为已配置。
- Redirect resolution in SKILL.md now caps the chain at 5 hops (`curl --max-redirs 5`); longer chains count as resolution failures.
  SKILL.md 的重定向还原加 5 跳上限（`curl --max-redirs 5`）；超长链按还原失败处理。

### Fixed / 修复

- prune_state.py: the state file is now written atomically (temp file + rename), so a crash mid-write can no longer leave a half-truncated JSON that breaks cross-run dedup; malformed state files (non-object root, non-list `processed_email_ids`) are rejected with exit code 2 instead of crashing or silently corrupting the state.
  prune_state.py：状态文件改为原子写入（临时文件 + 重命名），写入中途崩溃不再留下半截 JSON 破坏跨期去重；畸形状态文件（根非对象、`processed_email_ids` 非列表）以退出码 2 拒绝，不再崩溃或静默损坏状态。
- extract_context.py: English sentences now split on "." with decimal points (3.5) and common abbreviations (e.g., i.e., etc., U.S.) excluded; `--max-chars` is clamped to a minimum of 10 (0 or negative values previously produced a negative slice that silently skipped truncation); non-dict link entries are skipped instead of crashing; the URL-only fallback now measures the actually matched text, fixing off-by-anchor-length offsets; input files are read with context managers.
  extract_context.py：英文句子现按「.」切分（排除小数点与常见缩写）；`--max-chars` 钳制到最小 10（此前传 0 或负数会因负切片静默跳过截断）；非字典链接条目跳过而非崩溃；URL 兜底匹配改用实际匹配文本的长度，修复锚文本长度偏差；输入文件改用上下文管理器读取。
- check_library.py: input files are read with context managers (no leaked file handles).
  check_library.py：输入文件改用上下文管理器读取（不再泄漏文件句柄）。

### Notes / 说明

- Version bumped 1.2.0 → 1.3.0 (MINOR: new `--max-pages` CLI option and behavior-preserving normalization changes).
- 版本 1.2.0 → 1.3.0（MINOR：新增 `--max-pages` 参数，归一化改动保持行为兼容）。

## [1.2.0] - 2026-09-27

### Security / 安全

- Library export no longer defaults to a predictable filename in the shared temp directory (readable by other local users on multi-user systems, and overwritable via a pre-planted symlink); it now writes to `~/.config/newsletter-link-harvester/library.json` with 0600 file and 0700 directory permissions.
  库导出默认输出不再使用共享临时目录里的可预测文件名（多用户系统上其他本地用户可读、且可被预置符号链接覆盖）；改为写入 `~/.config/newsletter-link-harvester/library.json`，文件权限 0600、目录权限 0700。
- Jev pre-classification is now explicit opt-in per rules file (`settings.jev_enabled`, default `false`) instead of triggering on mere key presence — the step sends entry text derived from email content to the TypeSafe API, so "a key exists" and "this run may use it" are now separate decisions.
  Jev 预分类改为按规则文件显式开启（`settings.jev_enabled`，默认 `false`），不再凭「key 存在」自动触发——该步骤会把邮件衍生的条目文本发送至 TypeSafe API，「配置了 key」与「本次运行允许使用」从此是两个独立决定。

### Changed / 变更

- Jev classification now reads the check_library.py output with `--only-new`: entries already in the Raindrop library are no longer wastefully classified; requests run in a small thread pool (4 workers, pacing preserved) instead of sequentially; `--max-entries` (default 100) caps the classified count so a large batch cannot run away.
  Jev 分类改读 check_library.py 输出并加 `--only-new`：已在 Raindrop 库中的条目不再被白白分类；请求改由小型线程池并发执行（4 工作线程、保留节流）；`--max-entries`（默认 100）封顶分类数量，防止大批量失控。
- check_library.py results now carry through every original entry field (anchor text, context, sender, ...), so downstream steps consume the output directly without rejoining the input file.
  check_library.py 的结果条目现在原样携带全部原始字段（锚文本、语境、发件人等），下游步骤可直接消费其输出、无需回联输入文件。

### Fixed / 修复

- check_environment.py: the `unavailable` status branch was dead code (its trigger string never occurs), so SKILL.md routing on it could never fire — the status now derives cleanly from the MCP check result, and the docstring no longer claims an unreachable exit code 1. `unavailable` remains a session-level decision made by the live probe in SKILL.md Step 0.
  check_environment.py：`unavailable` 状态分支为死代码（触发字符串永远不会出现），SKILL.md 对它的路由从不生效——状态现直接由 MCP 检查结果推导，文档不再声明不可达的退出码 1。`unavailable` 仍由 SKILL.md Step 0 的会话内探针判定。
- fetch_library.py: a gateway response with an empty `content` array crashed with an uncaught IndexError, bypassing the designed retry; the content is now validated before access and malformed responses go through the normal retry path.
  fetch_library.py：网关返回空 `content` 数组时以未捕获的 IndexError 崩溃、绕过既定重试；现在取值前校验内容，畸形响应走正常重试路径。

### Notes / 说明

- Version bumped 1.1.0 → 1.2.0 (MINOR: the `jev_enabled` setting and new CLI flags are backward-compatible additions; the Jev opt-in is a deliberate privacy behavior change).
- 版本 1.1.0 → 1.2.0（MINOR：`jev_enabled` 设置与新增 CLI 参数均为向后兼容能力；Jev 改为显式开启是有意的隐私行为变更）。

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

## [Unreleased]

_Nothing yet._
_暂无。_
