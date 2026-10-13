# Install medialab Server from the apt repository (Debian/Ubuntu)

medialab Server is distributed as signed Debian packages from `https://apt.medialab.works/debian`:

| Package | Content |
|---|---|
| `medialab-server` | the server (based on Jellyfin 12.2), the `jellyfin` system service and the in-app updater |
| `medialab-server-web` | the web interface |
| `jellyfin-ffmpeg8` | Jellyfin's FFmpeg build used for transcoding |
| `medialab-repo` | the repository definition and its signing key |

Architectures: `amd64` and `arm64`.

## Supported systems

The packages are built for **Debian 12 (bookworm)** (`+deb12` in the version) and its derivatives based on bookworm,
such as Raspberry Pi OS (64-bit) bookworm. They depend on Debian 12 libraries (for example `libicu72`), so they do not
install on Ubuntu releases or other Debian releases. On Ubuntu, use the container image instead
(see "Install medialab Server in a container").

## 1. Add the repository

The `medialab-repo` package installs the repository definition and the signing key:

```sh
curl -fsSLO https://apt.medialab.works/medialab-repo.deb
sudo apt install ./medialab-repo.deb
```

It creates `/etc/apt/sources.list.d/medialab.sources`:

```
Types: deb
URIs: https://apt.medialab.works/debian
Suites: stable
Components: main
Signed-By: /usr/share/keyrings/medialab-archive-keyring.gpg
```

**Manual alternative.** Download the key and create the same file yourself:

```sh
sudo curl -fsSL https://apt.medialab.works/debian/medialab-archive-keyring.gpg \
  -o /usr/share/keyrings/medialab-archive-keyring.gpg
gpg --show-keys /usr/share/keyrings/medialab-archive-keyring.gpg
```

The key fingerprint must be `6B7D 46D8 2C3C 4D4C 0A14  2F92 4189 96EB 3CE1 59C7`
("medialab Server packages <packages@medialab.works>"). Then write the `medialab.sources` file shown above.

apt checks the repository signature with this key on every `apt update`.

## 2. Install

```sh
sudo apt update
sudo apt install medialab-server medialab-server-web jellyfin-ffmpeg8
```

`medialab-server` replaces `jellyfin-server` and `medialab-server-web` replaces `jellyfin-web`: if Jellyfin is already
installed from Jellyfin's repository, apt removes those two packages and keeps your data, because medialab Server uses
the same folders. At the first start the database is upgraded to the 12.2 format, which an older Jellyfin cannot
open again: make a backup first (see below). If Jellyfin's repository is still configured, apt keeps the medialab
packages installed; you can remove Jellyfin's repository if you no longer need it.

## 3. The service

The server runs as the `jellyfin` system service, under the `jellyfin` user:

```sh
sudo systemctl status jellyfin
sudo systemctl restart jellyfin
sudo journalctl -u jellyfin -f
```

Open `http://<server>:8096` and complete the setup wizard.

| Path | Content |
|---|---|
| `/etc/jellyfin` | settings (`system.xml`, `network.xml`, `encoding.xml`, `logging.json`) |
| `/var/lib/jellyfin` | database, plugins, metadata |
| `/var/log/jellyfin` | logs |
| `/var/cache/jellyfin` | cache |
| `/etc/default/jellyfin` | start-up options (web folder, FFmpeg path, extra options) |
| `/usr/share/jellyfin/web` | web interface |
| `/usr/lib/jellyfin-ffmpeg/ffmpeg` | FFmpeg |

To change the service user or other systemd options, use `sudo systemctl edit jellyfin` (or the file
`/etc/systemd/system/jellyfin.service.d/jellyfin.service.conf`).

For hardware transcoding with an Intel or AMD GPU, the package adds the `jellyfin` user to the `render` and `video`
groups; choose the method in Dashboard → Playback → Transcoding. For NVIDIA, install the NVIDIA driver from your
distribution first.

## 4. Updates

```sh
sudo apt update
sudo apt upgrade
```

The package stops the service during the upgrade and starts it again on the new version. The package also contains an updater service (`medialab-update.path` /
`medialab-update.service`) used by the "Self-Update by MediaLab" plugin to update the server from the web interface;
it installs the packages from this same repository.

To stay on one version: `sudo apt-mark hold medialab-server medialab-server-web`
(`sudo apt-mark unhold …` to undo).

## Backup

Stop the service and copy the settings and data folders:

```sh
sudo systemctl stop jellyfin
sudo tar -czf medialab-backup-$(date +%F).tar.gz /etc/jellyfin /var/lib/jellyfin
sudo systemctl start jellyfin
```

## Uninstall

```sh
sudo apt remove medialab-server medialab-server-web     # keeps settings, data and logs
sudo apt remove medialab-repo                            # removes the repository
```

`sudo apt purge medialab-server` also **deletes** `/etc/jellyfin`, `/var/lib/jellyfin` (database, plugins, metadata),
`/var/log/jellyfin`, `/var/cache/jellyfin` and the `jellyfin` user. Make a backup before purging.

## Troubleshooting

- **`apt update` reports a signature error (NO_PUBKEY / EXPKEYSIG):** reinstall `medialab-repo` (step 1) to get the
  current key.
- **Unmet dependencies such as `libicu72`:** the system is not Debian 12; use the container image.
- **The service does not start:** `sudo journalctl -u jellyfin -n 100` and the files in `/var/log/jellyfin` show the
  reason. Check that the `jellyfin` user can read your media folders.
- **Port 8096 already in use:** another Jellyfin or media server is running; stop it, or change the port in Dashboard →
  Networking.
