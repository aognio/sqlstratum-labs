#!/usr/bin/env bash
set -euo pipefail

export BOOKINGLAB_ENV=development

uvicorn bookinglab.app:app --reload --port 5002
