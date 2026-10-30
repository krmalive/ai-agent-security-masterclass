#!/usr/bin/env bash
# Source this file, rather than executing it, to configure the current terminal.
set +x
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo 'Use: source scripts/load-requesty.sh /root/openai-creds.txt' >&2
  exit 1
fi
lab_requesty_file="${1:-/root/openai-creds.txt}"
unset lab_key lab_base
if [[ ! -r "$lab_requesty_file" ]]; then echo 'Credential file is missing. Run asectl init llm first.' >&2; return 1; fi
while IFS= read -r lab_line || [[ -n "$lab_line" ]]; do
  lab_line="${lab_line%$'\r'}"
  case "$lab_line" in
    REQUESTY_API_KEY=*) lab_key="${lab_line#*=}" ;;
    BASE_URL=*) lab_base="${lab_line#*=}" ;;
  esac
done < "$lab_requesty_file"
lab_key="${lab_key:-}"; lab_base="${lab_base:-}"
lab_key="${lab_key#\"}"; lab_key="${lab_key%\"}"; lab_key="${lab_key#\'}"; lab_key="${lab_key%\'}"
lab_base="${lab_base#\"}"; lab_base="${lab_base%\"}"; lab_base="${lab_base#\'}"; lab_base="${lab_base%\'}"
lab_base="${lab_base%/}"; lab_base="${lab_base%/v1}"
if [[ -z "$lab_key" || ( "$lab_base" != 'https://router.requesty.ai' && "$lab_base" != 'https://router.eu.requesty.ai' ) ]]; then
  unset lab_key lab_base lab_line lab_requesty_file
  echo 'Expected REQUESTY_API_KEY and an official Requesty BASE_URL.' >&2; return 1
fi
unset ANTHROPIC_API_KEY ANTHROPIC_CUSTOM_HEADERS
export ANTHROPIC_AUTH_TOKEN="$lab_key"
export ANTHROPIC_BASE_URL="$lab_base"
export ANTHROPIC_MODEL='gpt-5.6-luna'
export ANTHROPIC_DEFAULT_HAIKU_MODEL="$ANTHROPIC_MODEL"
export ANTHROPIC_DEFAULT_SONNET_MODEL="$ANTHROPIC_MODEL"
export ANTHROPIC_DEFAULT_OPUS_MODEL="$ANTHROPIC_MODEL"
export ANTHROPIC_SMALL_FAST_MODEL="$ANTHROPIC_MODEL"
export API_TIMEOUT_MS=300000
unset lab_key lab_base lab_line lab_requesty_file
echo 'Claude Code configured for GPT 5.6 Luna through Requesty. Credential value was not printed.'
