# Instalarea medialab Server într-un container

medialab Server e publicat ca imagine de container pentru `linux/amd64` și `linux/arm64`:

```
ghcr.io/cristiancasapu/medialab-server
```

Imaginea e construită din aceleași pachete Debian semnate ca depozitul apt (`medialab-server`,
`medialab-server-web`, `jellyfin-ffmpeg8`); fișierele de construire sunt publice la
[github.com/CristianCasapu/medialab-server-docker](https://github.com/CristianCasapu/medialab-server-docker) (GPL-2.0).

Etichete:

| Etichetă | Înseamnă |
|---|---|
| `12.2-ml.5` | o versiune anume; recomandată când vrei să alegi tu momentul actualizării |
| `12.2` | cea mai nouă versiune bazată pe Jellyfin 12.2 |
| `latest` | cea mai nouă versiune |
| `12.2-ml5-deb12` | versiunea apt exactă din imagine |

## De ce ai nevoie

- Docker (sau Podman, Unraid, Portainer, Kubernetes) pe un calculator x86 sau ARM pe 64 de biți.
- Un dosar pentru setări (`/config`), unul pentru cache (`/cache`) și dosarul cu fișierele media (`/media`).
- Utilizatorul și grupul numerice care trebuie să dețină setările: `id -u` și `id -g` ale contului respectiv
  (`PUID`, `PGID`).

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

Deschide `http://<server>:8096`. Pe un server nou, asistentul de configurare cere primul administrator, limba și
bibliotecile (le adaugi din `/media`).

Ca să sari peste asistent, lasă containerul să creeze administratorul. Pune parola într-un fișier, nu în linia de
comandă:

```sh
printf '%s' 'o-parola-lunga' > /srv/medialab/admin_password
docker run -d ... \
  -v /srv/medialab/admin_password:/run/secrets/admin_password:ro \
  -e MLW_ADMIN_USER=admin \
  -e MLW_ADMIN_PASSWORD_FILE=/run/secrets/admin_password \
  ghcr.io/cristiancasapu/medialab-server:latest
```

Merge doar pe un server nou; pe un server deja configurat variabilele sunt ignorate. Parola nu apare niciodată în
jurnalele containerului.

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
      MLW_SERVER_NAME: Media acasă
      MLW_ADMIN_USER: admin
      MLW_ADMIN_PASSWORD_FILE: /run/secrets/admin_password
    secrets:
      - admin_password

secrets:
  admin_password:
    file: ./secrets/admin_password
```

```sh
mkdir -p secrets && printf '%s' 'o-parola-lunga' > secrets/admin_password
docker compose up -d
docker compose logs -f
```

Un exemplu complet, cu fișier `.env`, e în depozit (`examples/compose.yaml`, `examples/.env.example`).

## Unraid

1. În fila Docker alegi **Add Container** și pui la **Template** adresa
   `https://raw.githubusercontent.com/CristianCasapu/medialab-server-docker/main/examples/unraid/medialab-server.xml`
   (sau copiezi fișierul în `/boot/config/plugins/dockerMan/templates-user/`).
2. Verifici căile: `/config` → `/mnt/user/appdata/medialab-server`, `/media` → share-ul cu fișierele media.
3. `PUID` 99 și `PGID` 100 sunt valorile obișnuite pe Unraid (nobody / users).
4. Placă Intel sau AMD: adaugi `--device=/dev/dri` la **Extra Parameters** și alegi la **Hardware acceleration**
   `qsv` sau `vaapi`. NVIDIA: instalezi plugin-ul Nvidia-Driver, adaugi `--runtime=nvidia` și alegi `nvenc`.
5. Apply, apoi deschizi WebUI.

## Portainer

1. **Stacks → Add stack → Web editor** și lipești `examples/portainer/stack.yml` din depozit.
2. La **Environment variables** încarci `examples/portainer/stack.env` (sau adaugi variabilele de mână) și ajustezi
   căile, `PUID`, `PGID` și `TZ`.
3. **Deploy the stack.**

Stivele Portainer nu pot folosi secrete Docker pe o gazdă simplă (fără Swarm), așa că exemplul dă
`MLW_ADMIN_PASSWORD` ca variabilă a stivei. E folosită o singură dată; o poți șterge după prima pornire.

## Kubernetes

`examples/kubernetes/medialab-server.yaml` conține un ConfigMap, două PersistentVolumeClaim, un Deployment (o
replică, strategia `Recreate`, verificări pe `/health`), un Service și un Ingress:

```sh
kubectl create namespace medialab
kubectl -n medialab create secret generic medialab-secrets \
  --from-literal=admin-password='o-parola-lunga' --from-literal=license-key='' --from-literal=repo-key=''
kubectl -n medialab apply -f medialab-server.yaml
```

Ajustează mai întâi dimensiunile volumelor, volumul media (e inclus un exemplu NFS) și numele gazdei. Rulează o
singură replică: serverul își ține baza de date în `/config`.

## Accelerare hardware

**Intel (QSV / VAAPI) și AMD (VAAPI)**

```sh
docker run ... --device /dev/dri:/dev/dri -e MLW_HW_ACCEL=qsv ...     # Intel
docker run ... --device /dev/dri:/dev/dri -e MLW_HW_ACCEL=vaapi ...   # AMD sau Intel mai vechi
```

Containerul adaugă singur utilizatorul serverului în grupurile care dețin `/dev/dri/*`, deci nu trebuie să cauți
numerele grupurilor `render` și `video`. Driverele vin cu `jellyfin-ffmpeg8`; imaginea amd64 conține și runtime-ul
OpenCL Intel din Debian 12, pentru maparea tonurilor HDR (plăcile Intel foarte noi pot avea nevoie de un runtime mai nou
decât cel din Debian 12).

**NVIDIA (NVENC / NVDEC)**

Instalează pe gazdă driverul NVIDIA și NVIDIA Container Toolkit, apoi:

```sh
docker run ... --gpus all -e MLW_HW_ACCEL=nvenc ...
```

Cu Compose adaugi `examples/compose.nvidia.yaml`; în Kubernetes ceri `nvidia.com/gpu: 1`.

După prima pornire verifică Panou → Redare → Transcodare și redă un video care are nevoie de transcodare; jurnalul
ffmpeg din `/config/log` arată dacă s-a folosit placa grafică.

## Plugin-uri, setări și licențe din exterior

Tot ce urmează e opțional; lista completă a variabilelor e în `docs/ENVIRONMENT.ro.md` din depozit.

**Setările serverului.** De exemplu:

```sh
-e MLW_PUBLISHED_URL=https://media.example.org \
-e MLW_KNOWN_PROXIES=172.16.0.0/12 \
-e MLW_UI_CULTURE=ro -e MLW_METADATA_COUNTRY=RO \
-e MLW_REMOTE_ACCESS=true
```

Sunt scrise în `system.xml`, `network.xml` și `encoding.xml` înainte de pornirea serverului. Cu modul implicit
`MLW_CONFIG_MODE=first-run`, o valoare e scrisă pe un server nou și apoi doar când modifici variabila, așa că ce schimbi
ulterior în panou se păstrează. `MLW_CONFIG_MODE=enforce` le scrie la fiecare pornire. Orice altă proprietate se poate
seta cu `MLW_SYSTEM__<Proprietate>`, `MLW_NETWORK__<Proprietate>` și `MLW_ENCODING__<Proprietate>`.

**Catalogul de plugin-uri.** Catalogul public medialab.works și depozitul oficial Jellyfin sunt adăugate implicit
(`MLW_PLUGIN_REPOS=medialab,jellyfin`). Dacă ai în cont o cheie de depozit, o adaugi cu `MLW_REPO_KEY` (sau
`MLW_REPO_KEY_FILE`); în jurnale apare mascată.

**Plugin-uri.** Le enumeri în `MLW_PLUGINS`; sunt instalate înainte de pornirea serverului:

```sh
-e MLW_PLUGINS="jf-rosub,jf-registration@1.0.2"
```

Un plugin e găsit după slug (`jf-rosub`), după nume sau după GUID; `@versiune` fixează o versiune. Arhiva e verificată
cu suma de control din catalog, iar semnătura medialab (`.dll.sig`) se păstrează, ca panoul să arate plugin-ul ca
verificat. Plugin-urile deja instalate nu se descarcă din nou; `MLW_PLUGINS_UPDATE=true` instalează versiunile mai noi
la pornire.

**Setările plugin-urilor.** Fie montezi fișierul de configurare al plugin-ului
(`/config/plugins/configurations/<Assembly>.xml`, de ex. `Rosub.xml`), fie setezi valori una câte una:

```sh
-e MLW_PLUGIN_ROSUB__ArchiveCacheDays=14
```

**Chei de licență.** `MLW_LICENSE_KEY`, `MLW_LICENSE_KEY_<SLUG>` (de ex. `MLW_LICENSE_KEY_JF_ROSUB`), formele lor `_FILE`
și secretele Docker numite `mlw_license_key` sau `mlw_license_key_<slug>` ajung neschimbate în mediul procesului server.
Plugin-urile le citesc de acolo în versiunile care suportă asta; cu o versiune mai veche de plugin, introdu cheia în
pagina plugin-ului din panou (se salvează în `/config`).

Orice variabilă acceptă și forma `<NUME>_FILE=/cale/fișier`, pentru secretele Docker și Kubernetes.

## Actualizări

Descarci imaginea nouă și recreezi containerul; setările din `/config` rămân:

```sh
docker pull ghcr.io/cristiancasapu/medialab-server:12.2-ml.6
docker stop medialab-server && docker rm medialab-server
docker run -d ... ghcr.io/cristiancasapu/medialab-server:12.2-ml.6     # aceleași opțiuni ca înainte
```

Cu Compose: schimbi eticheta în `compose.yaml` (sau păstrezi `latest`), apoi `docker compose pull && docker compose up -d`.
Pe Unraid: **Check for Updates** în fila Docker. În Portainer: **Recreate** cu **Re-pull image**.

Actualizatorul din interfață al pachetului Debian nu face parte din imagine. „Self-Update by MediaLab” arată versiunile
disponibile într-un container, dar nu instalează pachete; actualizezi descărcând noua etichetă a imaginii (`12.2-ml.N`)
și recreând containerul.

## Copie de siguranță

`/config` conține tot ce contează (setări, utilizatori, baza de date, plugin-uri, metadate). Oprește containerul și
copiază-l:

```sh
docker stop medialab-server
tar -C /srv/medialab -czf medialab-config-$(date +%F).tar.gz config
docker start medialab-server
```

`/cache` se poate reface și nu are nevoie de copie. Pentru restaurare pui `config` la loc și pornești aceeași etichetă a
imaginii sau una mai nouă.

## Probleme frecvente

- **Ce a făcut containerul:** `docker logs medialab-server`. Liniile care încep cu `[medialab]` vin de la scriptul de
  pornire al containerului (setări scrise, plugin-uri instalate, administrator creat).
- **Containerul se oprește imediat cu `[medialab] ERROR`:** o variabilă are o valoare greșită; mesajul o numește.
- **„Permission denied”:** `PUID`/`PGID` nu se potrivesc cu proprietarul dosarelor. Containerul corectează singur
  `/config` și `/cache`, niciodată `/media`. Pornit cu `--user`, nu schimbă nimic: dosarele trebuie să aparțină deja
  acelui utilizator.
- **O setare din mediu nu se aplică:** în modul `first-run`, o valoare e scrisă pe un server nou sau când se schimbă.
  Folosește `MLW_CONFIG_MODE=enforce` ca s-o impui.
- **Un plugin nu s-a instalat:** jurnalul spune de ce (catalog indisponibil, nume negăsit, sumă de control greșită, nicio
  versiune pentru acest server). Serverul pornește oricum, în afară de cazul `MLW_PLUGINS_STRICT=true`.
- **Containerul apare „unhealthy”:** verificarea apelează `/health` pe portul 8096 (sau pe portul și subcalea din
  `network.xml`). Prima pornire poate dura un minut sau două.
- **În spatele unui proxy invers, aplicațiile primesc adresa greșită:** pune în `MLW_KNOWN_PROXIES` adresa proxy-ului și
  în `MLW_PUBLISHED_URL` adresa publică.
