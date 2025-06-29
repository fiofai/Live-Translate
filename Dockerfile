# 第一阶段：构建依赖
FROM python:3.11-slim-bookworm AS builder

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libssl-dev \
    pkg-config \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# 安装 Rust 工具链
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# 创建并设置工作目录
WORKDIR /app

# 复制并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# 第二阶段：运行时镜像
FROM python:3.11-slim-bookworm

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libssl1.1 \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN useradd -m appuser
WORKDIR /app
USER appuser

# 从构建阶段复制安装的Python包
COPY --from=builder /install /usr/local
# 复制应用代码
COPY . /app/

# 创建必要的目录结构
RUN mkdir -p /app/encoder/saved_models \
    /app/synthesizer/saved_models \
    /app/vocoder/saved_models \
    /app/voice_samples \
    /app/voice_embeddings \
    && touch /app/encoder/saved_models/.gitkeep \
    /app/synthesizer/saved_models/.gitkeep \
    /app/vocoder/saved_models/.gitkeep \
    /app/voice_samples/.gitkeep \
    /app/voice_embeddings/.gitkeep

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "main.py"] 