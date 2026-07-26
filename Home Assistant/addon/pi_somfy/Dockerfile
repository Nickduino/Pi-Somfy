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

# Cache-busting for the clone below: Docker caches `RUN git clone` by the
# command's literal text, not by checking whether the remote branch has new
# commits — without this, a rebuild can silently reuse a stale clone from
# before your latest push (and finish suspiciously fast). ADD-from-URL is
# different: Docker re-checks the URL's ETag/Last-Modified on every build, so
# using GitHub's commit API here invalidates the cache below whenever the
# branch actually moves. Testing-only — remove this block alongside
# REPO_URL/GIT_REF once this merges upstream.
# IMPORTANT: the branch name in this URL must always match GIT_REF below —
# if you switch testing branches, update BOTH or this silently stops
# busting the cache (confirmed: this has drifted out of sync before, and
# every rebuild kept re-serving a stale clone from before the branch switch
# with no visible error).
ADD https://api.github.com/repos/orren5/Pi-Somfy/commits/feature/add_mqtt_option /tmp/branch_head.json

# Clone Pi-Somfy source at build time. Defaults below point at this fork's
# testing branch — revert REPO_URL to https://github.com/Nickduino/Pi-Somfy.git
# and GIT_REF to v${BUILD_VERSION} once this merges upstream and a release
# tag exists. Override either at build time with:
#   docker build --build-arg REPO_URL=... --build-arg GIT_REF=... ...
ARG BUILD_VERSION
ARG REPO_URL=https://github.com/orren5/Pi-Somfy.git
ARG GIT_REF=feature/add_mqtt_option
RUN git clone --branch ${GIT_REF} --depth 1 ${REPO_URL} /somfy

WORKDIR /somfy

# Install Python dependencies
RUN pip3 install --no-cache-dir --break-system-packages \
    ephem \
    configparser \
    Flask \
    requests \
    paho-mqtt

# Copy run script
COPY run.sh /
RUN chmod a+x /run.sh

# Health check via the watchdog URL
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -sf http://127.0.0.1:80/cmd/getConfig || exit 1

CMD ["/run.sh"]
