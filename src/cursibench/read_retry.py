"""Bounded transport recovery for two audited, application-read-only commands."""
import asyncio

READ_COMMANDS=frozenset({
    'curl -sf http://127.0.0.1:4318/observe',
    'python /app/kanboard_seed.py /app/final-db.json',
})
TRANSPORT_ERRORS=frozenset({'TimeoutException','TimeoutError','ConnectError',
                           'ReadError','RemoteProtocolError','ReadTimeout',
                           'ConnectTimeout','WriteError','WriteTimeout'})


async def retry_read(command,call,on_retry=lambda *_:None,sleep=asyncio.sleep):
    """Never redispatch a GUI action, setup command, or arbitrary shell command."""
    attempts=3 if command in READ_COMMANDS else 1
    for attempt in range(attempts):
        try:return await call()
        except Exception as exc:
            transient=type(exc).__name__ in TRANSPORT_ERRORS or str(exc)=='Command ended without an end event'
            if not transient or attempt+1==attempts:raise
            on_retry(attempt+1,type(exc).__name__)
            await sleep(1+attempt)
