# 基于 sanketb/libreoffice-headless:alpine
FROM sanketb/libreoffice-headless:alpine

# 设置工作目录
WORKDIR /app

# 替换为清华的 Alpine 源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories

# 安装 Python 和 pip
RUN apk update && apk add --no-cache \
    python3 \
    py3-pip \
    && python3 -m ensurepip \
    && pip3 install --no-cache-dir --upgrade pip

# 配置 pip 使用清华源
RUN mkdir -p ~/.pip && \
    echo "[global]\nindex-url = https://pypi.tuna.tsinghua.edu.cn/simple\n" > ~/.pip/pip.conf

# 安装 FastAPI 和 Uvicorn
RUN pip install --no-cache-dir fastapi uvicorn unoconv python-multipart


# 创建一个 app 目录并复制源代码
COPY ./app /app
COPY ./static /app/static
# 暴露 FastAPI 默认端口
EXPOSE 8000
# 设置新的 ENTRYPOINT（覆盖基础镜像的 ENTRYPOINT）
ENTRYPOINT []
# 启动 FastAPI 服务
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
