#!/usr/bin/env python3
"""
Usage:
  python tor_crawler_func.py -u http://example.com -d 1
  python tor_crawler_func.py -u http://xxxxxx.onion -d 2
"""

import argparse
import os
import sys
import time
import csv
import logging
import subprocess
from urllib.parse import urljoin, urldefrag, urlparse
from collections import deque
import requests
from bs4 import BeautifulSoup
import urllib.robotparser
from tqdm import tqdm
from requests.exceptions import RequestException

# --- Default constants ---
TOR_PROXY = "socks5h://127.0.0.1:9050"
DEFAULT_USER_AGENT = "ShadowCrawler/1.0 (+https://example.local)"
DEFAULT_DELAY = 2
DEFAULT_MAX_PAGES = 200
DEFAULT_OUTPUT_DIR = "tor_output"

# --- Logging setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


# === TOR CHECK FUNCTIONS ===

def check_tor_installed() -> bool:
    """Check if Tor binary is installed on system."""
    result = subprocess.call("which tor", shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result == 0:
        logging.info("[+] Tor is installed.")
        return True
    logging.error("[-] Tor is not installed. Please install it: sudo apt install tor")
    return False


def check_tor_service() -> bool:
    """Check if Tor service is active."""
    try:
        status = subprocess.check_output(["systemctl", "is-active", "tor"],
                                         stderr=subprocess.STDOUT).decode().strip()
        if status == "active":
            logging.info("[+] Tor service is running.")
            return True
        else:
            logging.warning(f"[-] Tor service status: {status}")
            return False
    except subprocess.CalledProcessError:
        logging.error("[-] Tor service not found or inactive.")
        return False


def start_tor_service():
    """Try to start the Tor service if not running."""
    logging.info("[*] Attempting to start Tor service...")
    os.system("sudo systemctl start tor")
    time.sleep(3)
    if not check_tor_service():
        sys.exit("[-] Failed to start Tor service. Please start it manually.")


# === Helper Functions ===

def normalize_url(url: str) -> str:
    """Normalize URL by removing fragments and enforcing scheme."""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc
    path = parsed.path or "/"
    return f"{scheme}://{netloc}{path}"


def get_domain(url: str) -> str:
    """Extract domain from URL."""
    return urlparse(url).netloc.lower()


def load_robots_txt(url: str):
    """Load robots.txt for the given URL's domain."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp
    except Exception:
        return None


def is_allowed(rp, user_agent: str, url: str) -> bool:
    """Check if crawling this URL is allowed by robots.txt."""
    if rp is None:
        return True
    try:
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True


def setup_session(use_tor: bool, user_agent: str):
    """Create a requests.Session with (or without) Tor."""
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    if use_tor:
        session.proxies.update({"http": TOR_PROXY, "https": TOR_PROXY})
    return session


def save_html(output_dir: str, url: str, content: bytes) -> str:
    """Save HTML content to a file and return its path."""
    parsed = urlparse(url)
    safe_name = parsed.netloc + parsed.path.replace("/", "_")
    if not safe_name or safe_name.endswith("_"):
        safe_name += "index"
    fname = f"{safe_name}.html"
    path = os.path.join(output_dir, fname[:200])  # truncate long names
    with open(path, "wb") as f:
        f.write(content)
    return path


def extract_links(base_url: str, html: str) -> set:
    """Extract all valid <a href> links from HTML."""
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme in ("http", "https"):
            links.add(normalize_url(full_url))
    return links


def log_to_csv(log_path: str, url: str, status, content_type="", saved_file=""):
    """Append a record to the crawl log CSV."""
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([url, status, content_type, saved_file])


# === Main Crawler Logic ===

def crawl(start_url, depth, delay, use_tor, output_dir, user_agent, respect_robots, max_pages):
    """Main crawl loop (BFS)."""
    start_url = normalize_url(start_url)
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "crawl_log.csv")

    # Initialize log file
    if not os.path.exists(log_path):
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["url", "status_code", "content_type", "saved_file"])

    session = setup_session(use_tor, user_agent)
    rp = load_robots_txt(start_url) if respect_robots else None

    visited = set()
    queue = deque([(start_url, 0)])
    processed = 0

    logging.info(f"Starting crawl: {start_url} | Depth={depth} | TOR={'ON' if use_tor else 'OFF'}")

    pbar = tqdm(total=max_pages, desc="Crawling", unit="page")
    while queue and processed < max_pages:
        url, level = queue.popleft()
        if url in visited or level > depth:
            continue

        # Robots.txt check
        if respect_robots and not is_allowed(rp, user_agent, url):
            logging.info(f"Blocked by robots.txt: {url}")
            log_to_csv(log_path, url, "robots_blocked")
            visited.add(url)
            pbar.update(1)
            continue

        try:
            resp = session.get(url, timeout=30)
            status = resp.status_code
            ctype = resp.headers.get("Content-Type", "")
            saved_file = ""

            if status == 200 and "text/html" in ctype.lower():
                saved_file = save_html(output_dir, url, resp.content)
                if level < depth:
                    links = extract_links(url, resp.text)
                    for link in links:
                        if link not in visited and get_domain(link).endswith(get_domain(start_url)):
                            queue.append((link, level + 1))

            log_to_csv(log_path, url, status, ctype, saved_file)
        except RequestException as e:
            logging.warning(f"Error fetching {url}: {e}")
            log_to_csv(log_path, url, f"error:{type(e).__name__}")

        visited.add(url)
        processed += 1
        pbar.update(1)
        time.sleep(delay)

    pbar.close()
    logging.info("Crawl complete.")


# === CLI Entrypoint ===

def main():
    parser = argparse.ArgumentParser(description="Functional Tor-enabled web crawler")
    parser.add_argument("-u", "--url", required=True, help="Start URL (http(s) or .onion)")
    parser.add_argument("-d", "--depth", type=int, default=1, help="Crawl depth")
    parser.add_argument("-p", "--delay", type=float, default=DEFAULT_DELAY, help="Delay between requests (sec)")
    parser.add_argument("--no-tor", action="store_true", help="Disable TOR (use direct requests)")
    parser.add_argument("--no-robots", action="store_true", help="Ignore robots.txt")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent string")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help="Maximum pages to crawl")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR, help="Output directory")

    args = parser.parse_args()

    # --- Tor checks ---
    if not args.no_tor:
        if not check_tor_installed():
            sys.exit(1)
        if not check_tor_service():
            start_tor_service()

    # --- Start crawl ---
    crawl(
        start_url=args.url,
        depth=args.depth,
        delay=args.delay,
        use_tor=not args.no_tor,
        output_dir=args.output,
        user_agent=args.user_agent,
        respect_robots=not args.no_robots,
        max_pages=args.max_pages
    )


if __name__ == "__main__":
    main()

