"""gtfo-cli - map local SUID/SGID + capabilities to GTFObins privesc entries."""
from __future__ import annotations

import argparse
import io
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

import yaml

GTFO_BASE = "https://gtfobins.github.io/gtfobins"
TARBALL_URL = (
    "https://codeload.github.com/GTFOBins/GTFOBins.github.io/tar.gz/refs/heads/master"
)

# ANSI colors (auto-disabled when output is not a TTY / NO_COLOR is set)
_TTY = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _TTY else text


def db_dir() -> Path:
    """Cache location for the offline GTFObins DB. Override with $GTFO_DB."""
    override = os.environ.get("GTFO_DB")
    if override:
        return Path(override)
    base = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(base) / "gtfo-cli"


def bin_dir() -> Path:
    return db_dir() / "_gtfobins"


BANNER = r""" ██████╗████████╗███████╗ ██████╗        ██████╗██╗     ██╗
██╔════╝╚══██╔══╝██╔════╝██╔═══██╗      ██╔════╝██║     ██║
██║  ███╗  ██║   █████╗  ██║   ██║█████╗██║     ██║     ██║
██║   ██║  ██║   ██╔══╝  ██║   ██║╚════╝██║     ██║     ██║
╚██████╔╝  ██║   ██║     ╚██████╔╝      ╚██████╗███████╗██║
 ╚═════╝   ╚═╝   ╚═╝      ╚═════╝        ╚═════╝╚══════╝╚═╝
                                                           
"""


def banner() -> str:
    tagline = "                       created by Exript"
    return c(BANNER, "36") + c(tagline, "90") + "\n"


# ---------------------------------------------------------------------------
# GTFObins DB (download / cache)
# ---------------------------------------------------------------------------
def update_db() -> bool:
    print(c("[*]", "34"), "Fetching GTFObins DB...")
    try:
        req = urllib.request.Request(TARBALL_URL, headers={"User-Agent": "gtfo-cli"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
    except Exception as exc:  # offline target, proxy, etc.
        print(c("[-]", "31"), f"Download failed: {exc}")
        print("    Offline target? Copy a cached DB and set $GTFO_DB.")
        return False

    target = bin_dir()
    if target.exists():
        shutil.rmtree(target)
    db_dir().mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/")
            if len(parts) >= 3 and parts[1] == "_gtfobins" and member.isfile():
                member.name = parts[-1]  # flatten
                tar.extract(member, target)  # noqa: S202 (trusted GitHub source)

    count = len(list(target.iterdir()))
    print(c("[+]", "32"), f"DB ready: {count} binaries -> {target}")
    return True


def ensure_db() -> bool:
    if bin_dir().is_dir() and any(bin_dir().iterdir()):
        return True
    return update_db()


# ---------------------------------------------------------------------------
# GTFObins lookup
# ---------------------------------------------------------------------------
def funcs_for_context(binary: str, wanted_contexts) -> list[str]:
    """Return GTFObins function-names (anchors) for a binary that expose any of
    the wanted contexts (e.g. 'suid', 'limited-suid', 'capabilities')."""
    path = bin_dir() / binary
    if not path.is_file():
        return []
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []

    wanted = set(wanted_contexts)
    hits = []
    for fname, fbody in (doc.get("functions") or {}).items():
        # Each function maps to a list of example entries (sometimes a single
        # dict); every entry carries its own `contexts`.
        entries = fbody if isinstance(fbody, list) else [fbody]
        ctx_names: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            contexts = entry.get("contexts")
            if isinstance(contexts, dict):
                ctx_names |= set(contexts.keys())
            elif isinstance(contexts, list):
                ctx_names |= set(contexts)
        if ctx_names & wanted:
            hits.append(fname)
    return sorted(set(hits))


def report(binary: str, contexts) -> bool:
    fns = funcs_for_context(binary, contexts)
    if not fns:
        return False
    for fn in fns:
        link = f"{GTFO_BASE}/{binary}/#{fn}"
        print(f"  {c(binary.ljust(20), '33')} --> {c(link, '32')}")
    return True


# ---------------------------------------------------------------------------
# Host enumeration
# ---------------------------------------------------------------------------
def iter_suid_sgid(root: str = "/"):
    """Yield paths of files with the SUID or SGID bit set."""
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        for name in filenames:
            fp = os.path.join(dirpath, name)
            try:
                st = os.lstat(fp)
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            if st.st_mode & (stat.S_ISUID | stat.S_ISGID):
                yield fp


def iter_capabilities(root: str = "/"):
    """Yield (path, caps) using getcap. Returns [] if getcap is unavailable."""
    if shutil.which("getcap") is None:
        return
    try:
        out = subprocess.run(
            ["getcap", "-r", root],
            capture_output=True, text=True, timeout=120,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # format: "/path/to/bin cap_setuid=ep"  (older getcap uses " = ")
        path = line.split(" =")[0].split(" cap_")[0].strip()
        yield path, line


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_scan(root: str) -> int:
    if not ensure_db():
        return 1

    hit = False

    print("\n" + c("[*]", "34"), "Enumerating SUID/SGID binaries...")
    print(c(">>> SUID matches (context: suid / limited-suid):", "1"))
    seen = set()
    for fp in iter_suid_sgid(root):
        b = os.path.basename(fp)
        if b in seen:
            continue
        seen.add(b)
        if report(b, ("suid", "limited-suid")):
            hit = True

    print("\n" + c("[*]", "34"), "Enumerating file capabilities (getcap)...")
    print(c(">>> Capabilities matches (context: capabilities):", "1"))
    if shutil.which("getcap") is None:
        print("  " + c("[!]", "33"), "getcap not found -> apt install libcap2-bin")
    else:
        seen = set()
        for fp, _caps in iter_capabilities(root):
            b = os.path.basename(fp)
            if b in seen:
                continue
            seen.add(b)
            if report(b, ("capabilities",)):
                hit = True

    print()
    if hit:
        print(c("Happy Hack Day ^-^", "32"))
    else:
        print("No SUID/capabilities-based GTFObins entries found :(")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="gtfo-cli",
        description="Map local SUID/SGID + capabilities to GTFObins privesc entries.",
    )
    parser.add_argument("--update", action="store_true",
                        help="(re)download the offline GTFObins DB and exit")
    parser.add_argument("--root", default="/",
                        help="filesystem root to scan (default: /)")
    parser.add_argument("--no-banner", action="store_true", help="suppress the banner")
    args = parser.parse_args(argv)

    if not args.no_banner:
        print(banner())

    if args.update:
        return 0 if update_db() else 1
    return run_scan(args.root)


if __name__ == "__main__":
    sys.exit(main())
