# C0rp0s3cur3---Tor-Enabled-Web-Crawler
A Python-based Tor-enabled web crawler for crawling `.onion` sites and public websites. It can search for user-provided keywords, save HTML pages, and log results in CSV format. Works entirely through Tor for anonymity.

---

## Features

- Crawl `.onion` sites via Tor (`socks5h://127.0.0.1:9050`)
- BFS-based crawling with configurable depth
- Save HTML pages locally
- Log crawl results in CSV (`crawl_log.csv`)
- Respect `robots.txt` (optional)
- Customizable user-agent and request delay
- Search for keywords on `.onion` sites (experimental)

---

## Requirements

- Python 3.8+
- Tor installed and running

### Python dependencies

```bash
pip install requests[socks] tqdm beautifulsoup4 lxml

### System dependencies
### System dependencies

```bash
sudo apt install tor
```

---

## Usage

```bash
python tor_crawler_func.py -u <URL or .onion> -d <DEPTH> [options]
```

### Options
- `-u`, `--url` : Start URL (required)
- `-d`, `--depth` : Crawl depth (default: 1)
- `-p`, `--delay` : Delay between requests in seconds (default: 2)
- `--no-tor` : Disable Tor (use direct requests)
- `--no-robots` : Ignore `robots.txt`
- `--user-agent` : Set custom user-agent
- `--max-pages` : Maximum pages to crawl (default: 200)
- `-o`, `--output` : Output directory for saved HTML and logs (default: `tor_output`)

---
## Example

Crawl a `.onion` site via Tor with depth 2:

```bash
python tor_crawler_func.py -u http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion -d 2
```
The crawler will save HTML pages in `tor_output` and log crawl results in `crawl_log.csv`.

---
## Notes

- Ensure Tor service is running:

```bash
sudo systemctl start tor
sudo systemctl status tor
```

- The crawler is intended for **public pages only**. It does not bypass CAPTCHAs or login forms.
- For large crawls, adjust `--max-pages` and `--delay` to avoid overloading sites.
- Use responsibly and ethically.
