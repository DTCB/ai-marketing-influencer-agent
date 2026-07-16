# AI营销 Agent：达人投放推荐工具

这是一个面向达人投放场景的 AI 营销 Agent MVP，用于演示品牌目标输入、达人推荐、内容建议与投放复盘的完整业务闭环。

项目默认以「美妆护肤新品投放」为案例，围绕品牌目标输入、达人匹配推荐、AI 推荐理由与内容建议、投放复盘分析，形成一条完整业务闭环。

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

系统基于达人标签、受众画像、互动率、报价、历史转化和品牌安全等字段进行可解释评分，并通过模板或可选 LLM 生成推荐理由、内容脚本和复盘摘要。

## 核心功能

- 品牌 Brief 输入：品类、人群、预算、平台、投放目的、核心卖点。
- 达人样例数据：内置 20 条美妆护肤达人数据，并支持上传同字段 CSV。
- 推荐排序：按标签匹配、受众匹配、内容效果、成本效率、历史转化、品牌安全计算推荐分。
- AI 内容建议：生成达人推荐理由、标题、短视频/图文脚本、卖点和风险提示。
- 投放复盘：计算曝光、点击、CTR、转化、CVR、CPA、ROI，并输出复盘摘要。

## 推荐算法逻辑

默认使用 100 分制加权评分：

```text
Score = 0.30 * TagScore
      + 0.20 * AudienceScore
      + 0.20 * PerformanceScore
      + 0.15 * CostScore
      + 0.10 * ConversionScore
      + 0.05 * SafetyScore
```

不同投放目标会动态调整权重：

- 品牌曝光：提高平均播放和互动率权重。
- 种草转化：提高标签匹配、受众匹配和互动收藏权重。
- 转化：提高历史 ROI 和历史转化率权重。

## 技术栈

- Python
- Streamlit
- Pandas
- Plotly
- OpenAI SDK / OpenAI-compatible API（可选）
- python-dotenv

没有 API Key 时，系统会自动使用模板生成推荐理由、内容建议和复盘摘要，保证 Demo 可稳定运行。侧边栏会显示当前是“模板模式”还是“真实 LLM 已配置”。

## 如何运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

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

页面反馈逻辑：

- 未配置 API Key：侧边栏显示“模板模式”，生成结果使用本地模板。
- 已配置 API Key：侧边栏显示 Provider、模型名、Base URL 和脱敏 Key。
- LLM 调用成功：生成区域显示“已调用真实 LLM”。
- LLM 调用失败：生成区域显示具体失败原因，并自动回退到本地模板结果。

## 数据说明

- `data/creators.csv`：达人样例数据。
- `data/campaign_cases.csv`：默认品牌投放案例。
- `data/review_metrics.csv`：模拟投放复盘数据。

上传达人 CSV 时，需要包含 `modules/scoring.py` 中定义的必要字段，否则页面会提示缺失字段。

## 项目亮点

- 不是单纯按粉丝数排序，而是将业务目标转成可解释推荐规则。
- 推荐结果包含分项得分和推荐理由，便于运营团队理解和复核推荐依据。
- AI 模块不依赖外部 API，具备模板 fallback，适合稳定演示。
- 投前推荐和投后复盘打通，体现“投前-投中-投后”的营销业务闭环。

## 可扩展方向

- 接入真实达人平台数据或第三方数据源。
- 用真实投放结果校准推荐权重。
- 增加 A/B 内容策略和多轮 Agent 调参。
- 支持更多行业案例，例如食品饮料、数码 3C、校园生活。
