"""
arq worker entry point — works around Python 3.10+ asyncio.get_event_loop() removal.
Usage: python run_tool.py app.tool.ToolSettings
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.set_event_loop(asyncio.new_event_loop())

from arq.cli import cli

cli()
