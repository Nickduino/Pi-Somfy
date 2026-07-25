ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install system dependencies (Debian base)
# Build lgpio from source (for Pi 5) and pigpiod from source (for Pi 1/2/3/4)
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
    && cd pigpio \
    && make \
    && make install \
    && cd / \
    && rm -rf /tmp/lg /tmp/pigpio \
    && apt-get purge -y --auto-remove make gcc g++ libc6-dev swig python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone Pi-Somfy source at build time. Defaults below point at this fork's
# testing branch — revert REPO_URL to https://github.com/Nickduino/Pi-Somfy.git
# and GIT_REF to v${BUILD_VERSION} once this merges upstream and a release
# tag exists. Override either at build time with:
#   docker build --build-arg REPO_URL=... --build-arg GIT_REF=... ...
ARG BUILD_VERSION
ARG REPO_URL=https://github.com/orren5/Pi-Somfy.git
ARG GIT_REF=reciever_M1
RUN git clone --branch ${GIT_REF} --depth 1 ${REPO_URL} /somfy

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
