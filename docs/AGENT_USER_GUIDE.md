# 《Agent使用与部署文档》

**Agent名称：** __article-publisher___

**文档版本：** V1.0

**最后更新日期：** ___2026____年____4___月___28____日

---

## 一、快速开始

### 1. 前提条件

#### 所需账号/权限：
- ChainThink CMS 账号（用于文章发布）
- 腾讯云 COS 账号（用于图片上传）
- LLM API 账号（智谱 GLM-4 / DeepSeek / 通义千问等，可选）

#### 运行环境要求：
- **操作系统**：Linux（推荐） / Windows / macOS
- **Python**：3.10 或更高版本
- **Node.js**：18 或更高版本（用于前端构建）
- **内存**：建议 ≥ 2GB
- **磁盘**：建议 ≥ 10GB（用于日志和数据存储）
- **网络**：可访问目标资讯网站和 LLM API

---

### 2. 部署步骤

#### 步骤1：获取代码

```bash
git clone https://github.com/rye-whisky/article-publisher.git
cd article-publisher
```

#### 步骤2：安装后端依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- fastapi、uvicorn：Web 框架
- requests、beautifulsoup4：网页抓取
- openai：LLM API 客户端
- pyyaml、click：配置和命令行
- pygame（用于 CRC-64 计算）

#### 步骤3：构建前端

```bash
cd frontend
npm install
npm run build
cd ..
```

构建产物将生成在 `frontend/dist/` 目录。

#### 步骤4：配置系统

```bash
cp config.yaml.example config.yaml
# 编辑 config.yaml，填入必要的配置项
```

**最小配置示例：**

```yaml
# ChainThink CMS 配置（必需）
chainthink:
  token: "your_chainthink_token"
  user_id: 123456
  app_id: 789
  api_url: "https://api.chainthink.cn/api/article"
  upload_url: "https://api.chainthink.cn/api/upload"
  push_url: "https://api.chainthink.cn/api/push"  # 可选

# 数据库配置
database:
  sqlite_path: "data/articles.db"

# 路径配置
paths:
  state_file: "data/state.json"
  log_file: "logs/pipeline.log"

# LLM 配置（可选，用于摘要生成和评分）
llm:
  factory: "zhipuai"  # 或 "deepseek"、"openai" 等
  api_url: "https://open.bigmodel.cn/api/paas/v4/chat/completions"
  api_key: "your_llm_api_key"
  model: "glm-4-flash"
```

#### 步骤5：启动服务

```bash
cd backend
python api.py
```

服务启动后，访问 `http://localhost:8000` 即可使用 Web 界面。

#### 步骤6：（可选）使用 systemd 管理服务

创建 `/etc/systemd/system/article-publisher.service`：

```ini
[Unit]
Description=Article Publisher Service
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/article-publisher
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python backend/api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable article-publisher
sudo systemctl start article-publisher
```

---

## 二、使用指南

### 1. 如何启动/调用Agent

#### 方式A：Web 界面（推荐）

访问 `http://your-server:8000`，使用默认账号登录（首次启动会创建）：
- 用户名：`admin`
- 密码：`admin123`（首次登录后请修改）

**主要功能页面：**

1. **Dashboard（仪表盘）**
   - 查看工作流状态
   - 查看最近发布的文章
   - 查看调度器状态
   - 查看推送统计

2. **Articles（文章管理）**
   - 查看所有采集的文章
   - 筛选、排序、搜索
   - 手动发布/推送文章
   - 查看评分详情

3. **Scheduler（调度配置）**
   - 配置各信源的自动采集间隔
   - 启用/禁用自动调度
   - 查看下次运行时间

4. **Settings（系统设置）**
   - LLM 配置
   - 过滤规则管理
   - 提示词管理
   - 用户管理

5. **Logs（实时日志）**
   - 查看系统运行日志
   - 实时日志流（SSE）

#### 方式B：CLI 命令

```bash
# 运行完整流程（采集 + 评分）
cd backend
python cli.py --source all

# 仅采集指定信源
python cli.py --source techflow

# 重新抓取指定文章
python cli.py --refetch-blockbeats-urls "https://theblockbeats.info/news/12345"
```

#### 方式C：API 调用

```bash
# 触发管道运行
curl -X POST "http://localhost:8000/api/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{"source": "all"}'

# 获取文章列表
curl "http://localhost:8000/api/articles?limit=20&status=local"

# 手动发布文章
curl -X POST "http://localhost:8000/api/articles/stcn:123456/publish"
```

---

### 2. 输入/输出说明

#### 输入格式/要求：

- **URL 输入**（重新抓取功能）：支持单个或多个 URL，用空格分隔
- **信源选择**：`stcn`、`techflow`、`blockbeats`、`chaincatcher`、`odaily`、`all`
- **调度配置**：
  - 间隔：1-1440 分钟
  - 启用状态：开启/关闭

#### 输出格式/样例：

**文章数据结构：**

```json
{
  "article_id": "techflow:12345",
  "source_key": "techflow",
  "title": "文章标题",
  "author": "作者名",
  "publish_time": "2026-04-28 10:00:00",
  "original_url": "https://...",
  "cover_src": "https://...",
  "abstract": "AI 生成的摘要...",
  "content": "文章正文（HTML格式）",
  "score": 82,
  "score_reason": "基础分:80, 内容长度:+2",
  "tags": ["DeFi", "以太坊"],
  "category": "other",
  "review_status": "manual_review",
  "publish_stage": "local",
  "created_at": "2026-04-28 10:05:00"
}
```

**运行结果：**

```json
{
  "ok": true,
  "ingested": 12,
  "published": [
    {
      "article_id": "techflow:12345",
      "cms_id": 67890,
      "title": "文章标题",
      "cover_image": "https://..."
    }
  ],
  "failed": []
}
```

---

### 3. 配置项说明

#### 全局配置（config.yaml）

| 配置项 | 说明 | 默认值 | 必需 |
|-------|------|--------|------|
| `chainthink.token` | ChainThink API Token | - | 是 |
| `chainthink.user_id` | ChainThink 用户 ID | - | 是 |
| `chainthink.app_id` | ChainThink 应用 ID | - | 是 |
| `chainthink.api_url` | CMS 文章发布 API | - | 是 |
| `chainthink.upload_url` | COS 图片上传 API | - | 是 |
| `chainthink.push_url` | App 推送 API | - | 否 |
| `database.sqlite_path` | SQLite 数据库路径 | `data/articles.db` | 否 |
| `llm.factory` | LLM 提供商 | - | 否* |
| `llm.api_key` | LLM API Key | - | 否* |
| `sources.*.enabled` | 信源是否启用 | `true` | 否 |
| `sources.*.schedule_interval_minutes` | 自动采集间隔（分钟） | `60` | 否 |

*LLM 配置可选，但不配置会导致摘要生成和评分功能不可用。

#### 调度配置（Web 界面 → Scheduler）

| 配置项 | 说明 | 取值范围 |
|-------|------|---------|
| 采集间隔 | 自动采集的时间间隔 | 1-1440 分钟 |
| 启用状态 | 是否启用自动调度 | 开启/关闭 |
| 自动发布 | 是否启用自动发布到 CMS | 开启/关闭 |
| App 推送 | 是否启用 App 推送 | 开启/关闭 |
| 推送上限 | 每时间窗口最大推送数 | 1-5 |

#### 过滤规则（Web 界面 → Settings → 过滤规则）

| 规则类型 | 说明 | 示例 |
|---------|------|------|
| 标题关键词 | 匹配标题中的关键词 | `行情分析`、`情报局` |
| 内容关键词 | 匹配正文中的关键词 | `广告`、`推广` |
| 作者过滤 | 仅采集指定作者的文章 | `沐阳`、`周乐` |
| 自动发布排除 | 排除不自动发布的标题模式 | `市场综述` |

---

## 三、故障排除

### 1. 常见问题与解决方案

#### 问题1：页面正文为空或内容明显不完整

**可能原因：**
- 网站结构变化
- SPA 页面未正确渲染
- 反爬机制

**解决方案：**
1. 检查日志中的具体错误信息
2. 尝试手动访问 URL 验证页面是否正常
3. 如果是 SPA 网站，检查爬虫实现是否需要更新
4. 考虑添加延迟或使用代理

#### 问题2：AI 摘要生成失败

**可能原因：**
- LLM API Key 无效或过期
- API 调用频率超限
- 网络问题

**解决方案：**
1. 检查 `config.yaml` 中的 LLM 配置
2. 验证 API Key 是否有效
3. 检查账户余额是否充足
4. 查看日志中的具体错误信息

#### 问题3：自动发布不工作

**可能原因：**
- 调度器未启用
- 没有达到评分阈值
- 时间窗口配置问题

**解决方案：**
1. 检查 Scheduler 页面，确认调度器已启用
2. 查看文章评分，确认有 ≥70 分的文章
3. 检查系统设置中的推送配置
4. 查看日志中的调度器运行记录

#### 问题4：语义去重误判

**可能原因：**
- LLM 理解偏差
- 阈值设置不合理

**解决方案：**
1. 在 Settings 中调整语义去重阈值
2. 检查被误判的文章，分析原因
3. 考虑将某些来源加入白名单

#### 问题5：数据库锁定错误

**可能原因：**
- 多个进程同时访问数据库
- 数据库文件损坏

**解决方案：**
1. 确保只有一个服务实例在运行
2. 检查是否有残留的 Python 进程：`ps aux | grep python`
3. 如果数据库损坏，从备份恢复或重建

---

### 2. 日志说明

#### 日志位置

- **主日志**：`logs/pipeline.log`
- **错误日志**：`logs/error.log`（如果配置）

#### 日志级别

- `DEBUG`：详细调试信息
- `INFO`：一般信息（如采集成功）
- `WARNING`：警告信息（如跳过某篇文章）
- `ERROR`：错误信息（如 API 调用失败）

#### 查看日志

```bash
# 查看最新日志
tail -f logs/pipeline.log

# 查看错误日志
tail -f logs/error.log

# 搜索特定关键词
grep "关键词" logs/pipeline.log
```

---

### 3. 性能优化建议

#### 减少内存占用

- 限制并发连接数（已默认限制为 8）
- 定期清理旧文章数据（`cleanup_old_articles`）
- 减少日志保留时间

#### 提高采集速度

- 使用 SSD 存储
- 优化网络连接（使用更近的服务器）
- 合理设置采集间隔，避免频繁触发

#### 降低 LLM 成本

- 使用更便宜的模型（如 `glm-4-flash`）
- 减少摘要长度
- 批量处理（未来版本支持）

---

### 4. 联系人与支持

- **技术咨询**：______whisky______________
- **反馈邮箱**：_____manyuan_whisky@163.com__________
- **GitHub Issues**：https://github.com/rye-whisky/article-publisher/issues

---

**文档维护人：** ___whisky_____
