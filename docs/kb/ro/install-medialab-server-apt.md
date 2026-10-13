# Instalarea medialab Server din depozitul apt (Debian/Ubuntu)

medialab Server e distribuit ca pachete Debian semnate din `https://apt.medialab.works/debian`:

| Pachet | Conținut |
|---|---|
| `medialab-server` | serverul (bazat pe Jellyfin 12.2), serviciul de sistem `jellyfin` și actualizatorul din interfață |
| `medialab-server-web` | interfața web |
| `jellyfin-ffmpeg8` | varianta FFmpeg a Jellyfin, folosită la transcodare |
| `medialab-repo` | definiția depozitului și cheia lui de semnare |

Arhitecturi: `amd64` și `arm64`.

## Sisteme suportate

Pachetele sunt construite pentru **Debian 12 (bookworm)** (`+deb12` în versiune) și pentru distribuțiile derivate din
bookworm, de exemplu Raspberry Pi OS (64 de biți) bookworm. Depind de biblioteci din Debian 12 (de exemplu `libicu72`),
deci nu se instalează pe versiunile Ubuntu sau pe alte versiuni Debian. Pe Ubuntu folosește imaginea de container
(vezi „Instalarea medialab Server într-un container”).

## 1. Adaugi depozitul

Pachetul `medialab-repo` instalează definiția depozitului și cheia de semnare:

```sh
curl -fsSLO https://apt.medialab.works/medialab-repo.deb
sudo apt install ./medialab-repo.deb
```

Creează `/etc/apt/sources.list.d/medialab.sources`:

```
Types: deb
URIs: https://apt.medialab.works/debian
Suites: stable
Components: main
Signed-By: /usr/share/keyrings/medialab-archive-keyring.gpg
```

**Varianta manuală.** Descarci cheia și creezi singur același fișier:

```sh
sudo curl -fsSL https://apt.medialab.works/debian/medialab-archive-keyring.gpg \
  -o /usr/share/keyrings/medialab-archive-keyring.gpg
gpg --show-keys /usr/share/keyrings/medialab-archive-keyring.gpg
```

Amprenta cheii trebuie să fie `6B7D 46D8 2C3C 4D4C 0A14  2F92 4189 96EB 3CE1 59C7`
(„medialab Server packages <packages@medialab.works>”). Apoi scrii fișierul `medialab.sources` de mai sus.

La fiecare `apt update`, apt verifică semnătura depozitului cu această cheie.

## 2. Instalezi

```sh
sudo apt update
sudo apt install medialab-server medialab-server-web jellyfin-ffmpeg8
```

`medialab-server` înlocuiește `jellyfin-server`, iar `medialab-server-web` înlocuiește `jellyfin-web`: dacă Jellyfin e
deja instalat din depozitul Jellyfin, apt scoate cele două pachete și păstrează datele, pentru că medialab Server
folosește aceleași dosare. La prima pornire baza de date e actualizată la formatul 12.2, pe care un Jellyfin mai vechi
nu îl mai poate deschide: fă mai întâi o copie de siguranță (vezi mai jos). Dacă depozitul Jellyfin rămâne configurat,
apt păstrează pachetele medialab instalate; poți scoate depozitul Jellyfin dacă nu mai ai nevoie de el.

## 3. Serviciul

Serverul rulează ca serviciul de sistem `jellyfin`, cu utilizatorul `jellyfin`:

```sh
sudo systemctl status jellyfin
sudo systemctl restart jellyfin
sudo journalctl -u jellyfin -f
```

Deschide `http://<server>:8096` și parcurge asistentul de configurare.

| Cale | Conținut |
|---|---|
| `/etc/jellyfin` | setări (`system.xml`, `network.xml`, `encoding.xml`, `logging.json`) |
| `/var/lib/jellyfin` | baza de date, plugin-uri, metadate |
| `/var/log/jellyfin` | jurnale |
| `/var/cache/jellyfin` | cache |
| `/etc/default/jellyfin` | opțiuni de pornire (dosarul web, calea FFmpeg, opțiuni suplimentare) |
| `/usr/share/jellyfin/web` | interfața web |
| `/usr/lib/jellyfin-ffmpeg/ffmpeg` | FFmpeg |

Pentru alt utilizator al serviciului sau alte opțiuni systemd folosește `sudo systemctl edit jellyfin` (sau fișierul
`/etc/systemd/system/jellyfin.service.d/jellyfin.service.conf`).

Pentru transcodare hardware cu o placă Intel sau AMD, pachetul adaugă utilizatorul `jellyfin` în grupurile `render` și
`video`; alegi metoda în Panou → Redare → Transcodare. Pentru NVIDIA instalează mai întâi driverul NVIDIA din
distribuție.

## 4. Actualizări

```sh
sudo apt update
sudo apt upgrade
```

Pachetul oprește serviciul în timpul actualizării și îl pornește din nou pe versiunea nouă. Pachetul conține și un
serviciu de actualizare (`medialab-update.path` / `medialab-update.service`), folosit de plugin-ul
„Self-Update by MediaLab” ca să actualizeze serverul din interfața web; instalează pachetele din același depozit.

Ca să rămâi pe o versiune: `sudo apt-mark hold medialab-server medialab-server-web`
(`sudo apt-mark unhold …` ca să anulezi).

## Copie de siguranță

Oprești serviciul și copiezi dosarele cu setări și date:

```sh
sudo systemctl stop jellyfin
sudo tar -czf medialab-backup-$(date +%F).tar.gz /etc/jellyfin /var/lib/jellyfin
sudo systemctl start jellyfin
```

## Dezinstalare

```sh
sudo apt remove medialab-server medialab-server-web     # păstrează setările, datele și jurnalele
sudo apt remove medialab-repo                            # scoate depozitul
```

`sudo apt purge medialab-server` **șterge** în plus `/etc/jellyfin`, `/var/lib/jellyfin` (baza de date, plugin-uri,
metadate), `/var/log/jellyfin`, `/var/cache/jellyfin` și utilizatorul `jellyfin`. Fă o copie de siguranță înainte.

## Probleme frecvente

- **`apt update` raportează o eroare de semnătură (NO_PUBKEY / EXPKEYSIG):** reinstalează `medialab-repo` (pasul 1)
  ca să primești cheia actuală.
- **Dependențe nesatisfăcute, de exemplu `libicu72`:** sistemul nu e Debian 12; folosește imaginea de container.
- **Serviciul nu pornește:** `sudo journalctl -u jellyfin -n 100` și fișierele din `/var/log/jellyfin` arată motivul.
  Verifică dacă utilizatorul `jellyfin` poate citi dosarele cu fișiere media.
- **Portul 8096 e deja ocupat:** rulează alt Jellyfin sau alt server media; oprește-l sau schimbă portul în
  Panou → Rețea.
