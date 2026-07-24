ARG BUILD_FROM
FROM ${BUILD_FROM}

# Same base and library builds as the pi_somfy add-on (design doc §7):
# lgpio from source (for Pi 5) and pigpiod from source (for Pi 1/2/3/4).
COPY patch_pigpiod.py /tmp/patch_pigpiod.py
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-dev \
        procps \
        git \
        make \
        gcc \
        g++ \
        libc6-dev \
        swig \
    && cd /tmp \
    && git clone --depth 1 https://github.com/joan2937/lg.git \
    && cd lg \
    && make \
    && make install \
    && cd /tmp/lg/PY_LGPIO \
    && pip3 install --no-cache-dir --break-system-packages . \
    && cd /tmp \
    && git clone --depth 1 https://github.com/joan2937/pigpio.git \
    && python3 /tmp/patch_pigpiod.py /tmp/pigpio/pigpiod.c \
    && cd pigpio \
    && make \
    && make install \
    && cd / \
    && rm -rf /tmp/lg /tmp/pigpio /tmp/patch_pigpiod.py \
    && apt-get purge -y --auto-remove make gcc g++ libc6-dev swig python3-dev \
    && rm -rf /var/lib/apt/lists/*

# paho-mqtt is optional at runtime (only used when mqtt_host is configured)
RUN pip3 install --no-cache-dir --break-system-packages paho-mqtt

COPY sniffer.py /sniffer.py
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
