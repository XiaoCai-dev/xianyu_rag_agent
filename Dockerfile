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
    PYTHONUNBUFFERED=1

# 运行时依赖（hnswlib 编译扩展需要 libstdc++）
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata libstdc++6 \
    && ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo Asia/Shanghai > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

RUN mkdir -p data prompts

# 复制示例提示词文件并重命名为正式文件（挂载卷会覆盖）
COPY prompts/classify_prompt_example.txt prompts/classify_prompt.txt
COPY prompts/price_prompt_example.txt prompts/price_prompt.txt
COPY prompts/tech_prompt_example.txt prompts/tech_prompt.txt
COPY prompts/default_prompt_example.txt prompts/default_prompt.txt

# 复制核心源码
COPY main.py XianyuAgent.py XianyuApis.py context_manager.py ./
COPY utils/ utils/
COPY xianyu_rag_agent/ xianyu_rag_agent/
COPY web/ web/

# bot 进程默认启动命令（web 进程在 docker-compose 中用 uvicorn 覆盖）
CMD ["python", "main.py"]
