#!/bin/sh
set -e

# The LLM used by the rails is reached through Requesty's OpenAI-compatible
# router: the API key comes from the standard OPENAI_API_KEY variable and
# the router URL is substituted into the configs as base_url below.
export OPENAI_API_KEY="${REQUESTY_API_KEY:-missing-key}"

MODEL_NAME="${MODEL_NAME:-openai/gpt-4.1-mini}"
BASE_URL="${BASE_URL:-https://router.requesty.ai/v1}"

# Copy the mounted configs so we can substitute values without touching the
# files on the host.
rm -rf /run-config
cp -r /config-src /run-config
find /run-config -name 'config.yml' -exec sed -i \
  -e "s|__MODEL_NAME__|${MODEL_NAME}|g" \
  -e "s|__BASE_URL__|${BASE_URL}|g" {} +

echo "Starting NeMo Guardrails server (model: ${MODEL_NAME})"
exec nemoguardrails server --config=/run-config --port=8000
