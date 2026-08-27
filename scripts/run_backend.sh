#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../backend"
pip install -r requirements.txt
python -m app.services.seed
uvicorn app.main:app --reload
