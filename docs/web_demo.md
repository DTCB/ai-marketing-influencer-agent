# GitHub + Vercel 上线与验收

生产仓库为 `DTCB/ai-marketing-influencer-agent`。Vercel Hobby 项目建议命名为 `influencer-campaign-demo`，使用平台提供的 `.vercel.app` 生产域名。

生产入口 [influencer-campaign-demo.vercel.app](https://influencer-campaign-demo.vercel.app/)。

## 首次发布与后续更新

1. 在本地运行 `python -m scripts.build_demo_snapshot --check`、`npm ci` 和 `npm run build`。业务数据变化后，运行 `python -m scripts.build_demo_snapshot` 更新前端随包提供的案例。
2. 从 [Vercel 项目导入](https://vercel.com/new)连接上述 GitHub 仓库。Root Directory 使用仓库根目录，Production Branch 设为 `main`。配置由 `vercel.json` 提供，Node 24.x、Vite 输出 `dist`、Python 3.12、美国东部 `iad1`、函数最长 120 秒。在项目设置确认 Fluid Compute 已开启。
3. 推送 `codex/*` 分支并查看 Vercel Preview，核对提交、构建日志、首页和 `/api/status`。确认后合并到 `main`，使用 Vercel 原生 Git 集成更新生产域名。正式链接填生产域名。
4. 用国内手机流量和无痕窗口确认可免登录查看案例，测试改预算、排除达人、Brief 编辑与 TXT 下载、确认后复盘。记录访问网络、日期、提交和函数区域。

如线上版本有回归，在 Vercel 恢复此前的成功生产部署，并用 Git revert 使 `main` 与生产修复版本一致。

## 首发与实时 AI

首版与 Preview 提供示例和模板。生产模型开启前，在项目 **Production** 环境配置：

| 变量 | 值或用途 |
|---|---|
| `LLM_API_KEY` | 达人 Demo 专用百炼密钥 |
| `LLM_BASE_URL` | 百炼兼容接口地址，HTTPS |
| `LLM_MODEL` | 已验证可用的模型名 |
| `LLM_ENABLE_THINKING` | `false`，适用支持该参数的百炼模型 |
| `UPSTASH_REDIS_REST_URL` | Upstash REST 地址 |
| `UPSTASH_REDIS_REST_TOKEN` | 具有计数写权限的 REST Token |
| `QUOTA_HASH_SECRET` | 独立随机密钥，建议 32 字节以上 |
| `AI_BUDGET_CONFIRMED` | 首次为 `0`，验收后切换为 `1` |

Upstash 可使用独立实例或沿用已有实例，达人 Demo 写入专用命名空间。按 UTC 日历计算每日每 IP 3 次、全站每月 200 次。三种功能共享额度，调用模型前原子扣减。IP 仅以带日期的 HMAC 值参与计数。模型调用失败也保留本次扣减。开启前在被 Git 忽略的 `.env.production.local` 里临时配置 Redis 地址和令牌，运行 `python -m scripts.verify_redis_quota --env-file .env.production.local` 检查并发日限额和全站月限额。

项目首期预算待账号所有者确认，参考 ¥20/月、¥16 告警。按专用 Key 设置百炼预算、告警和达到预算后停止。百炼说明停用可能有延迟。在预算与 Redis 验证通过后，将开关设为 `1`，重新部署当前生产版本。需要停用时将开关设回 `0` 后重新部署，紧急情况可在百炼禁用该项目 Key。 [百炼预算管理](https://help.aliyun.com/zh/model-studio/budget-management)

## 验收记录

用 `python -m scripts.verify_deployment <生产URL> --commit <Git提交>` 检查案例版和函数配置。实时 AI 开放后，从当天未用过额度的网络加 `--live` 执行一次。此操作会发起三个实时模型请求；如果限额异常，第四次探测也可能触发调用。

本地案例版已通过 `npm ci`、生产构建和 HTTP 验收。Chrome 验证了阻断 API 时首屏仍能查看、390 像素宽度可操作、导出的 TXT 含修改后的 Brief，以及刷新后复投候选仍在当前会话。模型接口和配额回退已使用模拟响应验证。

| 场景 | 预期结果 |
| --- | --- |
| 默认案例 | ¥49,800；已回收 4/5 位；收藏率 1.52%，单次转化成本 ¥36.58 |
| 排除蓝莓护肤避雷 | 晚安小敏补位，5 位达人报价 ¥49,600 |
| ¥30,000 要求 5 人 | 缺口 ¥8,200 |
| 示例版 | `/api/status` 返回 AI 未开启，案例与工作台照常体验 |
| 实时 AI | 同一公网 IP 用合成资料依次验证 Brief 解析、推荐解释和复盘摘要。第四次请求返回 `429`，模板和规则计算可继续使用 |
| 自动更新 | Preview 和正式部署分别对应 GitHub 的预览和主分支提交，发布后生产 URL 一致 |

2026-11-19，生产域名首次指向案例版提交 `c345f3f`。匿名 HTTPS 验证首页、预算组合和复盘 API 通过，`/api/status` 显示 `hkg1`、案例模式。国内手机流量和实时模型待验收。

2026-11-20，香港函数多次连接百炼失败，日志记录 APIConnectionError，单次约 62 秒后回退模板。使用同地域备用接入域名仍失败后，恢复原百炼接口，并将函数切到新加坡 `sin1`。生产状态与提交已核对，推荐解释、Brief 解析和复盘摘要均返回 live，分别耗时约 2.7、1.9、2.2 秒。保留当前 Key、模型和配额。错误提示现区分连接失败、超时及服务商拒绝，日志仅记录脱敏诊断。

同日后续使用再次出现连接失败，说明区域调整后的短时成功不足以确认稳定性。直接 HTTPS 对照获得 Linux 错误码 99（EADDRNOTAVAIL），表明连接地址分配失败。公开网页的模型请求固定使用 IPv4，并在请求结束后关闭连接，同时将部署区域对齐反馈洞察已在线使用的美国东部 `iad1`。沿用当前接口、Key、模型、请求参数与配额，每次预留额度最多发送一次模型请求。连接超时上限为 5 秒，响应超时仍按原配置限制。验收覆盖三项 AI 功能、不同连接及间隔后的调用，并核对实时返回和服务端日志。
