#!/usr/bin/python3 -I
# SPDX-License-Identifier: GPL-2.0-only
"""
medialab Server container setup helper (called by /usr/local/bin/entrypoint, runs as the server user).

Sub-commands:
  settings       apply server settings from the environment to system.xml / network.xml / encoding.xml (+ any other
                 *.xml through MLW_CONF__<file>__<Property>) and the plugin repository list
  plugins        install / update plugins listed in MLW_PLUGINS from the plugin manifests (MD5 checksum verified)
  plugin-config  merge MLW_PLUGIN_<SLUG>__<Property>=value into the plugins' configuration XML files
  wizard         wait for the server, then create the first administrator and complete the startup wizard
  show-env       print the effective non-secret settings (debugging)

Only the Python standard library is used. Secrets (passwords, licence keys, keyed repository URLs) are never printed.
The *_FILE forms of the variables are resolved by the entrypoint before this script runs.
"""

import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

PUBLIC_CATALOG = "https://medialab.works/jellyfin/manifest.json"
KEYED_CATALOG = "https://medialab.works/api/jellyfin/{key}/manifest.json"
JELLYFIN_REPO = "https://repo.jellyfin.org/files/plugin/manifest.json"

DATA_DIR = os.environ.get("JELLYFIN_DATA_DIR", "/config")
CONFIG_DIR = os.environ.get("JELLYFIN_CONFIG_DIR", os.path.join(DATA_DIR, "config"))
PLUGINS_DIR = os.path.join(DATA_DIR, "plugins")
PLUGIN_CONF_DIR = os.path.join(PLUGINS_DIR, "configurations")
STATE_FILE = os.path.join(DATA_DIR, ".medialab-docker", "state.json")

XSI = "http://www.w3.org/2001/XMLSchema-instance"
XSD = "http://www.w3.org/2001/XMLSchema"

USER_AGENT = "medialab-server-docker/1 (+https://github.com/CristianCasapu/medialab-server-docker)"
MAX_DOWNLOAD = 256 * 1024 * 1024

# ---------------------------------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------------------------------


def log(msg):
    print(f"[medialab] {msg}", flush=True)


def warn(msg):
    print(f"[medialab] WARNING: {msg}", file=sys.stderr, flush=True)


def env(name, default=None):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def env_bool(name, default=False):
    value = env(name)
    if value is None:
        return default
    return parse_bool(value, name)


def parse_bool(value, name="value"):
    v = str(value).strip().lower()
    if v in ("1", "true", "yes", "y", "on", "enable", "enabled"):
        return True
    if v in ("0", "false", "no", "n", "off", "disable", "disabled"):
        return False
    raise ValueError(f"{name}: '{value}' is not a boolean (use true or false)")


def split_list(value):
    """Comma / semicolon / newline separated list; a JSON array is accepted too."""
    value = (value or "").strip()
    if value.startswith("["):
        try:
            data = json.loads(value)
            return [str(x).strip() for x in data if str(x).strip()]
        except json.JSONDecodeError:
            pass
    return [x.strip() for x in re.split(r"[,;\n]+", value) if x.strip()]


def norm(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def mask_url(url):
    """Hide medialab repository keys (jfr_...) and query strings (signed links) in log lines."""
    url = re.sub(r"jfr_[A-Za-z0-9]+", "jfr_***", url)
    return url.split("?", 1)[0]


def server_abi():
    """12.2+ml5+deb12 -> 12.2.0.0 (Jellyfin compares targetAbi with the server version, 4 parts)."""
    raw = env("MLW_SERVER_ABI")
    if not raw:
        try:
            with open("/usr/lib/medialab-docker-version", encoding="utf-8") as fh:
                raw = fh.read().strip()
        except OSError:
            raw = "0"
    return four_part(raw)


def four_part(version):
    version = re.sub(r"^[^0-9]*", "", str(version or ""))
    version = re.split(r"[^0-9.]", version, 1)[0]
    parts = [int(p) for p in version.split(".") if p.isdigit()][:4]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts)


def vstr(t):
    return ".".join(str(x) for x in t)


def config_mode():
    mode = (env("MLW_CONFIG_MODE", "first-run") or "first-run").strip().lower()
    if mode not in ("first-run", "enforce"):
        raise ValueError(f"MLW_CONFIG_MODE must be first-run or enforce, not '{mode}'")
    return mode


# ---------------------------------------------------------------------------------------------------------------------
# state: which values were applied last time (hashes only, never the values)
# ---------------------------------------------------------------------------------------------------------------------


class State:
    def __init__(self):
        self.data = {}
        try:
            with open(STATE_FILE, encoding="utf-8") as fh:
                self.data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            self.data = {}

    def changed(self, key, value):
        return self.data.get(key) != digest(value)

    def remember(self, key, value):
        self.data[key] = digest(value)

    def save(self):
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=1, sort_keys=True)
        os.replace(tmp, STATE_FILE)


# ---------------------------------------------------------------------------------------------------------------------
# XML documents (Jellyfin's XmlSerializer format)
# ---------------------------------------------------------------------------------------------------------------------


class XmlDoc:
    def __init__(self, path, root_name):
        self.path = path
        self.created = False
        self.dirty = False
        if os.path.exists(path):
            try:
                self.tree = ET.parse(path)
            except ET.ParseError as exc:
                raise RuntimeError(f"{path} is not valid XML ({exc}); fix or remove it") from exc
        else:
            if root_name is None:
                self.tree = None
                return
            root = ET.Element(root_name)
            self.tree = ET.ElementTree(root)
            self.created = True
            self.dirty = True

    @property
    def exists(self):
        return self.tree is not None

    def element(self, path, create=True):
        node = self.tree.getroot()
        for part in path:
            child = node.find(part)
            if child is None:
                if not create:
                    return None
                child = ET.SubElement(node, part)
            node = child
        return node

    def get(self, path):
        node = self.element(path, create=False)
        return None if node is None else (node.text or "")

    def is_list(self, path):
        node = self.element(path, create=False)
        return node is not None and len(node) > 0 and all(c.tag == "string" for c in node)

    def set_scalar(self, path, value):
        node = self.element(path)
        if len(node) or node.text != value:
            for child in list(node):
                node.remove(child)
            node.text = value
            node.attrib.pop(f"{{{XSI}}}nil", None)
            self.dirty = True

    def set_list(self, path, values, item="string"):
        node = self.element(path)
        current = [c.text or "" for c in node]
        if current != values or any(c.tag != item for c in node):
            for child in list(node):
                node.remove(child)
            node.text = None
            for value in values:
                ET.SubElement(node, item).text = value
            self.dirty = True

    def save(self):
        if not self.dirty:
            return
        ET.register_namespace("xsi", XSI)
        ET.register_namespace("xsd", XSD)
        root = self.tree.getroot()
        indent(root)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".mlw-", dir=os.path.dirname(self.path))
        with os.fdopen(fd, "wb") as fh:
            fh.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
            self.tree.write(fh, encoding="utf-8", xml_declaration=False)
        if os.path.exists(self.path):
            shutil.copymode(self.path, tmp)
        else:
            os.chmod(tmp, 0o666 & ~current_umask())
        os.replace(tmp, self.path)
        self.dirty = False


def current_umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


def indent(elem, level=0):
    pad = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = pad + "  "
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = pad
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = pad


# ---------------------------------------------------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------------------------------------------------

FILES = {
    "system": ("system.xml", "ServerConfiguration"),
    "network": ("network.xml", "NetworkConfiguration"),
    "encoding": ("encoding.xml", "EncodingOptions"),
}

# friendly variable -> (file, property, kind); kind: str, bool, int, list, or a callable converter
FRIENDLY = {
    # system.xml
    "MLW_SERVER_NAME": ("system", "ServerName", "str"),
    "MLW_UI_CULTURE": ("system", "UICulture", "str"),
    "MLW_METADATA_LANGUAGE": ("system", "PreferredMetadataLanguage", "str"),
    "MLW_METADATA_COUNTRY": ("system", "MetadataCountryCode", "str"),
    "MLW_METADATA_PATH": ("system", "MetadataPath", "str"),
    "MLW_QUICKCONNECT": ("system", "QuickConnectAvailable", "bool"),
    "MLW_ENABLE_METRICS": ("system", "EnableMetrics", "bool"),
    "MLW_CORS_HOSTS": ("system", "CorsHosts", "list"),
    "MLW_ACTIVITY_LOG_RETENTION_DAYS": ("system", "ActivityLogRetentionDays", "int"),
    "MLW_LIBRARY_SCAN_CONCURRENCY": ("system", "LibraryScanFanoutConcurrency", "int"),
    "MLW_LIBRARY_REFRESH_CONCURRENCY": ("system", "LibraryMetadataRefreshConcurrency", "int"),
    "MLW_IMAGE_ENCODING_LIMIT": ("system", "ParallelImageEncodingLimit", "int"),
    "MLW_REMOTE_BITRATE_LIMIT": ("system", "RemoteClientBitrateLimit", "int"),
    "MLW_SLOW_RESPONSE_WARNING": ("system", "EnableSlowResponseWarning", "bool"),
    # network.xml
    "MLW_BASE_URL": ("network", "BaseUrl", "baseurl"),
    "MLW_HTTP_PORT": ("network", "InternalHttpPort", "int"),
    "MLW_HTTPS_PORT": ("network", "InternalHttpsPort", "int"),
    "MLW_PUBLIC_HTTP_PORT": ("network", "PublicHttpPort", "int"),
    "MLW_PUBLIC_HTTPS_PORT": ("network", "PublicHttpsPort", "int"),
    "MLW_ENABLE_HTTPS": ("network", "EnableHttps", "bool"),
    "MLW_REQUIRE_HTTPS": ("network", "RequireHttps", "bool"),
    "MLW_CERT_PATH": ("network", "CertificatePath", "str"),
    "MLW_CERT_PASSWORD": ("network", "CertificatePassword", "secret"),
    "MLW_REMOTE_ACCESS": ("network", "EnableRemoteAccess", "bool"),
    "MLW_KNOWN_PROXIES": ("network", "KnownProxies", "list"),
    "MLW_LOCAL_NETWORK_SUBNETS": ("network", "LocalNetworkSubnets", "list"),
    "MLW_LOCAL_NETWORK_ADDRESSES": ("network", "LocalNetworkAddresses", "list"),
    "MLW_PUBLISHED_URI_BY_SUBNET": ("network", "PublishedServerUriBySubnet", "list"),
    "MLW_ENABLE_IPV4": ("network", "EnableIPv4", "bool"),
    "MLW_ENABLE_IPV6": ("network", "EnableIPv6", "bool"),
    "MLW_AUTO_DISCOVERY": ("network", "AutoDiscovery", "bool"),
    "MLW_REMOTE_IP_FILTER": ("network", "RemoteIPFilter", "list"),
    "MLW_REMOTE_IP_FILTER_MODE": ("network", "IsRemoteIPFilterBlacklist", "filtermode"),
    # encoding.xml
    "MLW_HW_ACCEL": ("encoding", "HardwareAccelerationType", "hwaccel"),
    "MLW_VAAPI_DEVICE": ("encoding", "VaapiDevice", "str"),
    "MLW_QSV_DEVICE": ("encoding", "QsvDevice", "str"),
    "MLW_HW_DECODING_CODECS": ("encoding", "HardwareDecodingCodecs", "list"),
    "MLW_HW_ENCODING": ("encoding", "EnableHardwareEncoding", "bool"),
    "MLW_TONEMAPPING": ("encoding", "EnableTonemapping", "bool"),
    "MLW_VPP_TONEMAPPING": ("encoding", "EnableVppTonemapping", "bool"),
    "MLW_TRANSCODE_PATH": ("encoding", "TranscodingTempPath", "str"),
    "MLW_ENCODER_THREADS": ("encoding", "EncodingThreadCount", "int"),
    "MLW_THROTTLING": ("encoding", "EnableThrottling", "bool"),
    "MLW_SEGMENT_DELETION": ("encoding", "EnableSegmentDeletion", "bool"),
    "MLW_FALLBACK_FONT_PATH": ("encoding", "FallbackFontPath", "str"),
}

# Arrays of strings in these files (needed when the element does not exist yet).
KNOWN_LISTS = {
    "system": {"CorsHosts", "CodecsUsed", "SortReplaceCharacters", "SortRemoveCharacters", "SortRemoveWords"},
    "network": {"KnownProxies", "LocalNetworkSubnets", "LocalNetworkAddresses", "PublishedServerUriBySubnet",
                "RemoteIPFilter", "VirtualInterfaceNames"},
    "encoding": {"HardwareDecodingCodecs", "AllowOnDemandMetadataBasedKeyframeExtractionForExtensions"},
}

# Never written from the environment: the startup wizard must run through the API (database seeding depends on it).
FORBIDDEN = {("system", "IsStartupWizardCompleted"), ("system", "PluginRepositories")}

HWACCEL = {"none": "none", "": "none", "vaapi": "vaapi", "qsv": "qsv", "intel": "qsv", "nvenc": "nvenc",
           "nvidia": "nvenc", "cuda": "nvenc", "amf": "amf", "v4l2m2m": "v4l2m2m", "rkmpp": "rkmpp",
           "videotoolbox": "videotoolbox"}


def convert(kind, value, name):
    value = value.strip() if kind != "secret" else value
    if kind == "bool":
        return "true" if parse_bool(value, name) else "false"
    if kind == "int":
        if not re.fullmatch(r"-?[0-9]+", value):
            raise ValueError(f"{name}: '{value}' is not a whole number")
        return value
    if kind == "baseurl":
        value = value.strip().rstrip("/")
        if value and not value.startswith("/"):
            value = "/" + value
        return value
    if kind == "filtermode":
        v = value.lower()
        if v in ("block", "blocklist", "blacklist", "deny"):
            return "true"
        if v in ("allow", "allowlist", "whitelist"):
            return "false"
        raise ValueError(f"{name}: use allow or block, not '{value}'")
    if kind == "hwaccel":
        v = value.lower()
        if v not in HWACCEL:
            raise ValueError(f"{name}: unknown hardware acceleration '{value}' (none, vaapi, qsv, nvenc, amf, v4l2m2m, rkmpp)")
        return HWACCEL[v]
    return value


def wanted_settings():
    """[(file, path tuple, kind, value, variable name)] from the friendly and the generic variables."""
    out = []
    for name, (fkey, prop, kind) in FRIENDLY.items():
        value = env(name)
        if value is None:
            continue
        out.append((fkey, (prop,), "list" if kind == "list" else ("secret" if kind == "secret" else "scalar"),
                    split_list(value) if kind == "list" else convert(kind, value, name), name))
    generic = re.compile(r"^MLW_(SYSTEM|NETWORK|ENCODING)__(.+)$")
    other = re.compile(r"^MLW_CONF__([A-Za-z0-9_.-]+?)__(.+)$")
    for name in sorted(os.environ):
        if name.endswith("_FILE"):
            continue
        value = os.environ[name]
        m = generic.match(name)
        if m:
            fkey = m.group(1).lower()
            path = tuple(p for p in m.group(2).split("__") if p)
        else:
            m = other.match(name)
            if not m:
                continue
            fkey = "file:" + m.group(1)
            path = tuple(p for p in m.group(2).split("__") if p)
        if not path or not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", p) for p in path):
            raise ValueError(f"{name}: invalid property name")
        if (fkey, path[0]) in FORBIDDEN:
            warn(f"{name} is ignored: {path[0]} is managed by the entrypoint")
            continue
        is_list = len(path) == 1 and path[0] in KNOWN_LISTS.get(fkey, set())
        out.append((fkey, path, "list?" if not is_list else "list", value, name))
    return out


def open_doc(fkey):
    if fkey.startswith("file:"):
        name = fkey[5:]
        if not name.endswith(".xml"):
            name += ".xml"
        if "/" in name or name.startswith("."):
            raise ValueError(f"invalid configuration file name {name}")
        return XmlDoc(os.path.join(CONFIG_DIR, name), None)
    fname, root = FILES[fkey]
    return XmlDoc(os.path.join(CONFIG_DIR, fname), root)


def cmd_settings():
    mode = config_mode()
    state = State()
    docs = {}
    applied = 0
    for fkey, path, kind, value, name in wanted_settings():
        if fkey not in docs:
            docs[fkey] = open_doc(fkey)
        doc = docs[fkey]
        if not doc.exists:
            warn(f"{name}: {fkey[5:]}.xml does not exist yet (the server creates it); applied at the next start")
            continue
        state_key = f"{os.path.basename(doc.path)}:{'/'.join(path)}"
        serial = json.dumps(value) if isinstance(value, list) else value
        if mode == "first-run" and not doc.created and not state.changed(state_key, serial):
            continue
        if kind == "list" or (kind == "list?" and (doc.is_list(path) or str(value).strip().startswith("["))):
            items = value if isinstance(value, list) else split_list(value)
            doc.set_list(path, items)
            shown = f"{len(items)} item(s)"
        else:
            doc.set_scalar(path, value if isinstance(value, str) else str(value))
            shown = "(hidden)" if kind == "secret" or "PASSWORD" in name or "KEY" in name else repr(value)
        state.remember(state_key, serial)
        applied += 1
        log(f"{os.path.basename(doc.path)}: {'/'.join(path)} = {shown}")
    # plugin repositories (system.xml)
    if "system" not in docs:
        docs["system"] = open_doc("system")
    applied += apply_repositories(docs["system"], mode, state)
    for doc in docs.values():
        if doc.exists:
            doc.save()
    state.save()
    log(f"settings: {applied} value(s) applied (mode {mode})")


# ---------------------------------------------------------------------------------------------------------------------
# plugin repositories
# ---------------------------------------------------------------------------------------------------------------------


def repo_key_url():
    key = env("MLW_REPO_KEY")
    if not key:
        return None
    key = key.strip()
    if key.startswith("http://") or key.startswith("https://"):
        return key
    if not re.fullmatch(r"jfr_[A-Za-z0-9]{8,}", key):
        raise ValueError("MLW_REPO_KEY must be the repository key (jfr_...) or the full repository URL from your account")
    return KEYED_CATALOG.format(key=key)


def wanted_repositories():
    """[(name, url)] in order. Tokens: medialab, jellyfin, none, Name=URL, URL."""
    raw = env("MLW_PLUGIN_REPOS", "medialab,jellyfin")
    repos = []
    keyed = repo_key_url()
    if keyed:
        repos.append(("medialab.works (licensed)", keyed))
    for item in split_list(raw):
        low = item.lower()
        if low == "none":
            continue
        if low == "medialab":
            repos.append(("medialab.works", env("MLW_CATALOG_URL", PUBLIC_CATALOG)))
        elif low == "jellyfin":
            repos.append(("Jellyfin Stable", JELLYFIN_REPO))
        elif "=" in item and not item.lower().startswith("http"):
            name, url = item.split("=", 1)
            repos.append((name.strip(), url.strip()))
        elif item.lower().startswith("http://") or item.lower().startswith("https://"):
            host = urllib.parse.urlparse(item).hostname or item
            repos.append((host, item))
        else:
            raise ValueError(f"MLW_PLUGIN_REPOS: '{item}' is not medialab, jellyfin, none, Name=URL or a URL")
    seen, out = set(), []
    for name, url in repos:
        if url.lower() not in seen:
            seen.add(url.lower())
            out.append((name, url))
    return out


def apply_repositories(doc, mode, state):
    repos = wanted_repositories()
    if not repos:  # MLW_PLUGIN_REPOS=none and no key: the list is managed in the dashboard only
        return 0
    serial = json.dumps(repos)
    if mode == "first-run" and not doc.created and not state.changed("system.xml:PluginRepositories", serial):
        return 0
    node = doc.element(("PluginRepositories",))
    existing = []
    for info in node.findall("RepositoryInfo"):
        existing.append({c.tag: (c.text or "") for c in info})
    if mode == "enforce":
        merged = [{"Name": n, "Url": u, "Enabled": "true"} for n, u in repos]
    else:
        urls = {e.get("Url", "").lower() for e in existing}
        merged = [{"Name": n, "Url": u, "Enabled": "true"} for n, u in repos if u.lower() not in urls] + existing
    if merged != existing:
        for child in list(node):
            node.remove(child)
        node.text = None
        for entry in merged:
            info = ET.SubElement(node, "RepositoryInfo")
            for tag in ("Name", "Url", "Enabled"):
                ET.SubElement(info, tag).text = entry.get(tag, "true" if tag == "Enabled" else "")
        doc.dirty = True
        log("plugin repositories: " + ", ".join(f"{e['Name']} <{mask_url(e['Url'])}>" for e in merged))
    if doc.created:
        # On a new server, the setup migrations replace PluginRepositories with Jellyfin's default list. The value
        # is left pending: the post-start job applies it through the API (with MLW_ADMIN_*), else the next start does.
        log("plugin repositories: a new server resets the list during setup; applied again after the first start")
    else:
        state.remember("system.xml:PluginRepositories", serial)
    return 1


def merge_repositories(existing, mode):
    """existing: [{Name, Url, Enabled}] -> the list to keep, same rules as apply_repositories."""
    repos = [{"Name": n, "Url": u, "Enabled": True} for n, u in wanted_repositories()]
    if mode == "enforce":
        return repos
    urls = {str(e.get("Url", "")).lower() for e in existing}
    return [r for r in repos if r["Url"].lower() not in urls] + list(existing)


# ---------------------------------------------------------------------------------------------------------------------
# plugins
# ---------------------------------------------------------------------------------------------------------------------


def http_get(url, limit=MAX_DOWNLOAD, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - http(s) only, checked by callers
        data = resp.read(limit + 1)
        if len(data) > limit:
            raise RuntimeError("download too large")
        return data


def load_manifests():
    packages = []
    for name, url in wanted_repositories():
        if not url.lower().startswith(("http://", "https://")):
            continue
        try:
            data = json.loads(http_get(url, limit=32 * 1024 * 1024, timeout=30))
        except (urllib.error.URLError, OSError, RuntimeError, ValueError) as exc:
            warn(f"plugin repository {name} <{mask_url(url)}> not available: {exc}")
            continue
        if not isinstance(data, list):
            warn(f"plugin repository {name} <{mask_url(url)}> is not a plugin manifest")
            continue
        for pkg in data:
            if isinstance(pkg, dict) and pkg.get("guid") and pkg.get("name") and isinstance(pkg.get("versions"), list):
                pkg["_repo"] = name
                packages.append(pkg)
    return packages


def package_idents(pkg):
    ids = {str(pkg.get("guid", "")).lower(), norm(pkg.get("name"))}
    base = re.sub(r"\s+by\s+medialab\s*$", "", pkg.get("name", ""), flags=re.I)
    ids.add(norm(base))
    for ver in pkg.get("versions", []):
        m = re.search(r"/jellyfin/(?:download|source)/([a-z0-9-]+)/", str(ver.get("sourceUrl", "")))
        if m:
            ids.add(norm(m.group(1)))
            ids.add(norm(re.sub(r"^jf-", "", m.group(1))))
    ids.discard("")
    return ids


def ident_variants(ident):
    ident = ident.strip()
    out = {ident.lower(), norm(ident)}
    stripped = re.sub(r"^(jf|jellyfin)[-_]", "", ident, flags=re.I)
    out.add(norm(stripped))
    out.discard("")
    return out


def parse_plugin_list():
    items = []
    for item in split_list(env("MLW_PLUGINS", "")):
        name, _, version = item.partition("@")
        if not name.strip():
            continue
        items.append((name.strip(), version.strip() or None))
    return items


def installed_plugins():
    """[{dir, guid, version(tuple), name, assemblies}] from /config/plugins/*/meta.json."""
    out = []
    if not os.path.isdir(PLUGINS_DIR):
        return out
    for entry in sorted(os.listdir(PLUGINS_DIR)):
        path = os.path.join(PLUGINS_DIR, entry)
        meta = os.path.join(path, "meta.json")
        if not os.path.isdir(path) or entry == "configurations":
            continue
        info = {"dir": path, "guid": "", "version": four_part(entry.rsplit("_", 1)[-1] if "_" in entry else "0"),
                "name": entry.rsplit("_", 1)[0], "assemblies": [], "status": ""}
        if os.path.isfile(meta):
            try:
                with open(meta, encoding="utf-8") as fh:
                    m = json.load(fh)
                info.update({"guid": str(m.get("guid", "")).lower(), "version": four_part(m.get("version", "0")),
                             "name": m.get("name") or info["name"], "assemblies": m.get("assemblies") or [],
                             "status": m.get("status", "")})
            except (OSError, ValueError):
                pass
        out.append(info)
    return out


def safe_dir_name(name):
    if not name or name in (".", "..") or "/" in name or "\\" in name or "\0" in name:
        raise RuntimeError(f"plugin name '{name}' is not a valid directory name")
    return name


def install_package(pkg, ver):
    name = safe_dir_name(pkg["name"])
    version = vstr(four_part(ver["version"]))
    url = str(ver.get("sourceUrl", ""))
    if not url.lower().startswith(("https://", "http://")):
        raise RuntimeError("the manifest has no http(s) download URL")
    checksum = str(ver.get("checksum", "")).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", checksum):
        raise RuntimeError("the manifest has no MD5 checksum; refusing to install")
    data = http_get(url)
    got = hashlib.md5(data, usedforsecurity=False).hexdigest()
    if got != checksum:
        raise RuntimeError(f"checksum mismatch (expected {checksum}, got {got})")
    os.makedirs(PLUGINS_DIR, exist_ok=True)
    target = os.path.join(PLUGINS_DIR, f"{name}_{version}")
    tmp = tempfile.mkdtemp(prefix=".mlw-install-", dir=PLUGINS_DIR)
    try:
        local_meta = {}
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for member in zf.infolist():
                parts = member.filename.replace("\\", "/").split("/")
                if member.filename.startswith(("/", "\\")) or ".." in parts or re.match(r"^[A-Za-z]:", member.filename):
                    raise RuntimeError(f"unsafe path in the archive: {member.filename}")
            zf.extractall(tmp)
        meta_path = os.path.join(tmp, "meta.json")
        if os.path.isfile(meta_path):
            with open(meta_path, encoding="utf-8") as fh:
                local_meta = json.load(fh)
            if str(local_meta.get("guid", pkg["guid"])).lower() != str(pkg["guid"]).lower():
                raise RuntimeError("the guid in the archive's meta.json does not match the manifest")
        # meta.json as Jellyfin's PluginManager writes it after an install (package data, local values win).
        meta = {
            "category": local_meta.get("category") or pkg.get("category", ""),
            "changelog": local_meta.get("changelog") or ver.get("changelog") or "",
            "description": local_meta.get("description") or pkg.get("description", ""),
            "guid": pkg["guid"],
            "name": local_meta.get("name") or pkg["name"],
            "overview": local_meta.get("overview") or pkg.get("overview", ""),
            "owner": local_meta.get("owner") or pkg.get("owner", ""),
            "targetAbi": local_meta.get("targetAbi") or ver.get("targetAbi") or "",
            "timestamp": local_meta.get("timestamp") or ver.get("timestamp") or "0001-01-01T00:00:00.0000000Z",
            "version": version,
            "status": "Active",
            "autoUpdate": local_meta.get("autoUpdate", True),
            "imagePath": local_meta.get("imagePath", ""),
            "assemblies": local_meta.get("assemblies") or [],
        }
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)
        if os.path.exists(target):
            shutil.rmtree(target)
        os.replace(tmp, target)
        os.chmod(target, 0o777 & ~current_umask())  # mkdtemp created it 0700
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
    sigs = [f for f in os.listdir(target) if f.endswith(".dll.sig")]
    return target, sigs


def cmd_plugins():
    wanted = parse_plugin_list()
    if not wanted:
        return 0
    update = env_bool("MLW_PLUGINS_UPDATE", False)
    abi = server_abi()
    if not update:
        # Nothing to download when every plugin is already there (no network access needed at each start).
        present = installed_plugins()
        pending = []
        for ident, req_version in wanted:
            info = find_installed(ident, present)
            if info and (not req_version or info["version"] == four_part(req_version)):
                log(f"plugin {info['name']} {vstr(info['version'])}: installed")
            else:
                pending.append((ident, req_version))
        if not pending:
            return 0
        wanted = pending
    packages = load_manifests()
    if not packages:
        warn("no plugin manifest could be read; plugins not installed")
        return 1
    failures = 0
    for ident, req_version in wanted:
        variants = ident_variants(ident)
        matches = [p for p in packages if package_idents(p) & variants]
        if not matches:
            warn(f"plugin '{ident}': not found in the plugin repositories")
            failures += 1
            continue
        # every version of that plugin from every repository (a keyed and the public catalog may both list it)
        guid = str(matches[0]["guid"]).lower()
        candidates = []
        for p in packages:
            if str(p["guid"]).lower() != guid:
                continue
            for v in p.get("versions", []):
                if four_part(v.get("targetAbi") or "0") <= abi:
                    candidates.append((four_part(v.get("version")), p, v))
        candidates.sort(key=lambda c: c[0], reverse=True)
        if req_version:
            candidates = [c for c in candidates if c[0] == four_part(req_version)]
        if not candidates:
            warn(f"plugin '{ident}': no version {req_version or ''} compatible with server ABI {vstr(abi)}".replace("  ", " "))
            failures += 1
            continue
        version, pkg, ver = candidates[0]
        mine = [i for i in installed_plugins() if i["guid"] == guid]
        have = {i["version"] for i in mine}
        if req_version:
            if version in have and len(have) == 1:
                log(f"plugin {pkg['name']} {vstr(version)}: already installed")
                continue
        elif mine:
            if max(have) >= version:
                log(f"plugin {pkg['name']} {vstr(max(have))}: installed, newest available")
                continue
            if not update:
                log(f"plugin {pkg['name']} {vstr(max(have))}: installed ({vstr(version)} available; MLW_PLUGINS_UPDATE=true installs it)")
                continue
        try:
            target, sigs = install_package(pkg, ver)
        except (urllib.error.URLError, OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
            warn(f"plugin '{ident}' {vstr(version)}: install failed: {exc}")
            failures += 1
            continue
        for old in mine:
            if os.path.abspath(old["dir"]) != os.path.abspath(target):
                shutil.rmtree(old["dir"], ignore_errors=True)
        signed = f", signature kept ({', '.join(sigs)})" if sigs else ", unsigned"
        log(f"plugin {pkg['name']} {vstr(version)} installed from {pkg['_repo']} (MD5 verified{signed})")
    return 1 if failures else 0


# ---------------------------------------------------------------------------------------------------------------------
# plugin configuration
# ---------------------------------------------------------------------------------------------------------------------


def plugin_config_file(info):
    dlls = info["assemblies"] or sorted(f for f in os.listdir(info["dir"]) if f.lower().endswith(".dll"))
    if not dlls:
        return None
    main = dlls[0]
    if len(dlls) > 1:
        for dll in dlls:  # prefer an assembly with an existing configuration file or named like the plugin
            base = os.path.splitext(os.path.basename(dll))[0]
            if os.path.exists(os.path.join(PLUGIN_CONF_DIR, base + ".xml")) or norm(base) in norm(info["name"]):
                main = dll
                break
    return os.path.join(PLUGIN_CONF_DIR, os.path.splitext(os.path.basename(main))[0] + ".xml")


def find_installed(slug, plugins):
    variants = ident_variants(slug.replace("_", "-"))
    best = None
    for info in plugins:
        if info["status"] in ("Superceded", "Superseded", "Deleted"):
            continue
        ids = {info["guid"], norm(info["name"]), norm(re.sub(r"\s+by\s+medialab\s*$", "", info["name"], flags=re.I))}
        for dll in info["assemblies"] or [f for f in os.listdir(info["dir"]) if f.lower().endswith(".dll")]:
            ids.add(norm(os.path.splitext(os.path.basename(dll))[0]))
        if ids & variants and (best is None or info["version"] > best["version"]):
            best = info
    return best


def cmd_plugin_config():
    mode = config_mode()
    state = State()
    pattern = re.compile(r"^MLW_PLUGIN_([A-Za-z0-9_]+?)__(.+)$")
    plugins = installed_plugins()
    docs = {}
    applied = 0
    for name in sorted(os.environ):
        m = pattern.match(name)
        if not m or name.endswith("_FILE"):
            continue
        slug, prop = m.group(1), m.group(2)
        path = tuple(p for p in prop.split("__") if p)
        if not path or not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", p) for p in path):
            raise ValueError(f"{name}: invalid property name")
        info = find_installed(slug, plugins)
        if not info:
            warn(f"{name}: no installed plugin matches '{slug}' (install it first, e.g. MLW_PLUGINS=jf-{slug.lower()})")
            continue
        conf = plugin_config_file(info)
        if not conf:
            warn(f"{name}: cannot find the assembly of {info['name']}")
            continue
        if conf not in docs:
            docs[conf] = XmlDoc(conf, "PluginConfiguration")
        doc = docs[conf]
        value = os.environ[name]
        state_key = f"plugins/{os.path.basename(conf)}:{'/'.join(path)}"
        if mode == "first-run" and not doc.created and not state.changed(state_key, value):
            continue
        if doc.is_list(path) or value.strip().startswith("["):
            doc.set_list(path, split_list(value))
        else:
            doc.set_scalar(path, value)
        state.remember(state_key, value)
        applied += 1
        secret = any(w in name.upper() for w in ("PASSWORD", "SECRET", "TOKEN", "KEY", "APIKEY"))
        log(f"plugin {info['name']}: {'/'.join(path)} = {'(hidden)' if secret else repr(value)}")
    for doc in docs.values():
        doc.save()
    state.save()
    if applied:
        log(f"plugin settings: {applied} value(s) applied (mode {mode})")


# ---------------------------------------------------------------------------------------------------------------------
# startup wizard (first administrator)
# ---------------------------------------------------------------------------------------------------------------------


def local_base():
    port, base = "8096", ""
    try:
        doc = XmlDoc(os.path.join(CONFIG_DIR, "network.xml"), None)
        if doc.exists:
            port = (doc.get(("InternalHttpPort",)) or "8096").strip() or "8096"
            base = (doc.get(("BaseUrl",)) or "").strip().rstrip("/")
    except RuntimeError:
        pass
    if base and not base.startswith("/"):
        base = "/" + base
    return f"http://127.0.0.1:{port}{base}"


def api(method, url, body=None, timeout=15):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - local server
        raw = resp.read()
        return resp.status, (json.loads(raw) if raw.strip().startswith((b"{", b"[")) else None)


def cmd_wizard():
    user = env("MLW_ADMIN_USER")
    password = env("MLW_ADMIN_PASSWORD")
    if not user:
        return 0
    if not password:
        warn("MLW_ADMIN_USER is set but MLW_ADMIN_PASSWORD (or MLW_ADMIN_PASSWORD_FILE) is empty; the wizard is left to the web UI")
        return 1
    timeout = int(env("MLW_WIZARD_TIMEOUT", "600"))
    deadline = time.monotonic() + timeout
    info = None
    while time.monotonic() < deadline:
        base = local_base()
        try:
            status, info = api("GET", base + "/System/Info/Public", timeout=5)
            if status == 200 and isinstance(info, dict) and "StartupWizardCompleted" in info:
                break
        except (urllib.error.URLError, OSError, ValueError):
            pass
        info = None
        time.sleep(3)
    if info is None:
        warn(f"the server did not answer within {timeout}s; the first administrator was not created")
        return 1
    if info.get("StartupWizardCompleted"):
        log("startup wizard already completed; MLW_ADMIN_* ignored (users are managed in the dashboard)")
        return 0
    try:
        api("GET", base + "/Startup/User")  # creates the initial user record
        api("POST", base + "/Startup/User", {"Name": user, "Password": password})
        api("POST", base + "/Startup/Complete")
    except urllib.error.HTTPError as exc:
        warn(f"startup wizard: the server answered HTTP {exc.code} ({exc.reason}); finish the wizard in the web UI")
        return 1
    except (urllib.error.URLError, OSError, ValueError) as exc:
        warn(f"startup wizard failed: {exc.__class__.__name__}; finish the wizard in the web UI")
        return 1
    log(f"startup wizard completed; administrator '{user}' created")
    return post_wizard_repositories(base, user, password)


def post_wizard_repositories(base, user, password):
    """Applies the pending plugin repository list through the API, signed in as the new administrator."""
    state = State()
    if not wanted_repositories():
        return 0
    serial = json.dumps(wanted_repositories())
    if not state.changed("system.xml:PluginRepositories", serial):
        return 0
    auth = 'MediaBrowser Client="medialab-docker", Device="entrypoint", DeviceId="medialab-docker", Version="1"'
    try:
        data = json.dumps({"Username": user, "Pw": password}).encode("utf-8")
        req = urllib.request.Request(base + "/Users/AuthenticateByName", data=data, method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": auth,
                                              "User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - local server
            token = json.loads(resp.read())["AccessToken"]
        headers = {"Authorization": f'{auth}, Token="{token}"', "User-Agent": USER_AGENT,
                   "Content-Type": "application/json", "Accept": "application/json"}
        req = urllib.request.Request(base + "/Repositories", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            existing = json.loads(resp.read()) or []
        merged = merge_repositories(existing, config_mode())
        req = urllib.request.Request(base + "/Repositories", data=json.dumps(merged).encode("utf-8"),
                                     method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=15):  # noqa: S310
            pass
        try:  # sign out the temporary session
            req = urllib.request.Request(base + "/Sessions/Logout", data=b"", method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=15):  # noqa: S310
                pass
        except (urllib.error.URLError, OSError):
            pass
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        warn(f"plugin repositories not applied through the API ({exc.__class__.__name__}); applied at the next start")
        return 1
    state.remember("system.xml:PluginRepositories", serial)
    state.save()
    log("plugin repositories: " + ", ".join(f"{r['Name']} <{mask_url(r['Url'])}>" for r in merged))
    return 0


# ---------------------------------------------------------------------------------------------------------------------


def cmd_show_env():
    for fkey, path, kind, value, name in wanted_settings():
        shown = "(hidden)" if kind == "secret" else value
        print(f"{name} -> {fkey}:{'/'.join(path)} = {shown}")
    for name, url in wanted_repositories():
        print(f"repository {name} <{mask_url(url)}>")
    for ident, version in parse_plugin_list():
        print(f"plugin {ident}{'@' + version if version else ''}")
    return 0


def main(argv):
    commands = {"settings": cmd_settings, "plugins": cmd_plugins, "plugin-config": cmd_plugin_config,
                "wizard": cmd_wizard, "show-env": cmd_show_env}
    if len(argv) != 2 or argv[1] not in commands:
        print("usage: mlw_setup.py " + "|".join(commands), file=sys.stderr)
        return 2
    try:
        return commands[argv[1]]() or 0
    except (ValueError, RuntimeError) as exc:
        print(f"[medialab] ERROR: {exc}", file=sys.stderr, flush=True)
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
