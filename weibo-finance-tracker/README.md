# 微博财经博主追踪与投资辅助工具 (WFT)

追踪微博财经博主资讯，通过算法筛选优质博主，分析历史观点，辅助投资决策。

## 功能特性

- **博主管理** — 搜索/添加/移除微博财经博主，支持手动标记优选
- **数据采集** — 自动抓取博主微博内容，支持限速防反爬
- **观点分析** — NLP 情感分析 + LLM 深度解读，提取市场方向、板块、个股
- **智能排名** — 多维度评分算法（准确率 35% + 影响力 25% + 活跃度 20% + 一致性 20%）
- **优选 TOP3** — 手动筛选优先 + 算法补齐，聚焦最优质的信息源
- **投资参考** — 聚合多博主观点，生成市场共识和操作建议

## 快速开始

### 安装

```bash
cd weibo-finance-tracker
pip install -e .
```

### 配置

```bash
cp config/config.example.json config/config.json
```

编辑 `config/config.json`：

| 字段 | 说明 | 必填 |
|------|------|------|
| `weibo_cookie` | 微博登录 Cookie，提高抓取成功率 | 推荐 |
| `openai_api_key` | OpenAI/兼容 API Key，用于 LLM 深度分析 | 可选 |
| `llm_base_url` | LLM API 地址（支持自定义端点） | 可选 |
| `llm_model` | LLM 模型名称 | 可选 |

### 获取微博 Cookie

1. 浏览器登录 [m.weibo.cn](https://m.weibo.cn)
2. F12 打开开发者工具 → Network → 任意请求 → 复制 Cookie 值
3. 填入 `config/config.json` 的 `weibo_cookie` 字段

## 网页界面 (推荐)

在浏览器中选择博主、运行分析、查看可视化结果：

```bash
python3 webapp.py
# 打开 http://127.0.0.1:5000
```

界面功能：

- **勾选博主** — 点击卡片多选，支持全选/清空
- **一键分析** — 运行 NLP 情绪分析，实时展示三大结论
- **可视化** — 周度情绪趋势折线图 (Chart.js)、板块/个股热度与共识度进度条、量化指标卡片
- **量化指标** — BSI / MHI / CI / SM / RAI + 板块轮动 + 信号综述

> 首次运行会自动加载演示数据；接入真实数据请在 `config/config.json` 配置微博 Cookie 并运行 `wft fetch`。

## 离线 HTML 报告 (无需服务器)

若无法访问本地服务器端口，可导出一个**完全自包含的静态 HTML 报告**，用浏览器直接打开即可查看全部可视化结果（无任何外部依赖，SVG 内联趋势图）：

```bash
python3 export_report.py            # 生成 report.html
python3 export_report.py my.html    # 指定输出文件名
```

生成的 `report.html` 可直接双击打开，或通过在线预览查看：
`https://htmlpreview.github.io/?<report.html 的 raw 链接>`

## 使用方法

### 博主管理

```bash
# 搜索博主
wft blogger search "财经"

# 添加博主 (通过微博 UID)
wft blogger add 1234567890

# 添加并标记为手动优选
wft blogger add 1234567890 --manual

# 查看已追踪博主
wft blogger list

# 手动标记已有博主为优选
wft blogger select 1234567890

# 移除博主
wft blogger remove 1234567890
```

### 数据采集

```bash
# 抓取所有博主的微博
wft fetch

# 抓取指定博主，5 页
wft fetch --uid 1234567890 --pages 5
```

### 观点分析

```bash
# 基础 NLP 分析（离线，无需 API）
wft analyze

# 使用 LLM 深度分析（需配置 API Key）
wft analyze --llm

# 查看博主观点摘要
wft summary
wft summary --uid 1234567890
```

### 博主排名

```bash
# 显示 TOP 10 排名
wft rank

# 显示 TOP 20
wft rank --top 20

# 显示优选 TOP 3（手动筛选优先 + 算法补齐）
wft top3
```

### 深度情绪分析

交互式选择要分析的博主，输出市场走向、板块个股热度、量化指标三大部分：

```bash
# 交互选择博主编号（如输入 1,4,5 或 all）
wft deep

# 分析全部博主
wft deep --all

# 指定博主 UID（可多次传入）
wft deep --uid 1729390673 --uid 2001001003

# 使用 LLM 深度分析
wft deep --llm
```

输出内容：

- **① 市场整体走向与热度** — 趋势方向/强度、热度指数、情绪动量、量能信号、近 4 周情绪趋势图
- **② 板块与个股** — 讨论热度、共识度、情绪分及标签（强烈看多 → 强烈看空）
- **③ 量化参考指标** — BSI 博主情绪指数、MHI 市场热度指数、CI 共识指数、SM 情绪动量、RAI 风险偏好指数、板块轮动信号、信号综述

> 也可直接运行 `python3 run_analysis.py`（会自动加载演示数据），等价于 `wft deep`。

### 投资建议

```bash
# 基于所有博主生成建议
wft advice

# 仅基于 TOP3 博主
wft advice --top3-only

# 指定分析天数
wft advice --days 14
```

### 一键执行

```bash
# 全流程：抓取 → 分析 → 排名 → 建议
wft run

# 使用 LLM 分析
wft run --llm
```

## 排名算法

博主综合评分由四个维度加权计算：

```
综合分 = 准确率 × 0.35 + 影响力 × 0.25 + 活跃度 × 0.20 + 一致性 × 0.20
```

| 维度 | 权重 | 说明 |
|------|------|------|
| 准确率 | 35% | 历史观点验证，基于置信度代理指标 |
| 影响力 | 25% | 粉丝数（对数缩放）+ 互动率 + 认证加成 |
| 活跃度 | 20% | 近 30 天发帖频率，理想 1-3 条/天 |
| 一致性 | 20% | 情感波动幅度，越稳定分数越高 |

### 优选 TOP3 逻辑

1. 优先返回用户**手动标记**的优选博主
2. 手动优选不足 3 个时，由算法排名自动补齐
3. 即使是手动优选的博主，也会参与排名排序

## 项目结构

```
weibo-finance-tracker/
├── config/
│   └── config.example.json   # 配置模板
├── data/                      # SQLite 数据库（自动生成）
├── src/
│   ├── __init__.py
│   ├── main.py                # CLI 入口 & 命令定义
│   ├── scraper.py             # 微博数据采集
│   ├── database.py            # 数据库管理
│   ├── analyzer.py            # 观点分析（NLP + LLM）
│   ├── ranker.py              # 博主排名算法
│   ├── advisor.py             # 投资建议生成
│   ├── deep_analysis.py       # 深度语义分析 & 量化指标
│   ├── report.py              # 深度分析报告渲染（CLI/脚本共用）
│   └── demo.py                # 演示数据
├── templates/
│   └── index.html             # 网页界面
├── webapp.py                  # Flask Web 服务
├── run_analysis.py            # 交互式深度分析脚本（等价 wft deep）
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 风险提示

> ⚠️ 本工具生成的所有分析和建议**仅供参考，不构成投资建议**。投资有风险，入市需谨慎。请结合自身情况独立判断，对投资决策负责。

## License

MIT
