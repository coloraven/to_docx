FROM  docker.linkos.org/library/eclipse-temurin:23.0.1_11-jdk-alpine


WORKDIR /
RUN sed -i 's#https\?://dl-cdn.alpinelinux.org/alpine#http://mirrors.tuna.tsinghua.edu.cn/alpine#g' /etc/apk/repositories

RUN apk add --no-cache \
    bash curl \
    py3-pip \
    libreoffice \
    supervisor

# fonts - https://wiki.alpinelinux.org/wiki/Fonts
RUN apk add --no-cache \
    font-noto font-noto-cjk font-noto-extra \
    terminus-font \
    ttf-font-awesome \
    ttf-dejavu \
    ttf-freefont \
    ttf-hack \
    ttf-inconsolata \
    ttf-liberation \
    ttf-mononoki  \
    ttf-opensans   \
    fontconfig && \
    fc-cache -f

RUN rm -rf /var/cache/apk/* /tmp/*

# https://github.com/unoconv/unoserver/
RUN pip install --no-cache-dir \
    fastapi uvicorn python-multipart \
    httpx unoserver==3.1 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --break-system-packages
COPY supervisord.conf /supervisor/conf/interactive/supervisord.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x entrypoint.sh
WORKDIR /app
# 复制 main.py
COPY mainweb.py /app/main.py
ENTRYPOINT ["/entrypoint.sh"]