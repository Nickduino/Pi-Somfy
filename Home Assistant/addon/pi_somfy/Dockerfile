ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install system dependencies (Debian base)
# Build lgpio from source (for Pi 5) and pigpiod from source (for Pi 1/2/3/4)
COPY patch_pigpiod.py /tmp/patch_pigpiod.py
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-dev \
        procps \
        curl \
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

# Clone Pi-Somfy source at build time
ARG BUILD_VERSION
RUN git clone --branch v${BUILD_VERSION} --depth 1 https://github.com/Nickduino/Pi-Somfy.git /somfy

WORKDIR /somfy

# Install Python dependencies (excluding paho-mqtt — not needed without -m flag)
RUN pip3 install --no-cache-dir --break-system-packages \
    ephem \
    configparser \
    Flask \
    requests

# Copy run script
COPY run.sh /
RUN chmod a+x /run.sh

# Health check via the watchdog URL
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -sf http://127.0.0.1:80/cmd/getConfig || exit 1

CMD ["/run.sh"]
