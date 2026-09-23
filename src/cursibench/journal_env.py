"""Transport recovery via durable logical-command IDs, without repeated GUI effects."""
import asyncio,base64,re,uuid
from pathlib import Path
from .cloud_env import BoundedE2B
from .read_retry import READ_COMMANDS,TRANSPORT_ERRORS

ACTION_COMMAND=re.compile(r"printf %s '[A-Za-z0-9+/=]+' \| base64 -d \| curl -sf -X POST --data-binary @- http://127\.0\.0\.1:4318/act")


class JournalE2B(BoundedE2B):
    async def _create_sandbox(self):
        await super()._create_sandbox()
        await self._sandbox.files.write('/tmp/cua_command_journal.py',Path(__file__).with_name('command_journal.py').read_text())

    async def exec(self,command,**kwargs):
        if command not in READ_COMMANDS and not ACTION_COMMAND.fullmatch(command):
            return await super().exec(command,**kwargs)
        request_id=uuid.uuid4().hex
        encoded=base64.b64encode(command.encode()).decode()
        seconds=kwargs.get('timeout_sec') or 20
        wrapped=f"python /tmp/cua_command_journal.py --root /tmp/cua-command-journal --request-id {request_id} --command-b64 '{encoded}' --timeout {seconds}"
        options=dict(kwargs,timeout_sec=seconds+10)
        for attempt in range(3):
            try:
                result=await super().exec(wrapped,**options)
                if result.return_code==75:raise RuntimeError('journal detected uncertain effects or request collision')
                return result
            except Exception as exc:
                transient=type(exc).__name__ in TRANSPORT_ERRORS or str(exc)=='Command ended without an end event'
                if not transient or attempt==2:raise
                self.logger.warning('CUA_JOURNAL_RETRY id=%s attempt=%s error=%s',request_id,attempt+1,type(exc).__name__)
                await asyncio.sleep(attempt+1)
