<div align="center">

<br/>

```
                                 ██╗   ██╗ ██████╗███████╗██╗   ██╗███████╗███████╗
                                 ██║   ██║██╔════╝██╔════╝██║   ██║╚══███╔╝╚══███╔╝
                                 ██║   ██║██║     █████╗  ██║   ██║  ███╔╝   ███╔╝ 
                                 ██║   ██║██║     ██╔══╝  ██║   ██║ ███╔╝   ███╔╝  
                                 ╚██████╔╝╚██████╗██║     ╚██████╔╝███████╗███████╗
                                  ╚═════╝  ╚═════╝╚═╝      ╚═════╝ ╚══════╝╚══════╝
```

**Browser-based web fuzzer. Bypasses WAFs, solves CAPTCHAs, looks like a real user.**

<br/>

[![PyPI version](https://img.shields.io/pypi/v/ucfuzz?color=00d4aa&labelColor=0a0a0a&style=flat-square)](https://pypi.org/project/ucfuzz)
[![Python](https://img.shields.io/badge/python-3.11%2B-00d4aa?labelColor=0a0a0a&style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-00d4aa?labelColor=0a0a0a&style=flat-square)](LICENSE)
[![PyPI downloads](https://img.shields.io/pypi/dm/ucfuzz?color=00d4aa&labelColor=0a0a0a&style=flat-square)](https://pypi.org/project/ucfuzz)

<br/>

</div>

---

## Why UCFuzz?

Most fuzzers send raw HTTP requests. That works — until the target runs Cloudflare, has browser fingerprinting, requires a login session, or throws a CAPTCHA on suspicious traffic.

UCFuzz runs a **real Chrome browser** via undetected-chromedriver. Every request has a real TLS fingerprint, real browser headers, real JavaScript execution. To the server, it looks like a human clicking links.

```
Traditional fuzzer          UCFuzz
─────────────────           ──────────────────────────────
raw HTTP request   vs.      full Chrome browser session
blocked by WAF              bypasses Cloudflare, Akamai
no JS execution             executes JS, handles SPAs
no cookie session           keeps your login session
fails on CAPTCHA            pauses for you to solve it
```

---

## Install

```bash
pip install ucfuzz
```

Or from source:

```bash
git clone https://github.com/raceoverflow/ucfuzz
cd ucfuzz
pip install .
```

---

## Quick start

```bash
ucfuzz -u https://target.com/FUZZ -w wordlist.txt
```

The browser opens. Log in, solve any CAPTCHA, then press **Enter** — UCFuzz takes over from there.

---

## Usage

```
ucfuzz [OPTIONS]

Options:
  -u, --url TEXT              Target URL with FUZZ placeholder  [required]
  -w, --wordlist PATH         Path to wordlist  [required]
  -o, --output PATH           Save results as JSONL
  --delay TEXT                Delay between requests: 100ms, 1s, 2m  [default: 0s]
  --timeout FLOAT             Response timeout in seconds  [default: 10.0]
  --exclude-status INTEGER    Hide this status code (repeatable)  [default: 404]
  --exclude-length INTEGER    Hide this content length (repeatable)
  --extension TEXT            Append extension to every word: php, html, js
  --headless                  Run browser without a window
  --help                      Show this message and exit
```

---

## Use cases

### Directory discovery

Standard directory brute-force on a site protected by Cloudflare. UCFuzz navigates through the challenge automatically.

```bash
ucfuzz -u https://target.com/FUZZ -w raft-large-dirs.txt --delay 50ms
```

> 📽️ *[GIF: directory scan running, hits showing in green/yellow]*

---

### File extension fuzzing

Find hidden files with specific extensions. Combine with `--exclude-length` to filter out identical error pages.

```bash
ucfuzz -u https://target.com/FUZZ          \
       -w raft-small-words.txt             \
       --extension php                     \
       --exclude-length 1234               \
       -o results.jsonl
```

> 📽️ *[GIF: extension scan, filtering noise, clean hits]*

---

### Authenticated scanning

UCFuzz keeps the full browser session alive. Log in through the browser window when it opens — cookies, tokens, and session state are all preserved for every subsequent request.

```bash
ucfuzz -u https://app.target.com/api/FUZZ \
       -w api-endpoints.txt               \
       --delay 200ms
```

> 📽️ *[GIF: browser login step, then scan continuing with authenticated session]*

---

### Slow, human-like scanning

Avoid rate-limiting and IDS alerts by mimicking realistic browsing speed.

```bash
ucfuzz -u https://target.com/FUZZ -w wordlist.txt --delay 2s --timeout 30
```

---

## Output

Results print live to the terminal, colour-coded by status:

```
https://target.com/admin          (Status: 200) [Size: 4821]
https://target.com/backup.zip     (Status: 200) [Size: 204800]
https://target.com/config         (Status: 403) [Size: 312]
https://target.com/.env           (Status: 200) [Size: 89]
```

Save to JSONL with `-o results.jsonl` for further processing:

```bash
cat results.jsonl | jq 'select(.status_code == 200)'
```

---

## Recommended wordlists

UCFuzz works with any plain-text wordlist.

---

## Roadmap

Things coming next, roughly in priority order:

- [ ] **Parallel browser sessions** — run N browsers simultaneously for faster scans without looking like a bot
- [ ] **Recursive mode** — automatically fuzz newly discovered directories with specified recursion depth
- [ ] **Custom headers & cookies** — inject `Authorization`, `X-API-Key`, or any arbitrary header per request
- [ ] **POST / PUT fuzzing** — fuzz request bodies, not just URLs
- [ ] **Report export** — generate HTML/Markdown reports from JSONL output
- [ ] **Smarter response handling** - parse robots.txt, sitemap, ds_store and opendir responses
- [ ] **Save the state** - save the state of scans in sqlite database
- [ ] **Web GUI** - modern minimalistic web GUI based on FastAPI
- [ ] **More evasion** - more evasion with random delay option in specified range
- [ ] **CAPTCHA indicator** - indicate captcha by inclusion of specific markers to prevent it from wasting wordlist until solved
- [ ] **Optimization** - add flags for disabling css and media loading

Have a feature request? [Open an issue](https://github.com/raceoverflow/ucfuzz/issues).

---

## Legal

UCFuzz is intended for **authorized security testing only**. Only use it against systems you own or have explicit written permission to test. Unauthorized use is illegal and unethical.

---

<div align="center">

MIT License — © 2026 raceoverflow

</div>
