# 🤖 Xianyu RAG Agent — 闲鱼智能客服系统（RAG 知识库 + 可视化平台）

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com/)
[![Vue3](https://img.shields.io/badge/Vue3-3.5-42b883)](https://vuejs.org/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5-FF6F00)](https://www.trychroma.com/)
[![LLM](https://img.shields.io/badge/LLM-DashScope-7C3AED)](https://dashscope.aliyun.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE)

> 基于 LLM 的闲鱼平台 7×24 自动值守方案，集成 **多专家 Agent 路由**、**RAG 知识库检索增强** 与 **全栈可视化管控平台**，让 AI 客服既懂业务、又能管。

---

## 📖 项目简介

Xianyu RAG Agent 是一套闲鱼二手交易平台的智能客服系统。它在「WebSocket 实时消息接入 + LLM 多专家路由回复」的基础之上，新增了 **RAG 检索增强生成** 和 **Web 可视化管控平台** 两大核心模块，解决了原系统「知识不可控、回复无溯源、运维纯靠日志」的三大痛点。

### 它能做什么

| 能力 | 说明 |
|------|------|
| 🔄 **7×24 自动值守** | WebSocket 长连接实时接管闲鱼会话，自动回复买家咨询 |
| 🧭 **多专家 Agent 路由** | 关键词规则 + LLM 意图识别，分发到议价 / 技术 / 客服三个专家 Agent |
| 📚 **RAG 知识库** | 上传店铺 FAQ、商品说明书等文档，技术专家回复时自动检索注入，回复有据可依 |
| 💬 **上下文感知** | SQLite 持久化对话历史，支持议价轮次追踪，LLM 带上下文生成 |
| 🖥️ **可视化平台** | 仪表盘统计 + 会话浏览 + 知识库管理 + 提示词在线编辑热更新 |
| 🔧 **进程间通信** | SQLite 命令队列，Web 平台下发指令 → 主进程轮询执行，零中间件依赖 |
| 🛡️ **优雅降级** | RAG / LLM 异常时自动跳过不影响主流程，系统始终在线 |

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                      Bot 主进程 (main.py)                     │
│                                                              │
│  WebSocket 长连接 ←→ 闲鱼 IM                                  │
│       │                                                      │
│       ▼                                                      │
│  消息解密 → 时效过滤 → 人工接管判断                            │
│       │                                                      │
│       ▼                                                      │
│  IntentRouter (关键词规则 + LLM 意图分类)                     │
│       │                                                      │
│   ┌───┼───────────┬──────────────┐                           │
│   ▼   ▼           ▼              ▼                           │
│ PriceAgent  TechAgent   DefaultAgent   ClassifyAgent         │
│ (议价专家)  (技术专家)   (客服专家)     (意图分类)             │
│              │ RAG 检索注入 ↑                                  │
│              └───────┬────────────────────────────┘           │
│                      │                                       │
│  控制队列轮询 (每10s) ← 执行 Web 平台下发的热更新命令          │
└──────────┬───────────────────────┬──────────────────────────┘
           │ 读写                    │ 读写
   ┌───────▼──────────┐     ┌───────▼──────────┐
   │   SQLite          │     │   ChromaDB       │
   │   data/chat.db    │     │   data/chroma/   │
   │                   │     │                  │
   │ • messages        │     │ • 文档向量       │
   │ • items           │     │ • 元数据过滤     │
   │ • rag_documents   │     │ • cosine 检索    │
   │ • control_queue   │     └───────┬──────────┘
   │ • bargain_counts  │             │
   └───────┬──────────┘             │
           │ 读                       │ 读写
┌──────────▼──────────────────────────▼─────────────────────────┐
│                Web 进程 (FastAPI :8000)                        │
│                                                              │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ 仪表盘   │ │ 会话浏览    │ │ 知识库   │ │ 提示词管理   │  │
│  │ Dashboard│ │Conversations│ │ RAG CRUD │ │ 热更新       │  │
│  └──────────┘ └────────────┘ └──────────┘ └──────────────┘  │
│                                                              │
│              Vue3 + Element Plus SPA 前端                     │
└──────────────────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| **LLM** | DashScope (通义千问) | 对话生成 + 意图分类 + 文本向量化 |
| **Agent** | Python + OpenAI SDK | 多专家路由、RAG 注入、动态温度策略 |
| **向量库** | ChromaDB | 文档向量化存储 + cosine 语义检索 |
| **存储** | SQLite | 对话历史、商品信息、RAG 元数据、命令队列 |
| **后端** | FastAPI + Uvicorn | REST API + 静态文件托管 |
| **前端** | Vue3 + Element Plus | SPA 管理后台（ESM CDN，零构建） |
| **接入** | WebSockets | 闲鱼 IM 实时消息收发 |
| **部署** | Docker Compose | bot + web 双进程容器编排 |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- 一个 LLM API Key（默认用阿里云百炼平台 DashScope）

### 1. 克隆 & 安装

```bash
git clone <repo-url>
cd xianyu_rag_agent
pip install -r requirements.txt
```

### 2. 配置环境变量

将 `.env.example` 重命名为 `.env`，填入你的配置：

```bash
# ===== 必配 =====
API_KEY=你的百炼平台API_KEY
COOKIES_STR=闲鱼网页端获取的Cookie
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen-max

# ===== 可选 =====
TOGGLE_KEYWORDS=。              # 输入句号切换人工接管
SIMULATE_HUMAN_TYPING=False     # 模拟人工回复延迟
EMBEDDING_MODEL=text-embedding-v3  # RAG 向量化模型
CONTROL_POLL_INTERVAL=10        # 控制队列轮询间隔(秒)
LOG_LEVEL=INFO
```

> **获取 Cookie**：浏览器打开 [goofish.com](https://www.goofish.com) 登录 → F12 控制台 → Network → 点任意请求 → 复制 Cookie 值

### 3. 启动机器人

```bash
python main.py
```

### 4. 启动可视化平台（另开终端）

```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000
```

浏览器打开 `http://localhost:8000` 即可看到管理后台。

---

## 📚 RAG 知识库使用

### 命令行方式

```bash
# 入库店铺通用知识（退换货政策、发货说明等）
python -m xianyu_rag_agent.rag.cli ingest docs/policy.txt --scope shop --title "退换货政策"

# 入库某商品的专属知识（参数、成色说明等）
python -m xianyu_rag_agent.rag.cli ingest docs/phone.txt --scope item --item-id 123456 --title "iPhone15参数"

# 检索测试
python -m xianyu_rag_agent.rag.cli search "电池续航多久" --item-id 123456

# 查看已入库文档
python -m xianyu_rag_agent.rag.cli list

# 统计信息
python -m xianyu_rag_agent.rag.cli stats
```

### 网页方式

启动可视化平台后，进入 **「知识库」** 页面：
1. 选择文件（支持 .txt / .md）
2. 选择范围（店铺通用 / 指定商品）+ 填写商品 ID + 标题
3. 点击「入库」
4. 下方检索测试框可即时验证召回效果

> 知识入库后，`TechAgent` 处理技术咨询时会自动检索并注入回复，无需重启。

---

## 🖥️ 可视化平台

| 页面 | 功能 |
|------|------|
| **仪表盘** | 今日消息数、总消息、会话数、商品数、Bot 回复数、议价会话数；意图分布进度条；近 7 天消息趋势柱状图 |
| **会话浏览** | 左侧会话列表（搜索 + 分页），右侧消息气泡（区分用户/Bot，Bot 回复带意图标签），显示议价次数和商品信息 |
| **知识库** | 文档上传入库、文档列表删除、检索测试 |
| **提示词** | 四个 Agent 提示词在线编辑，保存即写文件并触发热更新（主进程 10 秒内自动重载，无需重启） |

---

### 效果展示

<div align="center">
  <img src="./images/dashboard.png" width="600" alt="仪表盘">
  <br>
  <em>图1: 仪表盘 - 消息统计与意图分布</em>
</div>

<br>

<div align="center">
  <img src="./images/conversations.png" width="600" alt="会话浏览">
  <br>
  <em>图2: 会话浏览 - 对话历史与意图标签</em>
</div>

---

## 🐳 Docker 部署

```bash
docker compose up -d
```

这会启动两个容器：
- **bot** — 机器人主进程（WebSocket 接入 + Agent 路由 + RAG 检索 + 控制队列轮询）
- **web** — 可视化平台（FastAPI :8000）

两者通过共享 `./data` 和 `./prompts` 卷交换数据。

---

## 📁 目录结构

```
xianyu_rag_agent/
├── main.py                     # 机器人主进程入口（WebSocket + 消息处理 + 控制轮询）
├── XianyuAgent.py              # 多专家 Agent 引擎（路由 + RAG 注入 + 动态温度）
├── XianyuApis.py               # 闲鱼 HTTP API 封装（Token / 商品信息）
├── context_manager.py          # SQLite 上下文管理（对话/商品/RAG元数据/命令队列）
├── xianyu_rag_agent/           # RAG 知识库模块
│   └── rag/
│       ├── store.py            #   ChromaDB 向量库封装
│       ├── chunker.py          #   文档切分（段落 + 滑动窗口）
│       ├── retriever.py        #   RAGRetriever（embedding + 检索 + 入库）
│       └── cli.py              #   命令行工具
├── web/                        # 可视化平台
│   ├── app.py                  #   FastAPI 入口
│   ├── deps.py                 #   共享依赖（单例管理）
│   ├── routers/                #   API 路由
│   │   ├── dashboard.py        #     仪表盘统计
│   │   ├── conversations.py    #     会话浏览
│   │   ├── rag.py              #     知识库 CRUD
│   │   └── prompts.py          #     提示词管理
│   └── static/                 #   Vue3 前端（ESM CDN）
│       ├── index.html
│       └── js/
│           ├── app.js          #     主应用 + hash 路由
│           ├── api.js          #     API 客户端
│           └── views/          #     四个页面组件
├── prompts/                    # Agent 提示词模板
├── utils/                      # 闲鱼工具函数（签名/Cookie/解密）
├── data/                       # 运行时数据（SQLite + ChromaDB）
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 🔧 提示词自定义

编辑 `prompts/` 目录下的文件即可定制各专家的行为：

| 文件 | 专家 | 职责 |
|------|------|------|
| `classify_prompt.txt` | 意图分类器 | 判断消息归属 price/tech/default/no_reply |
| `price_prompt.txt` | 议价专家 | 阶梯让步策略，守价格底线 |
| `tech_prompt.txt` | 技术专家 | 参数解读 + RAG 知识注入 |
| `default_prompt.txt` | 客服专家 | 物流/售后/日常咨询 |

也可通过可视化平台的 **提示词** 页面在线编辑，保存后自动热更新。

---

## 📄 License

[MIT License](./LICENSE)
