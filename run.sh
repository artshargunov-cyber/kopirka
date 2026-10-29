#!/bin/bash
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/.venv/lib/python3.9/site-packages"
python3 main.py
