#!/usr/bin/env bash
# riverflow-quota-diagnostic.sh
# Quick test: is riverflow quota available or exhausted?
# Exit 0 = quota OK, exit 1 = rate limited, exit 2 = other error
# Usage: bash riverflow-quota-diagnostic.sh

KEY=$(python3 -c "
with open('/home/alca/.hermes/config.yaml') as f:
    c = f.read()
i = c.find('opendeepseek:')
if i < 0: i = c.find('openddeepseek:')
s = c[i:i+200]
k = s.find('api_key:')
print(s[k+9:k+82].strip().strip(\"'\").strip('\"').strip())
")

python3 -c "
import json, tempfile, subprocess, os, sys

body = json.dumps({
    'model': 'sourceful/riverflow-v2.5-pro:free',
    'reasoning': {'effort': 'high'},
    'messages': [{'role': 'user', 'content': 'A single blue circle on white background.'}],
    'max_tokens': 500
})
pf = tempfile.mktemp(suffix='.json')
with open(pf, 'w') as f: f.write(body)
rf = tempfile.mktemp(suffix='.json')

auth = 'Authorization: ' + 'Bearer ' + os.environ.get('HERMES_RIVERFLOW_KEY', '')
if not auth:
    print('ERROR: No key found')
    sys.exit(2)

result = subprocess.run(
    ['curl', '-s', '--max-time', '60',
     '-H', 'Content-Type: application/json',
     '-H', auth,
     '-d', '@' + pf,
     'https://openrouter.ai/api/v1/chat/completions',
     '-o', rf],
    capture_output=True, text=True, timeout=70)
os.unlink(pf)

with open(rf) as f: data = f.read()
os.unlink(rf)

if not data.strip():
    print('EMPTY — provider may be down')
    sys.exit(2)

d = json.loads(data)
if 'error' in d:
    err = str(d.get('error', {}))
    if 'rate' in err.lower() or 'limit' in err.lower() or 'daily' in err.lower():
        print('RATE LIMITED — daily quota exhausted')
        sys.exit(1)
    else:
        print(f'OTHER ERROR: {err[:100]}')
        sys.exit(2)
elif d.get('choices'):
    print('QUOTA OK — riverflow is live')
    sys.exit(0)
else:
    print('UNKNOWN RESPONSE')
    sys.exit(2)
" 2>&1

exit $?
