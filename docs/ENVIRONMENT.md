# Environment variables

[Română](ENVIRONMENT.ro.md)

Every variable below can also be given as `<NAME>_FILE=/path/to/file`: the entrypoint reads the file (trailing
newlines removed) and sets `<NAME>`. Use it for Docker / Compose / Kubernetes secrets. If both are set, `<NAME>` wins.

An empty value means "not set": the setting is left to the dashboard.

## How settings are written (`MLW_CONFIG_MODE`)

The entrypoint writes the server settings into the XML files in `/config/config` **before** the server starts.

| Mode | When a value is written |
|---|---|
| `first-run` (default) | when the file does not exist yet (a new server), and again only when you **change** the value of the variable. Changes made later in the dashboard are kept until you change the variable. |
| `enforce` | at every start. Whatever was changed in the dashboard is overwritten by the variables at the next start. |

The entrypoint remembers which values it applied (hashes only, never the values) in `/config/.medialab-docker/state.json`.
Removing a variable never resets the setting: it simply stops being managed.

## Container

| Variable | Default | Description |
|---|---|---|
| `PUID` | `1000` | User id the server runs as. Files in `/config` and `/cache` belong to it. |
| `PGID` | `1000` | Group id the server runs as. |
| `UMASK` | `022` | File creation mask (`002` = group-writable files). |
| `TZ` | `Etc/UTC` | Time zone, e.g. `Europe/Bucharest` (scheduled tasks, logs). |
| `MLW_EXTRA_GIDS` | | Extra numeric group ids for the server user, comma separated. The groups owning `/dev/dri/*`, `/dev/nvidia*` and `/dev/dvb/*` are added automatically. |
| `MLW_CHOWN` | `auto` | `auto`: give `/config` and `/cache` to `PUID:PGID` when the folder belongs to someone else; `true`: always (recursive); `false`: never. `/media` is never changed. |
| `MLW_CONFIG_MODE` | `first-run` | `first-run` or `enforce` (see above). |
| `MLW_HEALTHCHECK_URL` | | URL checked by the container health check. Default: `http://127.0.0.1:<InternalHttpPort><BaseUrl>/health`. |

When the container is started with `--user uid:gid`, the entrypoint does not change users or ownership; the mounted
folders must then be writable by that user.

## Server (`system.xml`)

| Variable | Setting | Example |
|---|---|---|
| `MLW_SERVER_NAME` | `ServerName` | `Home media` |
| `MLW_UI_CULTURE` | `UICulture` (dashboard language) | `ro`, `en-US`, `de` |
| `MLW_METADATA_LANGUAGE` | `PreferredMetadataLanguage` | `ro`, `en` |
| `MLW_METADATA_COUNTRY` | `MetadataCountryCode` | `RO`, `US` |
| `MLW_METADATA_PATH` | `MetadataPath` | `/data/metadata` |
| `MLW_QUICKCONNECT` | `QuickConnectAvailable` | `true` / `false` |
| `MLW_ENABLE_METRICS` | `EnableMetrics` (Prometheus `/metrics`) | `true` / `false` |
| `MLW_CORS_HOSTS` | `CorsHosts` (list) | `https://app.example.org` |
| `MLW_ACTIVITY_LOG_RETENTION_DAYS` | `ActivityLogRetentionDays` | `30` |
| `MLW_LIBRARY_SCAN_CONCURRENCY` | `LibraryScanFanoutConcurrency` | `4` |
| `MLW_LIBRARY_REFRESH_CONCURRENCY` | `LibraryMetadataRefreshConcurrency` | `4` |
| `MLW_IMAGE_ENCODING_LIMIT` | `ParallelImageEncodingLimit` | `2` |
| `MLW_REMOTE_BITRATE_LIMIT` | `RemoteClientBitrateLimit` (bits/s, 0 = none) | `8000000` |
| `MLW_SLOW_RESPONSE_WARNING` | `EnableSlowResponseWarning` | `false` |

## Network (`network.xml`)

| Variable | Setting | Example |
|---|---|---|
| `MLW_PUBLISHED_URL` | the address given to clients (`JELLYFIN_PublishedServerUrl`, read by the server at start) | `https://media.example.org` |
| `MLW_BASE_URL` | `BaseUrl` (server under a sub-path) | `/media` |
| `MLW_HTTP_PORT` | `InternalHttpPort` (port inside the container; keep `8096` unless you know why) | `8096` |
| `MLW_HTTPS_PORT` | `InternalHttpsPort` | `8920` |
| `MLW_PUBLIC_HTTP_PORT` | `PublicHttpPort` | `80` |
| `MLW_PUBLIC_HTTPS_PORT` | `PublicHttpsPort` | `443` |
| `MLW_ENABLE_HTTPS` | `EnableHttps` (needs a certificate) | `true` |
| `MLW_REQUIRE_HTTPS` | `RequireHttps` | `true` |
| `MLW_CERT_PATH` | `CertificatePath` (PKCS#12 `.pfx` inside the container) | `/config/cert.pfx` |
| `MLW_CERT_PASSWORD` | `CertificatePassword` (stored by the server in `network.xml`; not logged) | |
| `MLW_REMOTE_ACCESS` | `EnableRemoteAccess` (connections from outside the local networks) | `true` / `false` |
| `MLW_KNOWN_PROXIES` | `KnownProxies` (list; your reverse proxy) | `172.16.0.0/12, 10.0.0.5` |
| `MLW_LOCAL_NETWORK_SUBNETS` | `LocalNetworkSubnets` (list) | `192.168.1.0/24` |
| `MLW_LOCAL_NETWORK_ADDRESSES` | `LocalNetworkAddresses` (list; bind addresses) | |
| `MLW_PUBLISHED_URI_BY_SUBNET` | `PublishedServerUriBySubnet` (list) | `192.168.1.0/24=http://192.168.1.10:8096` |
| `MLW_ENABLE_IPV4` / `MLW_ENABLE_IPV6` | `EnableIPv4` / `EnableIPv6` | `true` / `false` |
| `MLW_AUTO_DISCOVERY` | `AutoDiscovery` (UDP 7359) | `true` |
| `MLW_REMOTE_IP_FILTER` | `RemoteIPFilter` (list) | `203.0.113.0/24` |
| `MLW_REMOTE_IP_FILTER_MODE` | `IsRemoteIPFilterBlacklist` | `allow` (allow-list) / `block` (block-list) |

## Transcoding (`encoding.xml`)

| Variable | Setting | Example |
|---|---|---|
| `MLW_HW_ACCEL` | `HardwareAccelerationType` | `none`, `qsv` (Intel), `vaapi` (AMD / Intel), `nvenc` (NVIDIA), `amf`, `v4l2m2m`, `rkmpp` |
| `MLW_VAAPI_DEVICE` | `VaapiDevice` | `/dev/dri/renderD128` |
| `MLW_QSV_DEVICE` | `QsvDevice` | `/dev/dri/renderD128` |
| `MLW_HW_DECODING_CODECS` | `HardwareDecodingCodecs` (list) | `h264,hevc,vp9,av1` |
| `MLW_HW_ENCODING` | `EnableHardwareEncoding` | `true` |
| `MLW_TONEMAPPING` | `EnableTonemapping` (HDR to SDR) | `true` |
| `MLW_VPP_TONEMAPPING` | `EnableVppTonemapping` (Intel) | `true` |
| `MLW_TRANSCODE_PATH` | `TranscodingTempPath` | `/transcode` (e.g. a tmpfs) |
| `MLW_ENCODER_THREADS` | `EncodingThreadCount` (`-1` = auto) | `4` |
| `MLW_THROTTLING` | `EnableThrottling` | `true` |
| `MLW_SEGMENT_DELETION` | `EnableSegmentDeletion` | `true` |
| `MLW_FALLBACK_FONT_PATH` | `FallbackFontPath` (subtitle fonts) | `/config/fonts` |

## Any other setting

| Variable | Writes |
|---|---|
| `MLW_SYSTEM__<Property>` | `<Property>` in `system.xml` |
| `MLW_NETWORK__<Property>` | `<Property>` in `network.xml` |
| `MLW_ENCODING__<Property>` | `<Property>` in `encoding.xml` |
| `MLW_CONF__<file>__<Property>` | `<Property>` in `/config/config/<file>.xml` (the file must exist: the server creates most of them at the first start) |

Nested properties use more `__`, e.g. `MLW_SYSTEM__TrickplayOptions__EnableHwAcceleration=true`.
Property names are case-sensitive, exactly as in the XML file. A value starting with `[` is read as a JSON list; a
comma-separated value is written as a list when the existing element is a list. `IsStartupWizardCompleted` and
`PluginRepositories` cannot be set this way (see below).

## First administrator (new servers)

| Variable | Default | Description |
|---|---|---|
| `MLW_ADMIN_USER` | | Name of the first administrator. When set (with a password) on a server whose setup wizard has not been completed, the entrypoint creates this user and completes the wizard through the server's startup API, in the background, once the server answers. Ignored on a server that is already set up (users are managed in the dashboard). |
| `MLW_ADMIN_PASSWORD` | | Its password. Prefer `MLW_ADMIN_PASSWORD_FILE`. It is never logged and is removed from the server's environment. |
| `MLW_WIZARD_TIMEOUT` | `600` | Seconds to wait for the server before giving up. |

## Plugins

| Variable | Default | Description |
|---|---|---|
| `MLW_PLUGIN_REPOS` | `medialab,jellyfin` | Plugin repositories, comma separated: `medialab` (the public medialab.works catalog), `jellyfin` (Jellyfin's official repository), `Name=https://…/manifest.json`, a bare URL, or `none` (do not manage the list). In `first-run` mode missing repositories are added in front and the others are kept; in `enforce` mode the list is replaced. On a brand-new server the setup resets the list, so it is applied right after the wizard (when `MLW_ADMIN_*` is set) or at the next start. |
| `MLW_REPO_KEY` | | Your medialab.works repository key (`jfr_…`, from your account) or the full keyed URL. Adds the licensed catalog `https://medialab.works/api/jellyfin/<key>/manifest.json` first. Masked in the logs. |
| `MLW_CATALOG_URL` | `https://medialab.works/jellyfin/manifest.json` | The public catalog URL used for `medialab`. |
| `MLW_PLUGINS` | | Plugins to install before the server starts, comma separated: `jf-rosub,jf-registration@1.0.2`. A plugin is found by its medialab slug (`jf-rosub`, or just `rosub`), its name (`Rosub by MediaLab`) or its GUID. `@version` pins a version. Each archive is checked against the MD5 checksum of the manifest and unpacked into `/config/plugins/<Name>_<version>/` with its `meta.json`; a `.dll.sig` signature in the archive is kept, so the server can show it as "Verified – medialab". Already installed plugins are not downloaded again. |
| `MLW_PLUGINS_UPDATE` | `false` | `true`: install the newest compatible version of the unpinned plugins at each start (the older version is removed). |
| `MLW_PLUGINS_STRICT` | `false` | `true`: do not start the server when a plugin cannot be installed. |
| `MLW_PLUGIN_<SLUG>__<Property>` | | A value merged into the plugin's configuration file `/config/plugins/configurations/<Assembly>.xml`, e.g. `MLW_PLUGIN_ROSUB__ArchiveCacheDays=14`. `<SLUG>` is the plugin slug with or without `JF_` (`ROSUB`, `JF_ROSUB`), its name or its assembly name. The plugin must be installed (via `MLW_PLUGINS` or the dashboard). Follows `MLW_CONFIG_MODE`. Values of properties whose name contains `KEY`, `TOKEN`, `SECRET` or `PASSWORD` are not logged. |

Whole configuration files can also be mounted: `/config/plugins/configurations/<Assembly>.xml` (e.g. `Rosub.xml`).

## Licence keys

| Variable | Description |
|---|---|
| `MLW_LICENSE_KEY` | A medialab.works licence key, passed unchanged to the server process. |
| `MLW_LICENSE_KEY_<SLUG>` | The licence key of one plugin, e.g. `MLW_LICENSE_KEY_JF_ROSUB`. |
| `*_FILE`, `/run/secrets/mlw_license_key[_<slug>]` | The same from files: a Docker secret named `mlw_license_key` or `mlw_license_key_jf_rosub` becomes `MLW_LICENSE_KEY` / `MLW_LICENSE_KEY_JF_ROSUB`. |

The keys are never logged. Plugins read them from the environment **from the plugin versions that support it**;
until then, enter the key in the plugin's page in the dashboard (it is kept in `/config`).

## Set by the image (change only if you know why)

| Variable | Value |
|---|---|
| `JELLYFIN_DATA_DIR` | `/config` |
| `JELLYFIN_CONFIG_DIR` | `/config/config` |
| `JELLYFIN_LOG_DIR` | `/config/log` |
| `JELLYFIN_CACHE_DIR` | `/cache` |
| `JELLYFIN_WEB_DIR` | `/usr/share/jellyfin/web` |
| `JELLYFIN_FFMPEG` | `/usr/lib/jellyfin-ffmpeg/ffmpeg` |
| `NVIDIA_VISIBLE_DEVICES`, `NVIDIA_DRIVER_CAPABILITIES` | `all`, `compute,video,utility` |
| `MLW_CONTAINER` | `docker` (lets plugins know they run in a container) |

The server also reads any `JELLYFIN_<Key>` variable as a startup option (.NET configuration), e.g.
`JELLYFIN_PublishedServerUrl`. Note that the server logs the values of all `JELLYFIN_*` variables at start: do not put
secrets in them.
