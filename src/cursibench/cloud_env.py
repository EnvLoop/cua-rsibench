"""Harbor 0.23 E2B environment with a bounded TTL compatible with one-hour accounts.

Upstream uses 86400 seconds unconditionally. This adapter requests 1800 seconds;
it changes resource lifecycle only, not tasks, agent observations or scoring.
"""
from e2b import AsyncSandbox
from harbor.environments.e2b import E2BEnvironment
from harbor.models.task.config import NetworkMode

class BoundedE2B(E2BEnvironment):
    async def _create_sandbox(self):
        self._sandbox=await AsyncSandbox.create(
            template=self._template_name,
            metadata={'environment_name':self.environment_name,'session_id':self.session_id},
            envs=self._startup_env(),timeout=1800,
            allow_internet_access=self.network_policy.network_mode!=NetworkMode.NO_NETWORK,
            network=self._sandbox_create_network_options())
