# 文章推送系统（Article Publisher）

> 面向 Web3/财经资讯团队的采集、清洗、评分、存草稿、自动发布与 App 推送一体化系统。

## 1. 项目简介

本项目用于把多个资讯源（如 TechFlow、BlockBeats、Odaily 等）自动抓取到本地，经过清洗与评分后，按策略进入：

- 人工审核队列
- 自动存草稿（达到阈值）
- 自动发布并推送（达到更高阈值 + 命中发布窗口）

同时提供前端管理台，支持文章列表、编辑、批量操作、发布状态追踪、调度控制与日志排障。

---

## 2. 核心能力

- 多信源抓取与定时调度
- 文章正文清洗（跳转链接、格式规范化、作者/来源尾注规则）
- AI/规则评分与自动流转
- CMS 草稿保存、发布、App 推送
- 自动发布窗口控制、配额控制、去重控制
- 本地 SQLite 持久化（可切 PostgreSQL）
- 前端一体化运维面板

---

## 3. 目录结构

```text
article-publisher/
├─ backend/
│  ├─ api.py                        # FastAPI 入口
│  ├─ routes/                       # API 路由层
│  │  ├─ articles.py                # 文章列表/编辑/发布相关
│  │  ├─ pipeline.py                # 抓取与流程触发
│  │  ├─ scheduler.py               # 调度配置
│  │  ├─ workflow.py                # 自动发布工作流相关
│  │  ├─ settings.py                # 系统配置项读写
│  │  ├─ logs.py                    # 日志接口
│  │  └─ auth.py                    # 登录与鉴权
│  ├─ services/                     # 业务核心
│  │  ├─ pipeline_service.py        # 主流程编排（抓取/评分/发布/推送）
│  │  ├─ auto_publish_scheduler.py  # 自动发布+推送调度器
│  │  ├─ daily_report.py            # Odaily 日报改写/发布任务
│  │  ├─ publisher.py               # CMS 发布、草稿保存、正文组装
│  │  ├─ database.py                # SQLite 数据访问与状态记录
│  │  ├─ scorer.py                  # 评分与审核策略
│  │  ├─ filter_service.py          # 自动发布过滤规则
│  │  └─ article_store.py           # 文章存储管理
│  ├─ pipelines/                    # 各信源抓取器
│  └─ utils/                        # COS、日志等工具
├─ frontend/
│  ├─ src/
│  │  ├─ App.jsx                    # 主界面
│  │  ├─ api.js                     # 前端 API 客户端
│  │  └─ ...
│  └─ dist/                         # 构建产物（由 Vite 生成）
├─ data/                            # 默认 SQLite 数据
├─ logs/                            # 运行日志
├─ config.yaml                      # 运行配置
├─ config.yaml.example              # 配置模板
├─ requirements.txt                 # Python 依赖
└─ README.md
```

---

## 4. 技术栈

### 后端
- FastAPI
- Uvicorn
- SQLite（可扩展 PostgreSQL）
- Requests + BeautifulSoup

### 前端
- React 18
- Vite 6

### 外部集成
- ChainThink CMS API（发布/草稿/推送）
- 腾讯 COS（封面与图片上传）
- OpenAI 兼容 LLM（摘要/改写等可选能力）

---

## 5. 快速启动（本地）

## 5.1 环境要求
- Python 3.10+
- Node.js 18+
- npm 9+

## 5.2 安装依赖

```bash
pip install -r requirements.txt
npm --prefix frontend install
```

## 5.3 准备配置

```bash
copy config.yaml.example config.yaml
```

重点配置（`config.yaml`）：

- `chainthink.api_url`：发布接口
- `chainthink.upload_url`：上传接口
- `chainthink.token`：x-token
- `chainthink.app_id`：x-app-id
- `chainthink.user_id`：x-user-id
- `database.sqlite_path`：SQLite 文件位置

建议把敏感值放进环境变量（如 `CHAINTHINK_TOKEN`）。

## 5.4 构建前端

```bash
npm --prefix frontend run build
```

## 5.5 启动后端

```bash
cd backend
python api.py
```

访问：<http://localhost:8000>

---

## 6. 自动发布流程说明（重要）

完整链路（简化）：

1. 抓取信源文章
2. 清洗正文并评分
3. 达到阈值后进入自动通道
4. 命中时间窗口后执行自动发布
5. 发布成功后执行 App 推送
6. 写入发布/推送历史，避免重复处理

### 关键状态字段（数据库）

- `review_status`：审核状态
- `auto_publish_enabled`：是否进入自动发布候选
- `publish_stage`：`local` / `draft` / `published`
- `cms_id`：CMS 文章 ID
- `published_strategy`：`manual` / `auto`

### 当前正文尾注规则（自动发布）

- 如果作者行已包含来源身份（例如“作者/编译”里已经出现 TechFlow、BlockBeats 等），则不再追加“来源/原文”行。
- 其他情况下，自动发布尾注标签使用“原文：xxx”（不再用“来源：xxx”）。
- 手动发布仍保持“来源：xxx”逻辑（除非后续再统一）。

---

## 7. 自动发布去重与重复发布防护

系统内有多层去重：

- 候选筛选去重（按状态与历史）
- 发布窗口内配额控制
- 发布/推送历史记录校验
- 对已发布文章 ID 的状态回写

> 说明：重复发布通常由“同一文章在不同环节被重复触发”或“草稿/发布状态回写异常”导致。排障时请优先查 `logs/pipeline.log` 与数据库 `publish_stage/cms_id/published_strategy`。

---

## 8. 配置说明（建议补充到 config.yaml）

你们线上常用的 ChainThink 认证头建议统一支持：

- `x-app-id`
- `x-token`
- `x-user-id`

如果是多人使用，建议每人独立配置并通过设置页动态保存，避免共用 token 导致发布失败或串号。

---

## 9. 常用命令

### 前端

```bash
npm --prefix frontend run dev
npm --prefix frontend run build
```

### 后端语法检查

```bash
python -m py_compile backend/services/publisher.py
python -m py_compile backend/services/pipeline_service.py
```

### Git（常用）

```bash
git status
git add .
git commit -m "中文备注"
git push
```

---

## 10. 线上部署建议

1. 本地先构建并自测
2. 提交并打版本标记（tag）
3. 部署到服务器并重启服务
4. 观察 1 个自动发布窗口周期
5. 校验 CMS 草稿箱、已发布列表、App 推送记录

建议服务化运行（systemd 或 supervisor），并保留近 7 天日志。

---

## 11. 故障排查清单

## 11.1 “达到分数但没有自动存草稿/发布”

检查项：

- 该文章 `auto_publish_enabled` 是否为 1
- 自动发布调度是否启动
- 当前是否处于发布窗口
- token 是否过期（日志中通常有 401/403）
- 过滤规则是否把该来源/关键词排除

## 11.2 “同一篇文章发布两次”

检查项：

- 是否被多个调度器重复命中
- 是否同一文章被“手动发布 + 自动发布”双触发
- `publish_stage` 与 `cms_id` 回写是否一致
- `push_history` / `broadcast_history` 是否已有记录但未被校验

## 11.3 “页面文案乱码/中文显示异常”

检查项：

- 文件编码是否 UTF-8
- i18n key 是否缺失
- 前端缓存是否未刷新（强刷 + 清缓存）

---

## 12. 安全建议

- 不要把真实 token 直接提交到 Git
- 使用环境变量管理密钥
- 定期轮换 `x-token`
- 对管理接口启用登录鉴权

---

## 13. 版本与变更建议

建议使用以下规范：

- 功能：`feat: xxx`
- 修复：`fix: xxx`
- 运维：`chore: xxx`

中文提交示例：
- `fix: 修复自动发布来源尾注重复问题`
- `feat: 新增 ChainThink app_id 与 user_id 配置项`

---

## 14. English Summary

This project is an end-to-end article ingestion and publishing system:
- Multi-source crawling
- Content cleaning/scoring
- Auto draft / auto publish / app push
- CMS integration with dedup and scheduling controls
- React + FastAPI + SQLite architecture

For production, ensure strict token management and log-based monitoring on each publish window.
