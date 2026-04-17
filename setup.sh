#!/bin/bash
set -e
echo "Setting up TikTok Hashtag Collector..."
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
mkdir -p output logs
echo "Setup complete! Edit config.yaml and run: python main.py fetch --help"
