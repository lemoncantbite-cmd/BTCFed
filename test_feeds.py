import feedparser

feeds = {
    # Forex
    "FXStreet": "https://www.fxstreet.com/rss/news",
    "Investing Forex": "https://www.investing.com/rss/news_1.rss",
    "ForexLive": "https://www.forexlive.com/feed/news",
    "ActionForex": "https://www.actionforex.com/feed",
    "ForexCrunch": "https://www.forexcrunch.com/feed",
    # Crypto
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph": "https://cointelegraph.com/rss",
    "Decrypt": "https://decrypt.co/feed",
    "Bitcoin Magazine": "https://bitcoinmagazine.com/.rss/full/",
    "CryptoSlate": "https://cryptoslate.com/feed/",
    "The Block": "https://www.theblock.co/rss.xml",
}

for name, url in feeds.items():
    f = feedparser.parse(url, agent="Mozilla/5.0")
    print(f"{name}: {len(f.entries)} entries, status={f.get('status')}")
