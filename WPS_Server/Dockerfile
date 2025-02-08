FROM debian:bullseye-slim

ARG DEBIAN_FRONTEND=noninteractive

ENV LANG=C.UTF-8 \
    TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    # pip:
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# python3.9(3.9.2)
RUN sed -i "s|http://deb.debian.org/debian|http://mirror.tuna.tsinghua.edu.cn/debian|g" /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y curl procps bsdmainutils xdg-utils libxslt1.1 xvfb libqt5gui5 libqt5xml5 python3 python3-pip && \
    curl -O https://wdl1.pcfg.cache.wpscdn.com/wpsdl/wpsoffice/download/linux/11723/wps-office_11.1.0.11723.XA_amd64.deb && \
    apt install -y ./wps-office_11.1.0.11723.XA_amd64.deb && \
    rm -rf wps-office_11.1.0.11723.XA_amd64.deb && \
    apt remove -y bsdmainutils xdg-utils && \
    apt autoremove -y && \
    mkdir -p /root/.config/Kingsoft/ && \
    # Cleaning cache:
    apt-get clean -y && rm -rf /var/lib/apt/lists/*


COPY ./requirements.txt /app/
RUN python3 -m pip install --no-cache-dir -r /app/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY ./server.py /app/
COPY Office.conf /root/.config/Kingsoft/Office.conf
# for chinese font
ADD SimHei.ttf /usr/share/fonts/

CMD ["python3", "/app/server.py"]
