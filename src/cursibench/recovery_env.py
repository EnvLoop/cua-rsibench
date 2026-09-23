"""Versioned transport-only recovery; frozen actor/observer/verifier unchanged."""
from .cloud_env import BoundedE2B
from .read_retry import retry_read


class ReadRetryE2B(BoundedE2B):
    async def exec(self,command,**kwargs):
        async def once():return await super(ReadRetryE2B,self).exec(command,**kwargs)
        def log(attempt,error):
            self.logger.warning('CUA_READ_RETRY attempt=%s type=%s',attempt,error)
        return await retry_read(command,once,log)
