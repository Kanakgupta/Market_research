"""Decode Google News tracking URLs to direct source URLs."""
import base64
import json
import logging
import re
from urllib.parse import quote, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

log = logging.getLogger(__name__)

def decode_google_news_url(source_url: str, timeout: int = 5) -> str:
    """
    Decodes a Google News article RSS URL back to its original source URL.
    Optimized to be fast, starting with local decryption & falling back to batchexecute/redirect lookup.
    """
    if "news.google.com" not in source_url:
        return source_url

    try:
        parsed = urlparse(source_url)
        path = parsed.path.split("/")
        if len(path) > 1 and path[-2] in ["articles", "read"]:
            base64_str = path[-1]
        else:
            # Maybe path[-1] is articles or read, or it is in the query parameter?
            # Let's check common RSS parameters
            return source_url

        # Fast path 1: Try local base64 decoding
        try:
            padding = '=' * (-len(base64_str) % 4)
            # Remove any trailing query parameters like ?oc=5
            clean_b64 = base64_str.split("?")[0]
            decoded_bytes = base64.urlsafe_b64decode(clean_b64 + padding)
            decoded_str = decoded_bytes.decode("latin1")

            prefix = b"\x08\x13\x22".decode("latin1")
            if decoded_str.startswith(prefix):
                decoded_str = decoded_str[len(prefix) :]

            suffix = b"\xd2\x01\x00".decode("latin1")
            if decoded_str.endswith(suffix):
                decoded_str = decoded_str[: -len(suffix)]

            bytes_array = bytearray(decoded_str, "latin1")
            if bytes_array:
                length = bytes_array[0]
                if length >= 0x80:
                    decoded_str = decoded_str[2 : length + 1]
                else:
                    decoded_str = decoded_str[1 : length + 1]

                if decoded_str.startswith(("http://", "https://")) and not decoded_str.startswith("AU_yqL"):
                    return decoded_str
        except Exception:
            pass

        # Fast path 2: If we are offline or want to avoid network, can return early.
        # But since user wants to land directly on customer page, let's do network resolution.
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        }
        
        # Try both formats
        clean_b64 = base64_str.split("?")[0]
        params_url = f"https://news.google.com/articles/{clean_b64}"
        try:
            response = requests.get(params_url, headers=headers, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException:
            params_url = f"https://news.google.com/rss/articles/{clean_b64}"
            response = requests.get(params_url, headers=headers, timeout=timeout)
            response.raise_for_status()

        html = response.text
        ts_match = re.search(r'data-n-a-ts="(\d+)"', html) or re.search(r"data-n-a-ts='(\d+)'", html)
        sg_match = re.search(r'data-n-a-sg="([^"]+)"', html) or re.search(r"data-n-a-sg='([^']+)'", html)

        if ts_match and sg_match:
            timestamp = ts_match.group(1)
            signature = sg_match.group(1)

            api_url = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
            payload = [
                "Fbv4je",
                f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{clean_b64}",{timestamp},"{signature}"]'
            ]
            
            data = f"f.req={quote(json.dumps([[payload]]))}"
            headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
            
            api_response = requests.post(api_url, headers=headers, data=data, timeout=timeout)
            api_response.raise_for_status()
            
            parts = api_response.text.split("\n\n")
            if len(parts) >= 2:
                parsed_data = json.loads(parts[1])[:-2]
                decoded_url = json.loads(parsed_data[0][2])[1]
                if decoded_url.startswith(("http://", "https://")):
                    return decoded_url
    except Exception as e:
        log.debug("decode_google_news_url failed for %s: %s", source_url, e)

    # Fallback to direct redirect headers follow
    try:
        r = requests.get(source_url, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True, timeout=timeout)
        if r.url.startswith(("http://", "https://")):
            return r.url
    except Exception:
        pass

    return source_url

def decode_articles_urls(articles: list[dict], max_workers: int = 16) -> list[dict]:
    """Decodes Google News URLs for a list of articles in parallel."""
    gnews_articles = [a for a in articles if "news.google.com" in a.get("url", "")]
    if not gnews_articles:
        return articles

    log.info("Decoding %d Google News URLs in parallel...", len(gnews_articles))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_article = {
            executor.submit(decode_google_news_url, a["url"]): a 
            for a in gnews_articles
        }
        for future in as_completed(future_to_article):
            article = future_to_article[future]
            try:
                decoded = future.result()
                if decoded and decoded.startswith(("http://", "https://")):
                    article["url"] = decoded
            except Exception as e:
                log.debug("Failed decoding article %s: %s", article.get("title"), e)

    return articles
