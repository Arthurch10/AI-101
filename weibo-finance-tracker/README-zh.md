# 微博财经博主追踪与投资辅助工具 (WFT)

[English](README.md)

追踪微博财经博主资讯，通过算法筛选优质博主，分析历史观点，辅助投资决策。

## 核心功能

1. **博主追踪** — 搜索并添加微博财经博主，自动采集最新微博
2. **智能筛选** — 用户可手动标记优选博主，也可由系统算法给出 TOP10 排名
3. **观点分析** — NLP + LLM 双引擎分析博主历史观点（情绪、方向、板块、个股）
4. **投资辅助** — 聚合多位博主观点，输出市场共识和操作建议

## 安装与使用

详见 [README.md](README.md)

## 快速上手

```bash
# 1. 安装
pip install -e .

# 2. 配置
cp config/config.example.json config/config.json
# 编辑 config.json 填入微博 Cookie

# 3. 添加博主
wft blogger add <UID>

# 4. 一键运行
wft run
```
