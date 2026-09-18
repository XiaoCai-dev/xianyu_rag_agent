FROM python:3.10-slim AS builder

WORKDIR /app

# 构建依赖（chromadb 的 hnswlib 扩展需要 gcc/g++）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 第二阶段：最终镜像
FROM python:3.10-slim

LABEL maintainer="XiaoCai"
LABEL description="闲鱼智能客服系统 (RAG知识库 + 可视化平台)"
LABEL version="1.0"

ENV TZ=Asia/Shanghai \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RUNNING_IN_DOCKER=1 \
    LOG_DIR=/app/data/logs

# 运行时依赖
#   libstdc++6  : chromadb 的 hnswlib 扩展
#   libgomp1    : onnxruntime（本地向量模型）依赖 OpenMP 运行时
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata libstdc++6 libgomp1 \
    && ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo Asia/Shanghai > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

RUN mkdir -p data/logs prompts

# 预热本地向量模型（RAG 离线兜底用），避免首次检索时才下载约 80MB。
# 网络不可用时不让构建失败，运行时会按需重试。
RUN python -c "from chromadb.utils import embedding_functions as ef; ef.DefaultEmbeddingFunction()(['warmup'])" \
    || echo "[warn] 本地向量模型预热失败，首次使用知识库时将重试下载"

# 复制示例提示词文件并重命名为正式文件（挂载卷会覆盖）
COPY prompts/classify_prompt_example.txt prompts/classify_prompt.txt
COPY prompts/price_prompt_example.txt prompts/price_prompt.txt
COPY prompts/tech_prompt_example.txt prompts/tech_prompt.txt
COPY prompts/default_prompt_example.txt prompts/default_prompt.txt

# .env 缺失时的兜底模板（网页「配置管理」也依赖它初始化）
COPY .env.example .

# 复制核心源码
COPY main.py XianyuAgent.py XianyuApis.py context_manager.py ./
COPY utils/ utils/
COPY xianyu_rag_agent/ xianyu_rag_agent/
COPY web/ web/

# bot 进程默认启动命令（web 进程在 docker-compose 中用 uvicorn 覆盖）
CMD ["python", "main.py"]
