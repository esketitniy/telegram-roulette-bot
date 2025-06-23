web: gunicorn main:app --bind 0.0.0.0:$PORT
worker: python -c "
import asyncio
from main import run_bot
asyncio.run(run_bot())
"
