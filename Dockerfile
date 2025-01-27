FROM docker.linkos.org/bitnami/java

# 设置非交互模式以避免交互式提示
ENV DEBIAN_FRONTEND=noninteractive

# 替换为清华的 Debian 源
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list && \
    sed -i 's|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list

# 更新包列表并安装 LibreOffice Headless 和 Python 环境
RUN apt-get update && apt-get install -y \
    libreoffice \
    libreoffice-java-common \
    libreoffice-writer \
    python3 \
    python3-pip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*



# 安装 FastAPI 和 Uvicorn
RUN pip install --no-cache-dir fastapi uvicorn unoconv python-multipart -i https://pypi.tuna.tsinghua.edu.cn/simple --break-system-packages

# 验证 Java 和 LibreOffice 的安装
RUN java -version && soffice --version

# 创建一个 app 目录并复制源代码
COPY ./app /app
COPY ./static /app/static
# 暴露 FastAPI 默认端口
EXPOSE 8000
# 设置新的 ENTRYPOINT（覆盖基础镜像的 ENTRYPOINT）
ENTRYPOINT []
# 启动 FastAPI 服务
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
