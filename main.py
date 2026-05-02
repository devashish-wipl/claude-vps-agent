#!/usr/bin/env python3
"""Entrypoint: `python main.py <host> '<request>'`"""
from dotenv import load_dotenv

load_dotenv()  # populate ANTHROPIC_API_KEY etc. from .env if present

from agent.core import main_cli

if __name__ == "__main__":
    main_cli()
