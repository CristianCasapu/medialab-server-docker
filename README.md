# medialab Server – container image

[Română](README.ro.md)

Container image of **medialab Server**, a GPL-2.0 fork of [Jellyfin](https://jellyfin.org) 12.2
([server](https://github.com/CristianCasapu/medialab-server), [web](https://github.com/CristianCasapu/medialab-server-web)),
built from the signed Debian packages of the medialab apt repository (`https://apt.medialab.works/debian`).
Nothing is compiled in this repository: the image installs `medialab-server`, `medialab-server-web` and
`jellyfin-ffmpeg8` from the repository over HTTPS, with the repository signature checked by apt and the signing key
pinned by fingerprint.

```
ghcr.io/cristiancasapu/medialab-server:latest        # newest release
ghcr.io/cristiancasapu/medialab-server:12.2          # newest 12.2 release
ghcr.io/cristiancasapu/medialab-server:12.2-ml.5     # one release (recommended for production)
ghcr.io/cristiancasapu/medialab-server:12.2-ml5-deb12  # the exact apt version
```

Architectures: `linux/amd64`, `linux/arm64`.

The main goal of the image is that **everything can be configured from outside**: server settings, the first
administrator, plugin repositories, plugins, plugin settings and licence keys come from environment variables (or
files / secrets), so a server can be recreated from a Compose file or a Kubernetes manifest.

## Quick start

```sh
docker run -d --name medialab-server --restart unless-stopped \
  -p 8096:8096 \
  -v /srv/medialab/config:/config -v /srv/medialab/cache:/cache -v /srv/media:/media:ro \
  -e PUID=1000 -e PGID=1000 -e TZ=Europe/Bucharest \
  ghcr.io/cristiancasapu/medialab-server:latest
```

Open `http://<host>:8096` and follow the setup wizard, or let the container create the administrator for you:

```sh
printf '%s' 'a-long-password' > /srv/medialab/admin_password
docker run ... \
  -v /srv/medialab/admin_password:/run/secrets/admin_password:ro \
  -e MLW_ADMIN_USER=admin -e MLW_ADMIN_PASSWORD_FILE=/run/secrets/admin_password \
  ghcr.io/cristiancasapu/medialab-server:latest
```

More examples in [`examples/`](examples):
[`docker-run.sh`](examples/docker-run.sh),
[`compose.yaml`](examples/compose.yaml) + [`.env.example`](examples/.env.example),
[`compose.intel.yaml`](examples/compose.intel.yaml), [`compose.nvidia.yaml`](examples/compose.nvidia.yaml),
[Unraid template](examples/unraid/medialab-server.xml), [Portainer stack](examples/portainer/stack.yml),
[Kubernetes](examples/kubernetes/medialab-server.yaml).

## Volumes and ports

| Path | Content |
|---|---|
| `/config` | settings (`/config/config/*.xml`), database, plugins (`/config/plugins`), logs (`/config/log`), metadata. **Back this up.** |
| `/cache` | image cache and transcoding files; can be lost. |
| `/media` | your media (mount read-only if the server does not need to write there). |
| `/data` | optional extra mount point (e.g. a second library). |

| Port | Use |
|---|---|
| `8096/tcp` | HTTP: web interface, apps, API |
| `8920/tcp` | HTTPS, only when enabled with a certificate (`MLW_ENABLE_HTTPS`) |
| `7359/udp` | client auto-discovery on the local network (optional) |
| `1900/udp` | DLNA / SSDP, for plugins that use it (optional) |

## Configuration from the environment

The full list is in **[docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)**. In short:

- **Container:** `PUID`, `PGID`, `UMASK`, `TZ`, `MLW_EXTRA_GIDS`, `MLW_CHOWN`.
- **Server settings** (written to `system.xml`, `network.xml`, `encoding.xml` before the server starts):
  `MLW_SERVER_NAME`, `MLW_UI_CULTURE`, `MLW_METADATA_LANGUAGE`, `MLW_METADATA_COUNTRY`, `MLW_PUBLISHED_URL`,
  `MLW_BASE_URL`, `MLW_KNOWN_PROXIES`, `MLW_REMOTE_ACCESS`, `MLW_HTTPS_PORT`, `MLW_PUBLIC_HTTPS_PORT`,
  `MLW_HW_ACCEL`, … and any other property through `MLW_SYSTEM__<Property>`, `MLW_NETWORK__<Property>`,
  `MLW_ENCODING__<Property>`, `MLW_CONF__<file>__<Property>`.
- **When they are written:** `MLW_CONFIG_MODE=first-run` (default) writes a value on a new server and again only when
  you change the variable, so changes made in the dashboard are kept; `MLW_CONFIG_MODE=enforce` writes them at every
  start.
- **First administrator:** `MLW_ADMIN_USER` + `MLW_ADMIN_PASSWORD` / `MLW_ADMIN_PASSWORD_FILE` create the administrator
  and complete the setup wizard through the server's startup API (new servers only).
- **Plugins:** `MLW_PLUGIN_REPOS` (default `medialab,jellyfin`), `MLW_REPO_KEY` (your keyed medialab.works catalog),
  `MLW_PLUGINS="jf-rosub,jf-registration@1.0.2"` (installed before the server starts, MD5 checked, medialab
  signatures kept), `MLW_PLUGINS_UPDATE=true`, and plugin settings as `MLW_PLUGIN_<SLUG>__<Property>=value`
  (or mount `/config/plugins/configurations/<Assembly>.xml`).
- **Licence keys:** `MLW_LICENSE_KEY`, `MLW_LICENSE_KEY_<SLUG>`, their `_FILE` forms and the Docker secrets
  `mlw_license_key[_<slug>]` are passed unchanged to the server process, for the plugin versions that read them from the
  environment (available from plugin versions that support it; until then, enter the key in the plugin's page).
- **Secrets:** every variable also accepts `<NAME>_FILE=/path`. Passwords and keys are never written to the logs; the
  administrator password and the repository key are removed from the server's environment.

## Hardware acceleration

**Intel (QSV / VAAPI) and AMD (VAAPI):** pass the GPU and choose the method. The entrypoint adds the server user to
the groups that own `/dev/dri/*`, whatever their numbers are on the host.

```sh
docker run ... --device /dev/dri:/dev/dri -e MLW_HW_ACCEL=qsv ...     # Intel
docker run ... --device /dev/dri:/dev/dri -e MLW_HW_ACCEL=vaapi ...   # AMD, older Intel
```

The amd64 image includes Intel's OpenCL runtime from Debian 12 (`intel-opencl-icd`, used for HDR tone mapping); the
`jellyfin-ffmpeg8` package brings its own VAAPI / QSV drivers (iHD, i965, radeonsi).

**NVIDIA (NVENC / NVDEC):** install the NVIDIA driver and the
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/) on the host, then:

```sh
docker run ... --gpus all -e MLW_HW_ACCEL=nvenc ...
```

(`--runtime=nvidia` on Unraid; `compose.nvidia.yaml` for Compose; the `nvidia.com/gpu` resource on Kubernetes.)
`NVIDIA_VISIBLE_DEVICES=all` and `NVIDIA_DRIVER_CAPABILITIES=compute,video,utility` are already set in the image.

Check the result in Dashboard → Playback → Transcoding, and in the transcoding logs in `/config/log`.

## Updates

Update by pulling a new image and recreating the container; `/config` is kept:

```sh
docker pull ghcr.io/cristiancasapu/medialab-server:12.2-ml.6
docker stop medialab-server && docker rm medialab-server
docker run ... ghcr.io/cristiancasapu/medialab-server:12.2-ml.6     # same options as before
# Compose: change the tag (or keep "latest"), then: docker compose pull && docker compose up -d
```

The in-app updater of the Debian package (a root system service) is **not** included in the image. The
"Self-Update by MediaLab" plugin detects that and only shows the available versions; it does not install packages in a
container. Plugins are updated from the dashboard as usual, or with `MLW_PLUGINS_UPDATE=true`.

A new image is built automatically when a new `medialab-server` version appears in the apt repository, and every
Monday (Debian security updates). Pin a release tag (`12.2-ml.5`) if you want to decide when to update.

## Backup

Stop the container (or at least make sure no scan is running) and copy `/config`:

```sh
docker stop medialab-server
tar -C /srv/medialab -czf medialab-config-$(date +%F).tar.gz config
docker start medialab-server
```

`/cache` does not need a backup. To restore, put the folder back and start the same (or a newer) image.

## Building the image yourself

```sh
docker buildx build --platform linux/amd64,linux/arm64 \
  --build-arg MLW_VERSION=12.2+ml5+deb12 -t medialab-server:12.2-ml.5 .
```

| Build argument | Default | Description |
|---|---|---|
| `MLW_VERSION` | see [`MLW_VERSION`](MLW_VERSION) | apt version of `medialab-server` / `medialab-server-web` (`latest` = newest) |
| `FFMPEG_VERSION` | `latest` | apt version of `jellyfin-ffmpeg8` |
| `MLW_APT_URL` | `https://apt.medialab.works/debian` | apt repository |
| `MLW_KEY_FPR` | `6B7D46D82C3C4D4C0A142F92418996EB3CE159C7` | expected fingerprint of the repository signing key |
| `INTEL_OPENCL` | `true` | install `intel-opencl-icd` on amd64 |
| `DEBIAN_TAG` | `bookworm-slim` | base image tag |

The GitHub workflow [`build.yml`](.github/workflows/build.yml) builds both architectures with Buildx, pushes them to
GHCR with OCI labels, an SBOM and build provenance; [`check-apt.yml`](.github/workflows/check-apt.yml) checks the apt
repository every day.

## Troubleshooting

- **The container stops right away with `[medialab] ERROR: …`:** a variable has a wrong value (e.g. a boolean that is
  not `true`/`false`); the message names it.
- **Permission denied on `/config` or `/media`:** check `PUID`/`PGID` (`id -u`, `id -g` of the owner of your files);
  `/media` is never changed by the container. With `--user`, the mounted folders must already belong to that user.
- **Settings from the environment do not seem to apply:** in `first-run` mode a value is written only on a new server or
  when you change it; use `MLW_CONFIG_MODE=enforce` to force it, and look for `[medialab] … = …` lines in `docker logs`.
- **Plugin not installed:** `docker logs` says why (repository not reachable, name not found, checksum mismatch, no
  version compatible with the server). The server starts anyway unless `MLW_PLUGINS_STRICT=true`.
- **Hardware transcoding fails:** check that the device exists in the container (`docker exec medialab-server ls -l /dev/dri`),
  that `MLW_HW_ACCEL` matches the GPU, and the ffmpeg log in `/config/log`.
- **Behind a reverse proxy:** set `MLW_KNOWN_PROXIES` to the proxy's address (or subnet), `MLW_PUBLISHED_URL` to the
  public URL and, for a sub-path, `MLW_BASE_URL`.

## Licence

GPL-2.0 (see [LICENSE](LICENSE)), like Jellyfin and medialab Server. The image contains Debian packages under their own
licences (see `/usr/share/doc/*/copyright` in the image). Jellyfin is a trademark of the Jellyfin project; medialab Server
is an independent fork and is not endorsed by the Jellyfin project.
