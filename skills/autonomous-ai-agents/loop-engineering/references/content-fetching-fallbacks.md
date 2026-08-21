# Content Fetching Fallbacks
**Date:** 2026-06-17
**Purpose:** Reliable content extraction when primary tools fail

## Problem Patterns

### 1. pulse_dig Timeout
- **Symptom:** `TimeoutError: MCP call timed out after 120.0s`
- **Solution:** Use browser tools instead
  - `browser_navigate(url)` → `browser_snapshot()` or `browser_vision()`
  - Works even when direct HTTP requests are blocked

### 2. Reddit Blocked
- **Symptom:** `HTTP Error 403: Blocked` or `blocked by network security`
- **Solution:** 
  - Mark URL as visited immediately to prevent retry loops
  - Use browser tools if available (sometimes works when urllib doesn't)
  - Alternative: Find the same content on other platforms (Twitter, HackerNews, etc.)

### 3. Direct HTTP Blocked
- **Symptom:** 403/404 from urllib or curl
- **Solution:**
  - Try browser tools first
  - For scholarly papers: Use arXiv API (`export.arxiv.org/api/query`)
  - For PDFs: Download and extract text (pdftotext or pikepdf)

## Working Examples

### arXiv Paper Extraction
```python
import urllib.request
import xml.etree.ElementTree as ET

req = urllib.request.Request(
    'http://export.arxiv.org/api/query?id_list=2605.26340v1',
    headers={'User-Agent': 'Hermes-Pulse-Wurm/2.0'}
)
```

### PDF Text Extraction
```bash
pdftotext paper.pdf -  # stdout
# or
python3 -c "import pikepdf; p = pikepdf.open('paper.pdf'); print(p.pages[0].extract_text())"
```

## Decision Tree

```
pulse_dig → browser_navigate → browser_snapshot/vision
    ↓ (if timeout)
  browser tools (often works when MCP fails)
    ↓ (if blocked)
  Mark visited, try alternative sources
    ↓ (for papers)
  arXiv API → PDF extraction
```