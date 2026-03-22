# Idea Radar — Project Plan

## Goal
自动收集 Reddit + Indie Hackers 上关于 side project、创业点子、用户痛点的讨论，
每日 AI 提炼成摘要发到邮箱。

## Stack
- Python 3.11+
- Reddit API: PRAW
- Indie Hackers: RSS + scraping
- Storage: SQLite (去重 + 历史)
- AI: OpenRouter free models (qwen-2.5-72b:free 为主，支持多模型切换)
- Email: Gmail SMTP
- Schedule: GitHub Actions (每日 08:00 Toronto 时间)
- Config: YAML

## Project Structure
```
idea-radar/
├── config.yaml              # 用户配置（不提交git）
├── config.example.yaml      # 模板
├── requirements.txt
├── pyproject.toml
├── idea_radar/
│   ├── __init__.py
│   ├── config.py            # YAML配置加载，dataclass
│   ├── models.py            # Post, Category, DigestItem 数据模型
│   ├── db.py                # SQLite CRUD，去重逻辑
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py          # BaseCollector ABC
│   │   ├── reddit.py        # Reddit via PRAW
│   │   └── indie_hackers.py # IH RSS + scraping
│   ├── classifier/
│   │   ├── __init__.py
│   │   └── ai_classifier.py # OpenRouter API, 多模型支持, batch分类
│   ├── digest/
│   │   ├── __init__.py
│   │   ├── builder.py       # 按类别归组，生成摘要
│   │   └── templates/
│   │       └── daily.html   # Jinja2 HTML email模板
│   ├── mailer/
│   │   ├── __init__.py
│   │   └── gmail.py         # Gmail SMTP发送
│   └── eval/
│       ├── __init__.py
│       ├── test_set.jsonl   # 标注测试集(50条)
│       └── benchmark.py     # 多模型评测脚本
├── scripts/
│   ├── run_daily.py         # 主入口: collect→classify→digest→send
│   └── run_eval.py          # 跑benchmark
├── .github/
│   └── workflows/
│       └── daily_digest.yml # GH Actions workflow
├── data/
│   └── .gitkeep
└── tests/
    ├── test_collector.py
    └── test_classifier.py
```

## Categories (AI 分类目标)
- `pain_point` — 用户抱怨某个问题/需求未满足
- `idea` — 有人分享创业/side project想法
- `project_launch` — 有人发布新产品/项目
- `lesson_learned` — 创业/做项目的经验教训
- `noise` — 不相关，过滤掉

## Phases
- P1: Core infra + Reddit collector (done by Agent 1)
- P2: Indie Hackers collector (Agent 2, after P1)
- P3: AI Classifier + Eval framework (Agent 3, parallel with P2)
- P4: Digest Builder + Gmail Mailer (Agent 4, after P2+P3)
- P5: GitHub Actions + 完整测试 (Agent 5, after P4)
