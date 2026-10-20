# syntax=docker/dockerfile:1.7
#
# medialab Server container image.
#
# medialab Server is a GPL-2.0 fork of Jellyfin (https://github.com/CristianCasapu/medialab-server,
# https://github.com/CristianCasapu/medialab-server-web). This image installs the signed Debian packages
# from the medialab apt repository (https://apt.medialab.works/debian); nothing is compiled here.
#
# Build (multi-arch):
#   docker buildx build --platform linux/amd64,linux/arm64 \
#     --build-arg MLW_VERSION=12.2+ml5+deb12 -t ghcr.io/cristiancasapu/medialab-server:12.2-ml.5 .

ARG DEBIAN_TAG=bookworm-slim

FROM debian:${DEBIAN_TAG}

# apt version of medialab-server and medialab-server-web ("latest" = newest in the repository).
ARG MLW_VERSION=12.2+ml5+deb12
# apt version of medialab-server-web. Empty = the same version as medialab-server or, when a release only rebuilt the
# server (no web package with that exact version), the newest web package of the same upstream version that is not
# newer than the server (e.g. server 12.2+ml10+deb12 -> web 12.2+ml9+deb12).
ARG MLW_WEB_VERSION=
# apt version of jellyfin-ffmpeg8 ("latest" = newest in the repository).
ARG FFMPEG_VERSION=latest
ARG MLW_APT_URL=https://apt.medialab.works/debian
# Fingerprint of the repository signing key; the build fails if the downloaded keyring holds another key.
ARG MLW_KEY_FPR=6B7D46D82C3C4D4C0A142F92418996EB3CE159C7
# Install Intel's OpenCL runtime on amd64 (HDR tone mapping on Intel GPUs). Set to "false" for a smaller image.
ARG INTEL_OPENCL=true
ARG TARGETARCH

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# The in-app updater of the .deb (a root systemd service driven by /var/lib/medialab-update) cannot work in a
# container: it is never unpacked here, so the "Self-Update by MediaLab" plugin detects "no updater" and only shows
# the available versions. Containers are updated by pulling a new image tag.
COPY rootfs/etc/dpkg/dpkg.cfg.d/medialab-docker /etc/dpkg/dpkg.cfg.d/medialab-docker

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg; \
    # 1. The repository keyring, over HTTPS, pinned to the expected fingerprint.
    curl -fsSL "${MLW_APT_URL}/medialab-archive-keyring.gpg" -o /usr/share/keyrings/medialab-archive-keyring.gpg; \
    fpr="$(gpg --show-keys --with-colons /usr/share/keyrings/medialab-archive-keyring.gpg | awk -F: '/^fpr/ {print $10}')"; \
    test "${fpr}" = "${MLW_KEY_FPR}"; \
    # 2. The repository (apt verifies the InRelease signature with that keyring).
    printf 'Types: deb\nURIs: %s\nSuites: stable\nComponents: main\nSigned-By: /usr/share/keyrings/medialab-archive-keyring.gpg\n' \
        "${MLW_APT_URL}" > /etc/apt/sources.list.d/medialab-bootstrap.sources; \
    apt-get update; \
    # 3. The packages (pinned versions unless "latest").
    pin() { if [ "$2" = latest ]; then echo "$1"; else echo "$1=$2"; fi; }; \
    web="${MLW_WEB_VERSION}"; \
    if [ -z "${web}" ] && [ "${MLW_VERSION}" = latest ]; then web=latest; fi; \
    if [ -z "${web}" ]; then \
        for v in $(apt-cache madison medialab-server-web | awk '{print $3}'); do \
            case "${v}" in "${MLW_VERSION%%+*}+"*) ;; *) continue ;; esac; \
            dpkg --compare-versions "${v}" le "${MLW_VERSION}" || continue; \
            if [ -z "${web}" ] || dpkg --compare-versions "${v}" gt "${web}"; then web="${v}"; fi; \
        done; \
        test -n "${web}"; \
    fi; \
    echo "medialab-server ${MLW_VERSION}, medialab-server-web ${web}"; \
    extra=(); \
    if [ "${TARGETARCH:-$(dpkg --print-architecture)}" = amd64 ] && [ "${INTEL_OPENCL}" = true ]; then extra+=(intel-opencl-icd); fi; \
    apt-get install -y --no-install-recommends \
        "$(pin medialab-server "${MLW_VERSION}")" \
        "$(pin medialab-server-web "${web}")" \
        "$(pin jellyfin-ffmpeg8 "${FFMPEG_VERSION}")" \
        medialab-repo \
        tini tzdata util-linux libfontconfig1 fonts-dejavu-core \
        "${extra[@]}"; \
    # 4. Leftovers of the package scripts that make no sense without systemd.
    # medialab-repo now provides the same source (/etc/apt/sources.list.d/medialab.sources) and keyring.
    rm -f /etc/apt/sources.list.d/medialab-bootstrap.sources; \
    rm -rf /var/lib/medialab-update /var/backups/medialab-server /etc/default/jellyfin \
           /etc/systemd/system/jellyfin.service.d; \
    test ! -e /usr/lib/medialab-server/update.sh; \
    apt-get purge -y --auto-remove gnupg; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/* /var/log/apt /var/log/dpkg.log /tmp/*; \
    # 5. Record what was installed (used for the server ABI and shown in the logs).
    dpkg-query -W -f='${Version}\n' medialab-server > /usr/lib/medialab-docker-version; \
    /usr/lib/jellyfin-ffmpeg/ffmpeg -hide_banner -version | head -n1; \
    test -x /usr/lib/jellyfin/bin/jellyfin; \
    test -f /usr/share/jellyfin/web/index.html

COPY --chmod=0755 rootfs/usr/local/bin/ /usr/local/bin/
COPY --chmod=0755 rootfs/usr/lib/medialab-docker/ /usr/lib/medialab-docker/

ENV PUID=1000 \
    PGID=1000 \
    UMASK=022 \
    TZ=Etc/UTC \
    MLW_CONFIG_MODE=first-run \
    JELLYFIN_DATA_DIR=/config \
    JELLYFIN_CONFIG_DIR=/config/config \
    JELLYFIN_LOG_DIR=/config/log \
    JELLYFIN_CACHE_DIR=/cache \
    JELLYFIN_WEB_DIR=/usr/share/jellyfin/web \
    JELLYFIN_FFMPEG=/usr/lib/jellyfin-ffmpeg/ffmpeg \
    MALLOC_TRIM_THRESHOLD_=131072 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,video,utility \
    MLW_CONTAINER=docker

# 8096 HTTP, 8920 HTTPS (when enabled), 7359/udp client discovery, 1900/udp DLNA/SSDP (plugins).
EXPOSE 8096/tcp 8920/tcp 7359/udp 1900/udp

# World-writable mount points: an empty named volume inherits them, so --user <any uid> works too. The entrypoint
# (as root) gives /config and /cache to PUID:PGID with normal permissions.
RUN mkdir -p /config /cache /media /data && chmod 0777 /config /cache

VOLUME ["/config", "/cache", "/media"]

WORKDIR /config

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 CMD ["/usr/local/bin/healthcheck"]

STOPSIGNAL SIGTERM

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/local/bin/entrypoint"]
CMD []

ARG MLW_IMAGE_REVISION=unknown
LABEL org.opencontainers.image.title="medialab Server" \
      org.opencontainers.image.description="medialab Server (a GPL-2.0 Jellyfin fork) from the signed medialab apt packages, configurable from the environment" \
      org.opencontainers.image.vendor="MediaLab Works" \
      org.opencontainers.image.url="https://medialab.works" \
      org.opencontainers.image.source="https://github.com/CristianCasapu/medialab-server-docker" \
      org.opencontainers.image.documentation="https://github.com/CristianCasapu/medialab-server-docker#readme" \
      org.opencontainers.image.licenses="GPL-2.0-only" \
      org.opencontainers.image.version="${MLW_VERSION}" \
      org.opencontainers.image.revision="${MLW_IMAGE_REVISION}" \
      works.medialab.server.apt-version="${MLW_VERSION}"
