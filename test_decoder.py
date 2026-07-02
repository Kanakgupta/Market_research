#!/usr/bin/env python3
import logging
from bluetooth_news.gnews_decoder import decode_google_news_url

logging.basicConfig(level=logging.DEBUG)

# One of the Google News URLs from our customers page
test_url = "https://news.google.com/rss/articles/CBMiggFBVV95cUxNNE9MQ2tJYVhlS1FTcXlaRDhpVjV5NjF5Skd3QUk2ZjFUeWp5SGxjNWxsWF9kNEd5Y0VIUklmejhyVG8tQ2FTTFh6MHVESGMyZlNqdzh1VnItWGhYenZieFpvanlyb3pXczdydW5IQVIwZG50RWxXY09qSUFma1h5cDdR?oc=5"

print("Original:", test_url)
decoded = decode_google_news_url(test_url)
print("Decoded URL:")
print(decoded)
