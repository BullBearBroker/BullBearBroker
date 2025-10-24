#!/usr/bin/env python3
# QA: force IPv4 hostaddr into SUPABASE_DB_URL in backend/.env.local (idempotent)
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path

ENV_PATH = Path("backend/.env.local")
_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
# QA: evita registrar los resolvers públicos como IP válidas
_INVALID_RESOLVER_IPS = {"1.1.1.1", "8.8.8.8"}


def _is_valid_ipv4(value: str) -> bool:
    return bool(_IPV4_RE.match(value)) and value not in _INVALID_RESOLVER_IPS


def _try_shell_resolvers(host: str) -> str | None:
    """# QA: extra IPv4 resolvers without new deps."""

    def _clean(line: str) -> str:
        return line.strip()

    # dig (Cloudflare / Google)
    if shutil.which("dig"):
        for dns in ("1.1.1.1", "8.8.8.8"):
            try:
                out = subprocess.check_output(
                    ["dig", "+short", "A", host, "@" + dns],
                    text=True,
                    timeout=3, stderr=subprocess.DEVNULL,
                )
                for line in map(_clean, out.splitlines()):
                    if _is_valid_ipv4(line):
                        return line
            except Exception:
                pass

    # nslookup
    if shutil.which("nslookup"):
        for dns in ("1.1.1.1", "8.8.8.8"):
            try:
                out = subprocess.check_output(
                    ["nslookup", host, dns],
                    text=True,
                    timeout=3, stderr=subprocess.DEVNULL,
                )
                for line in map(_clean, out.splitlines()):
                    if "Address:" in line:
                        candidate = line.split("Address:")[-1].strip()
                        if candidate != dns and _is_valid_ipv4(candidate):
                            return candidate
            except Exception:
                pass

    # host
    if shutil.which("host"):
        try:
            out = subprocess.check_output(
                ["host", "-t", "A", host, "1.1.1.1"],
                text=True,
                timeout=3, stderr=subprocess.DEVNULL,
            )
            for token in out.replace(",", " ").split():
                if _is_valid_ipv4(token):
                    return token
        except Exception:
            pass

    # ping (best-effort)
    if shutil.which("ping"):
        try:
            out = subprocess.check_output(
                ["ping", "-c1", host],
                text=True,
                timeout=3, stderr=subprocess.DEVNULL,
            )
            for token in (
                out.replace("(", " ")
                .replace(")", " ")
                .replace(":", " ")
                .split()
            ):
                if _is_valid_ipv4(token):
                    return token
        except Exception:
            pass

    return None


def main() -> None:
    if not ENV_PATH.exists():
        print('{"updated": false, "reason": "env_local_missing"}')
        return

    text = ENV_PATH.read_text(encoding="utf-8")
    match = re.search(r"^SUPABASE_DB_URL=(.+)$", text, flags=re.M)
    if not match:
        print('{"updated": false, "reason": "url_missing"}')
        return

    url = match.group(1)
    if "hostaddr=" in url:
        print('{"updated": false, "reason": "already_has_hostaddr"}')
        return

    override = os.getenv("SUPABASE_DB_HOSTADDR")
    ipv4: str | None = None
    source = "dns"

    if override:
        ipv4 = override.strip()
        source = "env"
    else:
        host_match = re.search(r"@([^:/?#]+)", url)
        host = host_match.group(1) if host_match else None
        if not host:
            print('{"updated": false, "reason": "host_not_found"}')
            return
        try:
            ipv4 = socket.getaddrinfo(host, 5432, family=socket.AF_INET)[0][4][0]
            if not _is_valid_ipv4(ipv4):
                # QA: fallback a resolvers de sistema cuando getaddrinfo devuelve valores no útiles
                ipv4 = _try_shell_resolvers(host)
        except Exception:
            # QA: fallback a resolvers de sistema cuando AF_INET no está disponible
            ipv4 = _try_shell_resolvers(host)

    if source != "env":
        if not ipv4 or not _is_valid_ipv4(ipv4):
            print('{"updated": false, "reason": "no_ipv4"}')
            return
    else:
        if not ipv4 or not _IPV4_RE.match(ipv4):
            print('{"updated": false, "reason": "no_ipv4"}')
            return

    sep = "&" if "?" in url else "?"
    new_url = f"{url}{sep}hostaddr={ipv4}"
    new_text = re.sub(r"^SUPABASE_DB_URL=.+$", f"SUPABASE_DB_URL={new_url}", text, flags=re.M)
    ENV_PATH.write_text(new_text, encoding="utf-8")
    print(f'{{"updated": true, "hostaddr": "{ipv4}", "source": "{source}"}}')


if __name__ == "__main__":
    main()
