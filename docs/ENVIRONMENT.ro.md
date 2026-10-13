# Variabile de mediu

[English](ENVIRONMENT.md)

Orice variabilă de mai jos poate fi dată și ca `<NUME>_FILE=/cale/fișier`: entrypoint-ul citește fișierul (fără
liniile noi de la final) și setează `<NUME>`. Folosește-o pentru secretele Docker / Compose / Kubernetes. Dacă sunt
setate amândouă, câștigă `<NUME>`.

O valoare goală înseamnă „nesetat”: setarea rămâne în grija panoului.

## Cum se scriu setările (`MLW_CONFIG_MODE`)

Entrypoint-ul scrie setările serverului în fișierele XML din `/config/config` **înainte** de pornirea serverului.

| Mod | Când se scrie o valoare |
|---|---|
| `first-run` (implicit) | când fișierul nu există încă (server nou) și apoi doar când **modifici** valoarea variabilei. Schimbările făcute ulterior în panou se păstrează până modifici variabila. |
| `enforce` | la fiecare pornire. Ce s-a schimbat în panou e suprascris de variabile la următoarea pornire. |

Entrypoint-ul ține minte ce valori a aplicat (doar amprente, niciodată valorile) în `/config/.medialab-docker/state.json`.
Ștergerea unei variabile nu resetează setarea: doar nu mai e administrată din mediu.

## Container

| Variabilă | Implicit | Descriere |
|---|---|---|
| `PUID` | `1000` | Utilizatorul (id) cu care rulează serverul. Fișierele din `/config` și `/cache` îi aparțin. |
| `PGID` | `1000` | Grupul (id) cu care rulează serverul. |
| `UMASK` | `022` | Masca la crearea fișierelor (`002` = fișiere scriibile de grup). |
| `TZ` | `Etc/UTC` | Fusul orar, de ex. `Europe/Bucharest` (sarcini programate, jurnale). |
| `MLW_EXTRA_GIDS` | | Grupuri suplimentare (id-uri numerice) pentru utilizatorul serverului, separate prin virgulă. Grupurile care dețin `/dev/dri/*`, `/dev/nvidia*` și `/dev/dvb/*` se adaugă automat. |
| `MLW_CHOWN` | `auto` | `auto`: dă `/config` și `/cache` lui `PUID:PGID` când dosarul aparține altcuiva; `true`: mereu (recursiv); `false`: niciodată. `/media` nu se modifică niciodată. |
| `MLW_CONFIG_MODE` | `first-run` | `first-run` sau `enforce` (vezi mai sus). |
| `MLW_HEALTHCHECK_URL` | | Adresa verificată de controlul de sănătate. Implicit: `http://127.0.0.1:<InternalHttpPort><BaseUrl>/health`. |

Când containerul pornește cu `--user uid:gid`, entrypoint-ul nu schimbă utilizatori sau proprietari; dosarele montate
trebuie să fie scriibile de acel utilizator.

## Server (`system.xml`)

| Variabilă | Setare | Exemplu |
|---|---|---|
| `MLW_SERVER_NAME` | `ServerName` | `Media acasă` |
| `MLW_UI_CULTURE` | `UICulture` (limba panoului) | `ro`, `en-US` |
| `MLW_METADATA_LANGUAGE` | `PreferredMetadataLanguage` | `ro`, `en` |
| `MLW_METADATA_COUNTRY` | `MetadataCountryCode` | `RO`, `US` |
| `MLW_METADATA_PATH` | `MetadataPath` | `/data/metadata` |
| `MLW_QUICKCONNECT` | `QuickConnectAvailable` | `true` / `false` |
| `MLW_ENABLE_METRICS` | `EnableMetrics` (Prometheus `/metrics`) | `true` / `false` |
| `MLW_CORS_HOSTS` | `CorsHosts` (listă) | `https://app.example.org` |
| `MLW_ACTIVITY_LOG_RETENTION_DAYS` | `ActivityLogRetentionDays` | `30` |
| `MLW_LIBRARY_SCAN_CONCURRENCY` | `LibraryScanFanoutConcurrency` | `4` |
| `MLW_LIBRARY_REFRESH_CONCURRENCY` | `LibraryMetadataRefreshConcurrency` | `4` |
| `MLW_IMAGE_ENCODING_LIMIT` | `ParallelImageEncodingLimit` | `2` |
| `MLW_REMOTE_BITRATE_LIMIT` | `RemoteClientBitrateLimit` (biți/s, 0 = fără limită) | `8000000` |
| `MLW_SLOW_RESPONSE_WARNING` | `EnableSlowResponseWarning` | `false` |

## Rețea (`network.xml`)

| Variabilă | Setare | Exemplu |
|---|---|---|
| `MLW_PUBLISHED_URL` | adresa comunicată aplicațiilor (`JELLYFIN_PublishedServerUrl`, citită de server la pornire) | `https://media.example.org` |
| `MLW_BASE_URL` | `BaseUrl` (server sub o subcale) | `/media` |
| `MLW_HTTP_PORT` | `InternalHttpPort` (portul din container; păstrează `8096` dacă nu ai un motiv) | `8096` |
| `MLW_HTTPS_PORT` | `InternalHttpsPort` | `8920` |
| `MLW_PUBLIC_HTTP_PORT` | `PublicHttpPort` | `80` |
| `MLW_PUBLIC_HTTPS_PORT` | `PublicHttpsPort` | `443` |
| `MLW_ENABLE_HTTPS` | `EnableHttps` (are nevoie de certificat) | `true` |
| `MLW_REQUIRE_HTTPS` | `RequireHttps` | `true` |
| `MLW_CERT_PATH` | `CertificatePath` (PKCS#12 `.pfx` din container) | `/config/cert.pfx` |
| `MLW_CERT_PASSWORD` | `CertificatePassword` (serverul o păstrează în `network.xml`; nu apare în jurnale) | |
| `MLW_REMOTE_ACCESS` | `EnableRemoteAccess` (conexiuni din afara rețelelor locale) | `true` / `false` |
| `MLW_KNOWN_PROXIES` | `KnownProxies` (listă; proxy-ul tău invers) | `172.16.0.0/12, 10.0.0.5` |
| `MLW_LOCAL_NETWORK_SUBNETS` | `LocalNetworkSubnets` (listă) | `192.168.1.0/24` |
| `MLW_LOCAL_NETWORK_ADDRESSES` | `LocalNetworkAddresses` (listă; adrese de ascultare) | |
| `MLW_PUBLISHED_URI_BY_SUBNET` | `PublishedServerUriBySubnet` (listă) | `192.168.1.0/24=http://192.168.1.10:8096` |
| `MLW_ENABLE_IPV4` / `MLW_ENABLE_IPV6` | `EnableIPv4` / `EnableIPv6` | `true` / `false` |
| `MLW_AUTO_DISCOVERY` | `AutoDiscovery` (UDP 7359) | `true` |
| `MLW_REMOTE_IP_FILTER` | `RemoteIPFilter` (listă) | `203.0.113.0/24` |
| `MLW_REMOTE_IP_FILTER_MODE` | `IsRemoteIPFilterBlacklist` | `allow` (listă permisă) / `block` (listă blocată) |

## Transcodare (`encoding.xml`)

| Variabilă | Setare | Exemplu |
|---|---|---|
| `MLW_HW_ACCEL` | `HardwareAccelerationType` | `none`, `qsv` (Intel), `vaapi` (AMD / Intel), `nvenc` (NVIDIA), `amf`, `v4l2m2m`, `rkmpp` |
| `MLW_VAAPI_DEVICE` | `VaapiDevice` | `/dev/dri/renderD128` |
| `MLW_QSV_DEVICE` | `QsvDevice` | `/dev/dri/renderD128` |
| `MLW_HW_DECODING_CODECS` | `HardwareDecodingCodecs` (listă) | `h264,hevc,vp9,av1` |
| `MLW_HW_ENCODING` | `EnableHardwareEncoding` | `true` |
| `MLW_TONEMAPPING` | `EnableTonemapping` (HDR în SDR) | `true` |
| `MLW_VPP_TONEMAPPING` | `EnableVppTonemapping` (Intel) | `true` |
| `MLW_TRANSCODE_PATH` | `TranscodingTempPath` | `/transcode` (de ex. un tmpfs) |
| `MLW_ENCODER_THREADS` | `EncodingThreadCount` (`-1` = automat) | `4` |
| `MLW_THROTTLING` | `EnableThrottling` | `true` |
| `MLW_SEGMENT_DELETION` | `EnableSegmentDeletion` | `true` |
| `MLW_FALLBACK_FONT_PATH` | `FallbackFontPath` (fonturi pentru subtitrări) | `/config/fonts` |

## Orice altă setare

| Variabilă | Scrie |
|---|---|
| `MLW_SYSTEM__<Proprietate>` | `<Proprietate>` în `system.xml` |
| `MLW_NETWORK__<Proprietate>` | `<Proprietate>` în `network.xml` |
| `MLW_ENCODING__<Proprietate>` | `<Proprietate>` în `encoding.xml` |
| `MLW_CONF__<fișier>__<Proprietate>` | `<Proprietate>` în `/config/config/<fișier>.xml` (fișierul trebuie să existe: serverul le creează pe cele mai multe la prima pornire) |

Proprietățile imbricate folosesc încă un `__`, de ex. `MLW_SYSTEM__TrickplayOptions__EnableHwAcceleration=true`.
Numele proprietăților țin cont de majuscule, exact ca în fișierul XML. O valoare care începe cu `[` e citită ca listă
JSON; o valoare cu virgule e scrisă ca listă dacă elementul existent e o listă. `IsStartupWizardCompleted` și
`PluginRepositories` nu se pot seta așa (vezi mai jos).

## Primul administrator (servere noi)

| Variabilă | Implicit | Descriere |
|---|---|---|
| `MLW_ADMIN_USER` | | Numele primului administrator. Când e setat (cu o parolă) pe un server al cărui asistent de configurare nu a fost încheiat, entrypoint-ul creează acest utilizator și încheie asistentul prin API-ul de pornire al serverului, în fundal, după ce serverul răspunde. E ignorat pe un server deja configurat (utilizatorii se administrează din panou). |
| `MLW_ADMIN_PASSWORD` | | Parola lui. Preferă `MLW_ADMIN_PASSWORD_FILE`. Nu apare niciodată în jurnale și e scoasă din mediul serverului. |
| `MLW_WIZARD_TIMEOUT` | `600` | Câte secunde se așteaptă serverul înainte de a renunța. |

## Plugin-uri

| Variabilă | Implicit | Descriere |
|---|---|---|
| `MLW_PLUGIN_REPOS` | `medialab,jellyfin` | Depozitele de plugin-uri, separate prin virgulă: `medialab` (catalogul public medialab.works), `jellyfin` (depozitul oficial Jellyfin), `Nume=https://…/manifest.json`, o adresă simplă sau `none` (lista nu e administrată din mediu). În modul `first-run` depozitele care lipsesc se adaugă în față și celelalte se păstrează; în modul `enforce` lista se înlocuiește. Pe un server nou, configurarea inițială resetează lista, așa că ea se aplică imediat după asistent (când e setat `MLW_ADMIN_*`) sau la următoarea pornire. |
| `MLW_REPO_KEY` | | Cheia depozitului tău medialab.works (`jfr_…`, din cont) sau adresa completă cu cheie. Adaugă primul catalogul licențiat `https://medialab.works/api/jellyfin/<cheie>/manifest.json`. Mascată în jurnale. |
| `MLW_CATALOG_URL` | `https://medialab.works/jellyfin/manifest.json` | Adresa catalogului public folosită pentru `medialab`. |
| `MLW_PLUGINS` | | Plugin-uri de instalat înainte de pornirea serverului, separate prin virgulă: `jf-rosub,jf-registration@1.0.2`. Un plugin e găsit după slug-ul medialab (`jf-rosub` sau doar `rosub`), după nume (`Rosub by MediaLab`) sau după GUID. `@versiune` fixează o versiune. Fiecare arhivă e verificată cu suma MD5 din manifest și dezarhivată în `/config/plugins/<Nume>_<versiune>/` cu `meta.json`; semnătura `.dll.sig` din arhivă se păstrează, ca serverul să afișeze „Verified – medialab”. Plugin-urile deja instalate nu se descarcă din nou. |
| `MLW_PLUGINS_UPDATE` | `false` | `true`: instalează la fiecare pornire cea mai nouă versiune compatibilă a plugin-urilor nefixate (versiunea veche se șterge). |
| `MLW_PLUGINS_STRICT` | `false` | `true`: serverul nu pornește dacă un plugin nu se poate instala. |
| `MLW_PLUGIN_<SLUG>__<Proprietate>` | | O valoare adăugată în fișierul de configurare al plugin-ului `/config/plugins/configurations/<Assembly>.xml`, de ex. `MLW_PLUGIN_ROSUB__ArchiveCacheDays=14`. `<SLUG>` e slug-ul plugin-ului cu sau fără `JF_` (`ROSUB`, `JF_ROSUB`), numele sau numele assembly-ului. Plugin-ul trebuie să fie instalat (prin `MLW_PLUGINS` sau din panou). Urmează `MLW_CONFIG_MODE`. Valorile proprietăților al căror nume conține `KEY`, `TOKEN`, `SECRET` sau `PASSWORD` nu apar în jurnale. |

Se pot monta și fișiere de configurare întregi: `/config/plugins/configurations/<Assembly>.xml` (de ex. `Rosub.xml`).

## Chei de licență

| Variabilă | Descriere |
|---|---|
| `MLW_LICENSE_KEY` | O cheie de licență medialab.works, transmisă neschimbată procesului server. |
| `MLW_LICENSE_KEY_<SLUG>` | Cheia de licență a unui plugin, de ex. `MLW_LICENSE_KEY_JF_ROSUB`. |
| `*_FILE`, `/run/secrets/mlw_license_key[_<slug>]` | La fel, din fișiere: un secret Docker numit `mlw_license_key` sau `mlw_license_key_jf_rosub` devine `MLW_LICENSE_KEY` / `MLW_LICENSE_KEY_JF_ROSUB`. |

Cheile nu apar niciodată în jurnale. Plugin-urile le citesc din mediu **de la versiunile de plugin care suportă asta**;
până atunci, introdu cheia în pagina plugin-ului din panou (se păstrează în `/config`).

## Setate de imagine (schimbă-le doar dacă știi de ce)

| Variabilă | Valoare |
|---|---|
| `JELLYFIN_DATA_DIR` | `/config` |
| `JELLYFIN_CONFIG_DIR` | `/config/config` |
| `JELLYFIN_LOG_DIR` | `/config/log` |
| `JELLYFIN_CACHE_DIR` | `/cache` |
| `JELLYFIN_WEB_DIR` | `/usr/share/jellyfin/web` |
| `JELLYFIN_FFMPEG` | `/usr/lib/jellyfin-ffmpeg/ffmpeg` |
| `NVIDIA_VISIBLE_DEVICES`, `NVIDIA_DRIVER_CAPABILITIES` | `all`, `compute,video,utility` |
| `MLW_CONTAINER` | `docker` (plugin-urile află că rulează într-un container) |

Serverul citește și orice variabilă `JELLYFIN_<Cheie>` ca opțiune de pornire (configurația .NET), de ex.
`JELLYFIN_PublishedServerUrl`. Atenție: serverul scrie în jurnal valorile tuturor variabilelor `JELLYFIN_*` la pornire,
deci nu pune secrete în ele.
