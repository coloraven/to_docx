FROM ghcr.linkos.org/unoconv/unoserver-docker
ARG UID=worker
WORKDIR /app

# 安装 FastAPI 及依赖
RUN pip install --no-cache-dir fastapi uvicorn python-multipart httpx -i https://pypi.tuna.tsinghua.edu.cn/simple --break-system-packages

# 追加 `program:main` 到 `supervisord.conf`
USER root
RUN printf "\n[program:main]\n\
environment=PATH=\"/home/worker/.local/bin:/usr/local/bin:/usr/bin:/bin\"\n\
command=uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --log-level info\n\
autostart=true\n\
autorestart=true\n\
redirect_stderr=true\n\
stderr_logfile=/dev/stderr\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile_maxbytes=0\n" >> /supervisor/conf/interactive/supervisord.conf

RUN sed -i 's|supervisord -c "$SUPERVISOR_INTERACTIVE_CONF"|exec supervisord -n -c "$SUPERVISOR_INTERACTIVE_CONF"|' /entrypoint.sh
# 复制 main.py
COPY mainweb.py /app/main.py
USER ${UID}
