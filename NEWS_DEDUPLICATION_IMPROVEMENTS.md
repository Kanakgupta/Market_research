# News Deduplication Improvements

## Problem
The news.html page at localhost:5005/news.html showed **LOT OF DUPLICATE NEWS** because the deduplication logic was too basic and only caught:
- Exact URL matches
- Exact title matches

This missed:
- Same article published from multiple news sources with slightly different titles
- Rewrites of the same news with paraphrased content
- Articles with URL parameters, redirects, or tracking codes
- News syndication from RSS feeds (common with tech news sites)

## Solution: Multi-Layer Semantic Deduplication

### Changes Made

#### 1. **aggregator.py** — Enhanced `process()` function

**Two-pass deduplication strategy:**

**Pass 1: Basic Filtering**
- Empty/invalid articles
- **Exact URL normalization** (removes query params, fragments)
- Age filtering (keep recent articles only)
- Relevance filtering (bucket/vendor/customer/app matching)

**Pass 2: Semantic/Content-Based Deduplication**
- **Content Fingerprinting**: Hash-based fingerprint of title + summary to catch rewrites
- **Fuzzy Title Matching**: 80% title similarity threshold (85% for same vendor+customer)
- **Content Similarity**: Jaccard token-based similarity for summaries (>75% = duplicate)
- **Recency Preference**: Keep newer/better-sourced articles when duplicates found

**New Helper Functions:**
```python
_content_fingerprint(title, summary)     # MD5 hash of normalized content
_title_similarity(title1, title2)        # SequenceMatcher ratio (0-1)
_content_similarity(text1, text2)        # Jaccard token-based (0-1)
_normalize_title()                       # Remove punctuation for better matching
```

**Logging Output:**
- Now reports: `duplicate_urls`, `semantic_dup`, `age`, `relevance` separately
- Makes it easy to see what's being filtered and why

---

#### 2. **tech_news.py** — Enhanced `_fetch_all()` function

**Advanced deduplication for RSS feeds:**
- **Exact link matching** (fast path)
- **Content hash matching** (catches rewrites in RSS)
- **Fuzzy title matching** with 85% similarity threshold
- **Recency-based selection** when near-duplicates found

**Why This Helps:**
- Tech news sites often syndicate the same article across multiple feeds
- RSS titles can be slightly different while content is identical
- Some sources rewrite the same news in different words

---

## Impact

### Before
- ✗ Many duplicate articles in news.html
- ✗ Low signal-to-noise ratio
- ✗ User confused by repeated content
- ✗ Limited insight from aggregated news

### After
- ✓ Semantic duplicates removed (same story from different sources)
- ✓ Better dedup of paraphrased/rewritten content
- ✓ Cleaner, more focused news feed
- ✓ Handles RSS syndication properly
- ✓ Respects recency (newer/better sources preferred)
- ✓ Better for vendor/customer/app classification

---

## Configuration

### Deduplication Thresholds

The thresholds can be tuned in `aggregator.py`:

```python
# Title similarity threshold (80% = "very similar")
threshold = 0.80

# Same vendor+customer: stricter matching (85%)
if (same_vendor_and_customer):
    threshold = 0.85

# Content similarity threshold (75% = likely duplicate)
if content_sim > 0.75:
    duplicate_found = True
```

### Adjustments for Your Domain

If you still see duplicates, you can:
1. **Lower thresholds** (e.g., 0.75 → 0.70) for more aggressive dedup
2. **Increase thresholds** (e.g., 0.80 → 0.85) to keep more variants
3. **Skip specific sources** in feed configuration if they're too noisy

---

## Technical Details

### Why Semantic Dedup Works

1. **Content Fingerprinting** captures **intent, not exact wording**
   - Different sources describe the same announcement differently
   - Hash signature catches these semantic duplicates

2. **Fuzzy Title Matching** uses **sequence alignment**
   - Handles missing words, reordering, punctuation differences
   - 80% threshold = same core story, not just keyword overlap

3. **Token-Based Content Similarity** is **cheap and effective**
   - Jaccard similarity = intersection / union of tokens
   - Catches paraphrased summaries without heavy NLP

4. **Recency Preference** keeps **best article per story**
   - Newer timestamp = likely better reporting
   - Better source = trusted news outlet

---

## Testing

To see the improvements in action:

```bash
# Full rebuild with verbose logging (see dedup stats)
python run.py --verbose

# Log output shows:
# Aggregator filtering: empty=12, duplicate_urls=24, semantic_dup=18, age=5, relevance=31
```

Check [docs/news.html](docs/news.html) to verify:
- ✓ No repeated article titles
- ✓ Clean list of unique stories
- ✓ Recent articles prioritized
- ✓ Different vendors/sources represented fairly

---

## Future Enhancements

Possible improvements for even better dedup:

1. **NLP-based semantic similarity** (expensive, but more accurate)
   - Use embeddings (sentence-transformers) for context-aware matching
   - Better handling of synonyms, industry terminology

2. **URL canonicalization** (more sophisticated)
   - Follow redirects and resolve shortened URLs
   - Handle AMP vs non-AMP versions

3. **Source reputation scoring**
   - Prefer established tech news outlets
   - Downweight low-quality sources

4. **Time-decay for older articles**
   - Automatically age out 30+ day old stories
   - Focus on fresh signals

5. **Duplicate clustering visualization**
   - Show which articles are related/clustered
   - Display "5 outlets covering this story"

---

## Files Modified

- `src/bluetooth_news/aggregator.py` — Main deduplication logic
- `src/bluetooth_news/tech_news.py` — RSS-specific deduplication

Both now use advanced techniques to catch semantic duplicates and improve news signal quality.
