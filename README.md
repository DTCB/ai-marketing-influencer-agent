# 小红书达人投放助手

这是一个面向品牌运营的 AI 营销 Agent 原型。打开页面即可体验敏感肌修护精华的小红书投放案例，从预算内选人、确认合作内容到模拟投后复盘。

[打开在线 Demo](https://influencer-campaign-demo.vercel.app/)

## 业务问题

品牌做达人投放时，常见问题包括：

- 达人筛选依赖人工经验，效率低。
- 只看粉丝数容易忽略人群匹配、互动质量和报价效率。
- 推荐理由不透明，难以向团队解释为什么选择某个达人。
- 内容方向和投后复盘分散，难以沉淀下一轮投放策略。

## 解决方案

本项目将投放流程拆成四个环节：

```text
品牌目标输入 → 达人匹配推荐 → 推荐理由与内容建议 → 投放复盘分析
```

系统基于达人标签、受众画像、互动率、报价、历史转化和品牌安全等字段评分，并用本地模板生成合作卡。推荐解释和复盘摘要支持按需调用 LLM。

## 核心功能

- 首页可直接查看完整案例，包含选人取舍、两份合作 Brief 和模拟复盘。
- 手动调整预算、合作人数与复盘目标。配置模型后也可用一句话生成条件预览，再由访客确认是否应用及排除达人。
- 对比按分数取前 N 位与预算内组合。可排除或恢复达人，查看重算后的名单、报价和综合分变化。
- 确认名单后逐位查看入选证据，编辑并保存合作 Brief，可复制全文或下载 TXT。
- 按确认名单查看模拟投后数据，对照收藏率与单次转化成本目标。待回收达人单独列出，已回收数据支持将低转化成本达人加入下一轮复投候选。

## 推荐算法逻辑

以本案例的种草转化目标为例，使用 100 分制加权评分：

```text
Score = 0.30 * TagScore
      + 0.25 * AudienceScore
      + 0.20 * PerformanceScore
      + 0.10 * CostScore
      + 0.10 * ConversionScore
      + 0.05 * SafetyScore
```

对同一批小红书候选，先按综合分取前 N 位作为对照，再在预算内挑选综合分之和最高的 N 人组合。同分时优先总报价更低的组合，再按达人 ID 决定。

## 技术栈

- Python
- Streamlit
- Pandas
- OpenAI SDK / OpenAI-compatible API（可选）
- python-dotenv

本地模板覆盖完整演示流程。选人页的一句话 Brief 提供可直接载入的示例。配置 API Key 后可解析访客输入，也能在合作内容页和复盘页按需生成 AI 内容。

## 如何运行

在两个终端分别启动网页和 API：

```bash
pip install -r requirements-local.txt
python -m uvicorn api.index:app --host 127.0.0.1 --port 8000
```

```bash
npm ci
npm run dev
```

打开 [本地网页](http://127.0.0.1:5173)。正式发布使用 [GitHub + Vercel 部署流程](docs/web_demo.md)。

原有 Streamlit 演示也可单独运行：

```bash
pip install -r requirements-local.txt
python -m streamlit run app.py
```

打开 [本地 Demo](http://localhost:8501)。默认案例中，按分取前五位的报价为 ¥52,800，预算内组合为 ¥49,800。把预算改为 ¥30,000 并重新计算，可看到 ¥8,200 的预算缺口。恢复默认并确认名单后，可查看逐位合作卡及 4/5 位达人的模拟数据回收情况。

## 配置真实 LLM 调用

推荐复制 `.env.example` 为 `.env`，然后填写下面三项。项目会自动读取 `.env`。

```bash
LLM_API_KEY=你的 API Key
LLM_BASE_URL=兼容 OpenAI 的服务地址
LLM_MODEL=模型名称
LLM_TIMEOUT_SECONDS=20
```

项目使用 OpenAI SDK 的 Chat Completions 形态，支持配置 OpenAI-compatible 的国产大模型接口。例如 DeepSeek 可使用：

```bash
LLM_API_KEY=你的 DeepSeek API Key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=从 DeepSeek 控制台或官方文档复制的模型名
```

也可以继续使用 OpenAI 风格变量：

```bash
OPENAI_API_KEY=你的 API Key
OPENAI_BASE_URL=兼容 OpenAI 的服务地址
OPENAI_MODEL=模型名称
```

配置后可主动生成 AI 推荐解释或复盘摘要。调用成功时标注 AI 生成，失败时显示本地模板。

## 数据说明

- `data/creators.csv`：达人样例数据。
- `data/campaign_cases.csv`：默认品牌投放案例。
- `data/review_metrics.csv`：模拟投放复盘数据。

工作台使用内置的小红书样例达人和模拟复盘记录。

## 项目亮点

- 将业务目标转成达人评分和整组预算约束，展示具体的换人取舍。
- 把达人标签和样例代表作转成运营可审阅的合作要求。
- 复盘保留待回收状态，下一轮建议基于已回收的数据。

## 可扩展方向

- 接入真实达人平台数据或第三方数据源。
- 用真实投放结果校准推荐权重。
- 增加 A/B 内容策略和多轮 Agent 调参。
- 支持更多行业案例，例如食品饮料、数码 3C、校园生活。
