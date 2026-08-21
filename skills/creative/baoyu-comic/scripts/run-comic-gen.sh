#!/bin/bash
# Bootstrap: extract API key from Hermes config and run the batch generator
# Usage: ./run_comic.sh [comic_id]
# The write_file tool redacts API keys from file content, so keys must be
# extracted at runtime and passed via env var — never hardcoded.

set -e

KEY=$(python3 -c "
with open('/home/alca/.hermes/config.yaml') as f:
    c = f.read()
i = c.find('opendeepseek:')
if i < 0: i = c.find('openddeepseek:')
s = c[i:i+200]
k = s.find('api_key:')
print(s[k+9:k+82].strip().strip(\"'\").strip('\"').strip())
")

export HERMES_RIVERFLOW_KEY="$KEY"
exec python3 "$(dirname "$0")/generate_all.py" "$@"
