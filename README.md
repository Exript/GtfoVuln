# gtfo-cli

Enumerate local **SUID/SGID** binaries and **file capabilities**, then map each one
to its matching [GTFObins](https://gtfobins.github.io/) privilege-escalation entry.

The GTFObins database is cached locally, so after one `--update` the tool runs
fully **offline** — ideal for engagements where the target has no internet.

## Install

```bash
pipx install gtfo-cli          # from PyPI
uvx gtfo-cli                    # run without installing
```

Install straight from git:

```bash
pipx install git+https://github.com/Exript/gtfo-cli
uvx --from git+https://github.com/Exript/gtfo-cli gtfo-cli
```

## Usage

```bash
gtfo-cli --update              # download the offline GTFObins DB (once)
gtfo-cli                       # scan the host and print GTFObins links
gtfo-cli --root /              # scan from a custom root
GTFO_DB=/tmp/db gtfo-cli       # use a portable cached DB (offline targets)
```

Created by **Exript**.


