# medialab Server – imagine de container

[English](README.md)

Imaginea de container a **medialab Server**, o ramificație GPL-2.0 a [Jellyfin](https://jellyfin.org) 12.2
([server](https://github.com/CristianCasapu/medialab-server), [web](https://github.com/CristianCasapu/medialab-server-web)),
construită din pachetele Debian semnate ale depozitului apt medialab (`https://apt.medialab.works/debian`).
În acest depozit nu se compilează nimic: imaginea instalează `medialab-server`, `medialab-server-web` și
`jellyfin-ffmpeg8` din depozit, prin HTTPS; apt verifică semnătura depozitului, iar cheia de semnare e fixată după
amprentă.

```
ghcr.io/cristiancasapu/medialab-server:latest          # cea mai nouă versiune
ghcr.io/cristiancasapu/medialab-server:12.2            # cea mai nouă versiune 12.2
ghcr.io/cristiancasapu/medialab-server:12.2-ml.5       # o versiune anume (recomandat în producție)
ghcr.io/cristiancasapu/medialab-server:12.2-ml5-deb12  # versiunea apt exactă
```

Arhitecturi: `linux/amd64`, `linux/arm64`.

Scopul principal al imaginii: **totul se poate configura din exterior**. Setările serverului, primul administrator,
depozitele de plugin-uri, plugin-urile, setările lor și cheile de licență vin din variabile de mediu (sau din fișiere /
secrete), așa că un server poate fi recreat dintr-un fișier Compose sau dintr-un manifest Kubernetes.

## Pornire rapidă

```sh
docker run -d --name medialab-server --restart unless-stopped \
  -p 8096:8096 \
  -v /srv/medialab/config:/config -v /srv/medialab/cache:/cache -v /srv/media:/media:ro \
  -e PUID=1000 -e PGID=1000 -e TZ=Europe/Bucharest \
  ghcr.io/cristiancasapu/medialab-server:latest
```

Deschide `http://<gazdă>:8096` și urmează asistentul de configurare sau lasă containerul să creeze administratorul:

```sh
printf '%s' 'o-parola-lunga' > /srv/medialab/admin_password
docker run ... \
  -v /srv/medialab/admin_password:/run/secrets/admin_password:ro \
  -e MLW_ADMIN_USER=admin -e MLW_ADMIN_PASSWORD_FILE=/run/secrets/admin_password \
  ghcr.io/cristiancasapu/medialab-server:latest
```

Alte exemple în [`examples/`](examples):
[`docker-run.sh`](examples/docker-run.sh),
[`compose.yaml`](examples/compose.yaml) + [`.env.example`](examples/.env.example),
[`compose.intel.yaml`](examples/compose.intel.yaml), [`compose.nvidia.yaml`](examples/compose.nvidia.yaml),
[șablon Unraid](examples/unraid/medialab-server.xml), [stivă Portainer](examples/portainer/stack.yml),
[Kubernetes](examples/kubernetes/medialab-server.yaml).

## Volume și porturi

| Cale | Conținut |
|---|---|
| `/config` | setări (`/config/config/*.xml`), baza de date, plugin-uri (`/config/plugins`), jurnale (`/config/log`), metadate. **Fă-i copie de siguranță.** |
| `/cache` | cache de imagini și fișiere de transcodare; se poate pierde. |
| `/media` | fișierele tale media (montează-le doar pentru citire dacă serverul nu trebuie să scrie acolo). |
| `/data` | punct de montare suplimentar, opțional (de exemplu o a doua bibliotecă). |

| Port | Folosire |
|---|---|
| `8096/tcp` | HTTP: interfața web, aplicațiile, API-ul |
| `8920/tcp` | HTTPS, doar dacă e activat cu un certificat (`MLW_ENABLE_HTTPS`) |
| `7359/udp` | descoperirea automată de către aplicații în rețeaua locală (opțional) |
| `1900/udp` | DLNA / SSDP, pentru plugin-urile care îl folosesc (opțional) |

## Configurarea din variabile de mediu

Lista completă: **[docs/ENVIRONMENT.ro.md](docs/ENVIRONMENT.ro.md)**. Pe scurt:

- **Container:** `PUID`, `PGID`, `UMASK`, `TZ`, `MLW_EXTRA_GIDS`, `MLW_CHOWN`.
- **Setările serverului** (scrise în `system.xml`, `network.xml`, `encoding.xml` înainte de pornirea serverului):
  `MLW_SERVER_NAME`, `MLW_UI_CULTURE`, `MLW_METADATA_LANGUAGE`, `MLW_METADATA_COUNTRY`, `MLW_PUBLISHED_URL`,
  `MLW_BASE_URL`, `MLW_KNOWN_PROXIES`, `MLW_REMOTE_ACCESS`, `MLW_HTTPS_PORT`, `MLW_PUBLIC_HTTPS_PORT`,
  `MLW_HW_ACCEL` … și orice altă proprietate prin `MLW_SYSTEM__<Proprietate>`, `MLW_NETWORK__<Proprietate>`,
  `MLW_ENCODING__<Proprietate>`, `MLW_CONF__<fișier>__<Proprietate>`.
- **Când sunt scrise:** `MLW_CONFIG_MODE=first-run` (implicit) scrie o valoare pe un server nou și apoi doar când
  modifici variabila, deci schimbările făcute în panou se păstrează; `MLW_CONFIG_MODE=enforce` le scrie la fiecare
  pornire.
- **Primul administrator:** `MLW_ADMIN_USER` + `MLW_ADMIN_PASSWORD` / `MLW_ADMIN_PASSWORD_FILE` creează administratorul
  și încheie asistentul de configurare prin API-ul de pornire al serverului (doar pe servere noi).
- **Plugin-uri:** `MLW_PLUGIN_REPOS` (implicit `medialab,jellyfin`), `MLW_REPO_KEY` (catalogul tău medialab.works cu
  cheie), `MLW_PLUGINS="jf-rosub,jf-registration@1.0.2"` (instalate înainte de pornirea serverului, cu verificarea
  sumei MD5 și păstrarea semnăturilor medialab), `MLW_PLUGINS_UPDATE=true` și setările plugin-urilor ca
  `MLW_PLUGIN_<SLUG>__<Proprietate>=valoare` (sau montezi `/config/plugins/configurations/<Assembly>.xml`).
- **Chei de licență:** `MLW_LICENSE_KEY`, `MLW_LICENSE_KEY_<SLUG>`, formele lor `_FILE` și secretele Docker
  `mlw_license_key[_<slug>]` ajung neschimbate în mediul procesului server, pentru versiunile de plugin care le citesc
  de acolo (disponibil de la versiunile de plugin care suportă asta; până atunci, introdu cheia în pagina plugin-ului).
- **Secrete:** orice variabilă acceptă și forma `<NUME>_FILE=/cale`. Parolele și cheile nu apar niciodată în jurnale;
  parola administratorului și cheia depozitului sunt scoase din mediul serverului.

## Accelerare hardware

**Intel (QSV / VAAPI) și AMD (VAAPI):** dai containerului placa grafică și alegi metoda. Entrypoint-ul adaugă
utilizatorul serverului în grupurile care dețin `/dev/dri/*`, oricare ar fi numerele lor pe gazdă.

```sh
docker run ... --device /dev/dri:/dev/dri -e MLW_HW_ACCEL=qsv ...     # Intel
docker run ... --device /dev/dri:/dev/dri -e MLW_HW_ACCEL=vaapi ...   # AMD, Intel mai vechi
```

Imaginea amd64 conține runtime-ul OpenCL Intel din Debian 12 (`intel-opencl-icd`, folosit la maparea tonurilor HDR);
pachetul `jellyfin-ffmpeg8` vine cu propriile drivere VAAPI / QSV (iHD, i965, radeonsi).

**NVIDIA (NVENC / NVDEC):** instalează pe gazdă driverul NVIDIA și
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/), apoi:

```sh
docker run ... --gpus all -e MLW_HW_ACCEL=nvenc ...
```

(`--runtime=nvidia` pe Unraid; `compose.nvidia.yaml` pentru Compose; resursa `nvidia.com/gpu` în Kubernetes.)
`NVIDIA_VISIBLE_DEVICES=all` și `NVIDIA_DRIVER_CAPABILITIES=compute,video,utility` sunt deja setate în imagine.

Verifică rezultatul în Panou → Redare → Transcodare și în jurnalele de transcodare din `/config/log`.

## Actualizări

Actualizezi descărcând imaginea nouă și recreând containerul; `/config` rămâne:

```sh
docker pull ghcr.io/cristiancasapu/medialab-server:12.2-ml.6
docker stop medialab-server && docker rm medialab-server
docker run ... ghcr.io/cristiancasapu/medialab-server:12.2-ml.6     # aceleași opțiuni ca înainte
# Compose: schimbi eticheta (sau păstrezi „latest”), apoi: docker compose pull && docker compose up -d
```

Actualizatorul din interfață al pachetului Debian (un serviciu de sistem care rulează ca root) **nu** e inclus în
imagine. Plugin-ul „Self-Update by MediaLab” detectează asta și doar afișează versiunile disponibile; într-un container
nu instalează pachete. Plugin-urile se actualizează din panou, ca de obicei, sau cu `MLW_PLUGINS_UPDATE=true`.

O imagine nouă se construiește automat când apare o versiune nouă `medialab-server` în depozitul apt, și în fiecare luni
(actualizările de securitate Debian). Fixează o etichetă de versiune (`12.2-ml.5`) dacă vrei să decizi tu când actualizezi.

## Copie de siguranță

Oprește containerul (sau măcar asigură-te că nu rulează o scanare) și copiază `/config`:

```sh
docker stop medialab-server
tar -C /srv/medialab -czf medialab-config-$(date +%F).tar.gz config
docker start medialab-server
```

`/cache` nu are nevoie de copie. Pentru restaurare, pui dosarul la loc și pornești aceeași imagine (sau una mai nouă).

## Construirea imaginii

```sh
docker buildx build --platform linux/amd64,linux/arm64 \
  --build-arg MLW_VERSION=12.2+ml5+deb12 -t medialab-server:12.2-ml.5 .
```

| Argument | Implicit | Descriere |
|---|---|---|
| `MLW_VERSION` | vezi [`MLW_VERSION`](MLW_VERSION) | versiunea apt a `medialab-server` / `medialab-server-web` (`latest` = cea mai nouă) |
| `FFMPEG_VERSION` | `latest` | versiunea apt a `jellyfin-ffmpeg8` |
| `MLW_APT_URL` | `https://apt.medialab.works/debian` | depozitul apt |
| `MLW_KEY_FPR` | `6B7D46D82C3C4D4C0A142F92418996EB3CE159C7` | amprenta așteptată a cheii de semnare |
| `INTEL_OPENCL` | `true` | instalează `intel-opencl-icd` pe amd64 |
| `DEBIAN_TAG` | `bookworm-slim` | eticheta imaginii de bază |

Fluxul GitHub [`build.yml`](.github/workflows/build.yml) construiește ambele arhitecturi cu Buildx și le publică în
GHCR cu etichete OCI, SBOM și proveniența build-ului; [`check-apt.yml`](.github/workflows/check-apt.yml) verifică
zilnic depozitul apt.

## Probleme frecvente

- **Containerul se oprește imediat cu `[medialab] ERROR: …`:** o variabilă are o valoare greșită (de exemplu o valoare
  booleană care nu e `true`/`false`); mesajul o numește.
- **Acces refuzat la `/config` sau `/media`:** verifică `PUID`/`PGID` (`id -u`, `id -g` ale proprietarului fișierelor);
  containerul nu modifică niciodată `/media`. Cu `--user`, dosarele montate trebuie să aparțină deja acelui utilizator.
- **Setările din mediu par să nu se aplice:** în modul `first-run` o valoare se scrie doar pe un server nou sau când o
  modifici; folosește `MLW_CONFIG_MODE=enforce` ca s-o impui și caută liniile `[medialab] … = …` în `docker logs`.
- **Plugin neinstalat:** `docker logs` spune de ce (depozit indisponibil, nume negăsit, sumă de control greșită, nicio
  versiune compatibilă cu serverul). Serverul pornește oricum, în afară de cazul `MLW_PLUGINS_STRICT=true`.
- **Transcodarea hardware nu merge:** verifică dacă dispozitivul există în container
  (`docker exec medialab-server ls -l /dev/dri`), dacă `MLW_HW_ACCEL` se potrivește cu placa și jurnalul ffmpeg din
  `/config/log`.
- **În spatele unui proxy invers:** pune în `MLW_KNOWN_PROXIES` adresa (sau subrețeaua) proxy-ului, în
  `MLW_PUBLISHED_URL` adresa publică și, pentru o subcale, `MLW_BASE_URL`.

## Licență

GPL-2.0 (vezi [LICENSE](LICENSE)), ca Jellyfin și medialab Server. Imaginea conține pachete Debian cu licențele lor
(vezi `/usr/share/doc/*/copyright` în imagine). Jellyfin este o marcă a proiectului Jellyfin; medialab Server este o
ramificație independentă și nu este susținută de proiectul Jellyfin.
