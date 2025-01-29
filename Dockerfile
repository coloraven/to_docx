FROM ghcr.linkos.org/unoconv/unoserver-docker

WORKDIR /app

# 复制 main.py 进入容器
COPY mainweb.py /app/main.py

# 安装 FastAPI 及依赖
RUN pip install --no-cache-dir fastapi uvicorn

# 修改原 `entrypoint.sh`，在 `unoserver --interface 0.0.0.0` 之后增加 `python3 /app/main.py &`
RUN sed -i '/unoserver --interface 0.0.0.0/a python3 /app/main.py &' /entrypoint.sh


