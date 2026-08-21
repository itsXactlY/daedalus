# PULSE Integration Details for BTQuant Macro Feed

## Endpoint Behavior

The PULSE MCP search endpoint (`http://127.0.0.1:8770/search`) returns:
- `ranked_candidates` array (not `candidates`)
- Each candidate has: `title`, `source`, `score`, `url`
- Scores are `0.00` when `use_llm=False` (no LLM ranking applied)
- Only 4 of 18 sources typically return results: reddit, arxiv, lobsters, tickertick

## Working HTTP Call Pattern

```python
import json
import urllib.request

url = "http://127.0.0.1:8770/search"
data = json.dumps({
    "topic": "financial markets macro",
    "n": 10,
    "use_llm": False
}).encode()

req = urllib.request.Request(
    url, 
    data=data, 
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req, timeout=120) as resp:
    result = json.loads(resp.read())
    ranked = result.get('ranked_candidates', [])
```

## Impact Assessment Keywords

Critical keywords for bond policy shock detection (HIGH volatility):
- `debt` → bonds/fx/equities | policy shock
- `hyperinflation` → bonds/fx/equities | policy shock  
- `bond` → bonds/fx/equities | policy shock
- `dollar` → bonds/fx/equities | policy shock
- `economy`, `federal` → bonds/fx/equities | policy shock

Geopolitical risk detection (SPIKE risk-off):
- `war`, `conflict`, `sanction`, `middle east`, `iran`, `israel`

Crypto-specific (MEDIUM-HIGH):
- `crypto`, `bitcoin`, `btc`, `ethereum`, `eth`, `defi`, `binance`, `trading`

Tech sector (RISK-ON):
- `ai`, `tech`, `semiconductor`, `nasdaq`, `chatgpt`, `chatgpt`

## Score Handling

When `use_llm=False`:
- All scores return as `0.00` or missing
- Display as `score: 0.00` in reports
- Ranking still occurs via source weights (polymarket 0.98, metaculus 0.94, reddit 1.15)