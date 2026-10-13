# Install medialab Server in a container

medialab Server is published as a container image for `linux/amd64` and `linux/arm64`:

```
ghcr.io/cristiancasapu/medialab-server
```

The image is built from the same signed Debian packages as the apt repository (`medialab-server`,
`medialab-server-web`, `jellyfin-ffmpeg8`); its build files are public at
[github.com/CristianCasapu/medialab-server-docker](https://github.com/CristianCasapu/medialab-server-docker) (GPL-2.0).

Tags:

| Tag | Meaning |
|---|---|
| `12.2-ml.5` | one release; recommended when you want to choose when to update |
| `12.2` | the newest release based on Jellyfin 12.2 |
| `latest` | the newest release |
| `12.2-ml5-deb12` | the exact apt version inside the image |

## What you need

- Docker (or Podman, Unraid, Portainer, Kubernetes) on a 64-bit x86 or ARM machine.
- A folder for the settings (`/config`), one for the cache (`/cache`) and your media folder (`/media`).
- The numeric user and group that should own the settings: `id -u` and `id -g` of that account (`PUID`, `PGID`).

## docker run

```sh
docker run -d --name medialab-server --restart unless-stopped \
  -p 8096:8096 -p 7359:7359/udp \
  -v /srv/medialab/config:/config \
  -v /srv/medialab/cache:/cache \
  -v /srv/media:/media:ro \
  -e PUID=1000 -e PGID=1000 -e TZ=Europe/Bucharest \
  ghcr.io/cristiancasapu/medialab-server:latest
```

Open `http://<server>:8096`. On a new server the setup wizard asks for the first administrator, the language and your
libraries (add them from `/media`).

To skip the wizard, let the container create the administrator. Put the password in a file, not on the command line:

```sh
printf '%s' 'a-long-password' > /srv/medialab/admin_password
docker run -d ... \
  -v /srv/medialab/admin_password:/run/secrets/admin_password:ro \
  -e MLW_ADMIN_USER=admin \
  -e MLW_ADMIN_PASSWORD_FILE=/run/secrets/admin_password \
  ghcr.io/cristiancasapu/medialab-server:latest
```

This only works on a new server; on a server that is already set up the variables are ignored. The password never
appears in the container logs.

## Docker Compose

`compose.yaml`:

```yaml
services:
  medialab-server:
    image: ghcr.io/cristiancasapu/medialab-server:12.2-ml.5
    container_name: medialab-server
    restart: unless-stopped
    ports:
      - "8096:8096"
      - "7359:7359/udp"
    volumes:
      - ./config:/config
      - ./cache:/cache
      - /srv/media:/media:ro
    environment:
      PUID: 1000
      PGID: 1000
      TZ: Europe/Bucharest
      MLW_SERVER_NAME: Home media
      MLW_ADMIN_USER: admin
      MLW_ADMIN_PASSWORD_FILE: /run/secrets/admin_password
    secrets:
      - admin_password

secrets:
  admin_password:
    file: ./secrets/admin_password
```

```sh
mkdir -p secrets && printf '%s' 'a-long-password' > secrets/admin_password
docker compose up -d
docker compose logs -f
```

A complete example with an `.env` file is in the repository (`examples/compose.yaml`, `examples/.env.example`).

## Unraid

1. In the Docker tab, choose **Add Container** and set **Template** to the URL
   `https://raw.githubusercontent.com/CristianCasapu/medialab-server-docker/main/examples/unraid/medialab-server.xml`
   (or copy the file to `/boot/config/plugins/dockerMan/templates-user/`).
2. Check the paths: `/config` → `/mnt/user/appdata/medialab-server`, `/media` → your media share.
3. `PUID` 99 and `PGID` 100 are the usual Unraid values (nobody / users).
4. Intel or AMD GPU: add `--device=/dev/dri` to **Extra Parameters** and set **Hardware acceleration** to `qsv`
   or `vaapi`. NVIDIA: install the Nvidia-Driver plugin, add `--runtime=nvidia` and set it to `nvenc`.
5. Apply, then open the WebUI.

## Portainer

1. **Stacks → Add stack → Web editor** and paste `examples/portainer/stack.yml` from the repository.
2. Under **Environment variables**, load `examples/portainer/stack.env` (or add the variables by hand) and adjust the
   paths, `PUID`, `PGID` and `TZ`.
3. **Deploy the stack.**

Portainer stacks cannot use Docker secrets on a standalone host, so the example passes `MLW_ADMIN_PASSWORD` as a stack
variable. It is only used once; you can delete it after the first start.

## Kubernetes

`examples/kubernetes/medialab-server.yaml` contains a ConfigMap, two PersistentVolumeClaims, a Deployment (one
replica, `Recreate` strategy, health probes on `/health`), a Service and an Ingress:

```sh
kubectl create namespace medialab
kubectl -n medialab create secret generic medialab-secrets \
  --from-literal=admin-password='a-long-password' --from-literal=license-key='' --from-literal=repo-key=''
kubectl -n medialab apply -f medialab-server.yaml
```

Adjust the storage sizes, the media volume (an NFS example is included) and the host name first. Run only one replica:
the server keeps its database in `/config`.

## Hardware acceleration

**Intel (QSV / VAAPI) and AMD (VAAPI)**

```sh
docker run ... --device /dev/dri:/dev/dri -e MLW_HW_ACCEL=qsv ...     # Intel
docker run ... --device /dev/dri:/dev/dri -e MLW_HW_ACCEL=vaapi ...   # AMD or older Intel
```

The container adds the server user to the groups that own `/dev/dri/*` by itself, so you do not need to look up the
`render` and `video` group numbers. The drivers come with `jellyfin-ffmpeg8`; the amd64 image also contains Intel's
OpenCL runtime from Debian 12 for HDR tone mapping (very new Intel GPUs may need a newer runtime than Debian 12 has).

**NVIDIA (NVENC / NVDEC)**

Install the NVIDIA driver and the NVIDIA Container Toolkit on the host, then:

```sh
docker run ... --gpus all -e MLW_HW_ACCEL=nvenc ...
```

With Compose, add `examples/compose.nvidia.yaml`; on Kubernetes request `nvidia.com/gpu: 1`.

After the first start, check Dashboard → Playback → Transcoding and play a video that needs transcoding; the ffmpeg
log in `/config/log` shows whether the GPU was used.

## Plugins, settings and licences from outside

Everything below is optional; the full list of variables is in `docs/ENVIRONMENT.md` in the repository.

**Server settings.** For example:

```sh
-e MLW_PUBLISHED_URL=https://media.example.org \
-e MLW_KNOWN_PROXIES=172.16.0.0/12 \
-e MLW_UI_CULTURE=en-US -e MLW_METADATA_COUNTRY=US \
-e MLW_REMOTE_ACCESS=true
```

They are written into `system.xml`, `network.xml` and `encoding.xml` before the server starts. With the default
`MLW_CONFIG_MODE=first-run` a value is written on a new server and again only when you change the variable, so what you
change later in the dashboard is kept. `MLW_CONFIG_MODE=enforce` writes them at every start. Any other property can be
set with `MLW_SYSTEM__<Property>`, `MLW_NETWORK__<Property>` and `MLW_ENCODING__<Property>`.

**Plugin catalog.** The public medialab.works catalog and Jellyfin's official repository are added by default
(`MLW_PLUGIN_REPOS=medialab,jellyfin`). If your account has a repository key, add it with `MLW_REPO_KEY` (or
`MLW_REPO_KEY_FILE`); it is masked in the logs.

**Plugins.** List them in `MLW_PLUGINS`; they are installed before the server starts:

```sh
-e MLW_PLUGINS="jf-rosub,jf-registration@1.0.2"
```

A plugin is found by its slug (`jf-rosub`), its name or its GUID; `@version` pins a version. The archive is checked
against the checksum in the catalog, and the medialab signature (`.dll.sig`) is kept, so the dashboard shows the plugin
as verified. Plugins already installed are not downloaded again; `MLW_PLUGINS_UPDATE=true` installs newer versions
at start.

**Plugin settings.** Either mount the plugin's configuration file
(`/config/plugins/configurations/<Assembly>.xml`, e.g. `Rosub.xml`) or set single values:

```sh
-e MLW_PLUGIN_ROSUB__ArchiveCacheDays=14
```

**Licence keys.** `MLW_LICENSE_KEY`, `MLW_LICENSE_KEY_<SLUG>` (e.g. `MLW_LICENSE_KEY_JF_ROSUB`), their `_FILE` forms and
Docker secrets named `mlw_license_key` or `mlw_license_key_<slug>` are passed unchanged to the server process. Plugins
read them from there in the plugin versions that support it; with an older plugin version, enter the key in the
plugin's page in the dashboard (it is saved in `/config`).

Every variable also accepts `<NAME>_FILE=/path/to/file`, for Docker and Kubernetes secrets.

## Updates

Pull the new image and recreate the container; the settings in `/config` stay:

```sh
docker pull ghcr.io/cristiancasapu/medialab-server:12.2-ml.6
docker stop medialab-server && docker rm medialab-server
docker run -d ... ghcr.io/cristiancasapu/medialab-server:12.2-ml.6     # same options as before
```

With Compose: change the tag in `compose.yaml` (or keep `latest`), then `docker compose pull && docker compose up -d`.
On Unraid: **Check for Updates** in the Docker tab. In Portainer: **Recreate** with **Re-pull image**.

The in-app updater of the Debian package is not part of the image. "Self-Update by MediaLab" shows the available
versions in a container but does not install packages; update by pulling the new image tag (`12.2-ml.N`) and recreating
the container.

## Backup

`/config` holds everything that matters (settings, users, database, plugins, metadata). Stop the container and copy it:

```sh
docker stop medialab-server
tar -C /srv/medialab -czf medialab-config-$(date +%F).tar.gz config
docker start medialab-server
```

`/cache` can be rebuilt and needs no backup. To restore, put `config` back in place and start the same image tag or a
newer one.

## Troubleshooting

- **See what the container did:** `docker logs medialab-server`. Lines starting with `[medialab]` come from the
  container's start-up script (settings written, plugins installed, administrator created).
- **The container stops at once with `[medialab] ERROR`:** a variable has an invalid value; the message names it.
- **"Permission denied":** `PUID`/`PGID` do not match the owner of the folders. The container fixes `/config` and
  `/cache` by itself, never `/media`. Started with `--user`, it changes nothing: the folders must already belong to that
  user.
- **A setting from the environment is not applied:** in `first-run` mode a value is written on a new server or when it
  changes. Use `MLW_CONFIG_MODE=enforce` to impose it.
- **A plugin is not installed:** the log says why (catalog not reachable, name not found, checksum mismatch, no version
  for this server). The server still starts, unless `MLW_PLUGINS_STRICT=true`.
- **Container shown as unhealthy:** the health check calls `/health` on port 8096 (or the port and base URL in
  `network.xml`). The first start can take a minute or two.
- **Behind a reverse proxy, clients get the wrong address:** set `MLW_KNOWN_PROXIES` to the proxy's address and
  `MLW_PUBLISHED_URL` to the public URL.
