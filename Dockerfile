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
    pip install --no-cache-dir --prefix=/install -r requirements.txt && \
    pip install --no-cache-dir --prefix=/install huggingface_hub qrcode pillow

# 第二阶段：运行时镜像
FROM python:3.11-slim-bookworm

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN useradd -m appuser

# 从构建阶段复制安装的Python包
COPY --from=builder /install /usr/local

# 设置工作目录
WORKDIR /app

# 复制应用代码
COPY . /app/

# 切换到root用户以设置权限
USER root

# 授权确保有写入权限
RUN chmod -R 755 /app

# 创建临时目录
RUN mkdir -p /app/temp

# 更改临时目录的所有权
RUN chown -R appuser:appuser /app/temp

# 切换回非root用户
USER appuser

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "main.py"] 
