"""Additive real SDK setup; no HTTP or sampling retry in any Qwen slot."""
from __future__ import annotations
import time
from cursibench.scale_vision_proxy import MODEL, QwenVisionRenderer, TinkerVisionBackend, campaign_metadata, digest


def sampler_class(selection):
    class Sampler(selection.RealTinkerSelectionSampler):
        def __enter__(self):
            import tinker
            from tinker.lib.retry_handler import RetryConfig
            self.lifecycle_started_monotonic=time.monotonic()
            if type(self.base_mode) is not bool:
                raise selection.SelectionWorkerError('selection_sampling_mode_invalid')
            if self.base_mode:
                if self.checkpoint_path!=MODEL or self.expected_base_checkpoint_sha256!=digest(MODEL):
                    raise selection.SelectionWorkerError('selection_base_checkpoint_unbound')
            elif type(self.checkpoint_path) is not str or selection.campaign.TINKER_PATH.fullmatch(self.checkpoint_path) is None:
                raise selection.SelectionWorkerError('selection_checkpoint_path_invalid')
            self.renderer=QwenVisionRenderer.load()
            self.service=tinker.ServiceClient(max_retries=0,user_metadata=campaign_metadata('odoo-v22-'+digest(self.attempt_id)[:12]))
            try:
                client=self.service.create_sampling_client(retry_config=RetryConfig(enable_retry_logic=False),**(
                    {'base_model':MODEL} if self.base_mode else {'model_path':self.checkpoint_path}))
                if client.get_base_model()!=MODEL:
                    raise selection.SelectionWorkerError('selection_sampler_base_model_changed')
                self.backend=TinkerVisionBackend(client,self.renderer,checkpoint=None if self.base_mode else self.checkpoint_path,seed=self.config['seed'])
                expected=digest(MODEL if self.base_mode else self.checkpoint_path)
                if self.backend.identity.get('sampling_kind')!=('base' if self.base_mode else 'checkpoint') or self.backend.identity.get('checkpoint_sha256')!=expected:
                    raise selection.SelectionWorkerError('selection_sampler_checkpoint_changed')
            except Exception:
                try:self.service.close('errored').result(timeout=30)
                finally:self.service=None
                raise
            return self
    return Sampler
