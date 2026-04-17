@echo off
echo Setting up TikTok Hashtag Collector...
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
mkdir output 2>nul
mkdir logs 2>nul
echo Setup complete! Edit config.yaml and run: python main.py fetch --help
