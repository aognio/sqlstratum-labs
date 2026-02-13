#!/usr/bin/env bash
set -euo pipefail
export FLASK_APP=clinicdesk.app
export FLASK_ENV=development

SQLSTRATUM_DEBUG="${SQLSTRATUM_DEBUG:-}"
ARGS=()
for arg in "$@"; do
  if [[ "$arg" == "--debug" ]]; then
    SQLSTRATUM_DEBUG="1"
  else
    ARGS+=("$arg")
  fi
done

if [[ -n "$SQLSTRATUM_DEBUG" ]]; then
  export SQLSTRATUM_DEBUG
fi

if ((${#ARGS[@]})); then
  flask run -p 5001 "${ARGS[@]}"
else
  flask run -p 5001
fi
