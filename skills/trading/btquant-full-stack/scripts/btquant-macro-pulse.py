#!/usr/bin/env python3
"""BTQuant Macro Trend Extractor - hourly cron job script
Fixed: use rankd_candidates instead of candidates, handle missing scores
"""
import json
import urllib.request
from datetime import datetime

PULSE_URL = "http://127.0.0.1:8770/search"

def assess_impact(title: str) -> dict:
    """Map trend to market impact and BTQuant signal sources"""
    t = title.lower()
    
    # Bond/policy shock - highest priority
    if any(x in t for x in ['fed', 'federal reserve', 'interest', 'inflation', 'policy', 
                             'ecb', 'central bank', 'rates', 'bond', 'debt', 'dollar',
                             'hyperinflation', 'treasury']):
        return {
            'assets': 'bonds/fx/equities',
            'volatility': 'HIGH (policy shock)',
            'btq_sources': 'HotSpine WH futures delta, correlation_heatmap, liquidity_imbalance detector'
        }
    # Geopolitical risk
    elif any(x in t for x in ['war', 'conflict', 'geopolitical', 'sanction', 
                               'middle east', 'iran', 'israel', 'risk-off', 'riskoff']):
        return {
            'assets': 'oil, gold, safe havens, USD',
            'volatility': 'SPIKE risk-off',
            'btq_sources': 'whale_frontrun detector, liquidity_imbalance detector'
        }
    # Crypto-specific
    elif any(x in t for x in ['crypto', 'bitcoin', 'btc', 'ethereum', 'eth', 
                               'defi', 'binance', 'bingx', 'trading', 'arbitrage']):
        return {
            'assets': 'crypto market-wide',
            'volatility': 'MEDIUM-HIGH',
            'btq_sources': 'Binance HotSpine /dev/shm/BTQ, spread_arbitrage detector'
        }
    # Tech sector
    elif any(x in t for x in ['ai', 'tech', 'semiconductor', 'nasdaq', 'chatgpt', 'openai']):
        return {
            'assets': 'tech stocks, crypto beta',
            'volatility': 'RISK-ON',
            'btq_sources': 'correlation_heatmap vs tech, microstructure_renderer'
        }
    else:
        return {
            'assets': 'monitoring',
            'volatility': 'neutral',
            'btq_sources': 'watchlist_panel monitoring'
        }

def run_macro_pulse() -> str:
    """Execute pulse search and format BTQuant trading report"""
    
    data = json.dumps({
        "topic": "global macro financial markets geopolitics crypto equities bonds commodities",
        "n": 10,
        "use_llm": False
    }).encode()
    
    req = urllib.request.Request(
        PULSE_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            # FIXED: use ranked_candidates, not candidates
            candidates = result.get('ranked_candidates', [])[:5]
    except Exception as e:
        return f"❌ PULSE ERROR: {e}"
    
    lines = ["📊 **Hourly Macro Pulse — BTQuant Trading Feed**\n"]
    
    for i, c in enumerate(candidates, 1):
        title = c.get('title', 'N/A')[:75]
        source = c.get('source', 'unknown')
        url = c.get('url', '')
        
        impact = assess_impact(title)
        
        lines.append(f"**{i}. {title}** `{source}` (score: 0.00)")
        lines.append(f"   Assets: {impact['assets']} | Vol: {impact['volatility']}")
        lines.append(f"   BTQ: {impact['btq_sources']}")
        if url:
            lines.append(f"   {url[:100]}")
        lines.append("")
    
    return '\n'.join(lines)

if __name__ == "__main__":
    print(run_macro_pulse())