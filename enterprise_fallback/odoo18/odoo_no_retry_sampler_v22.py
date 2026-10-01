"""Additive real SDK setup; no HTTP or sampling retry in any Qwen slot."""
from __future__ import annotations
from hashlib import sha256
import importlib
from pathlib import Path
import time


def sampler_class(selection):
    # Resolve exactly the current production sampler's public vision namespace.
    # External command hashes use literal UTF-8; backend identities use its
    # separately defined JSON-value digest. Those are distinct evidence fields.
    vision=importlib.import_module('cursibench.scale_vision_proxy')
    root=Path(__file__).resolve().parents[2]
    if (Path(vision.__file__).resolve()!=root/'src/cursibench/scale_vision_proxy.py' or
        selection.QWEN_MODEL!='Qwen/Qwen3.8-27B' or vision.MODEL!=selection.QWEN_MODEL or
        selection.vision_digest is not vision.digest):
        raise selection.SelectionWorkerError('selection_checked_vision_namespace_changed')
    model=selection.QWEN_MODEL
    class Sampler(selection.RealTinkerSelectionSampler):
        def __enter__(self):
            import tinker
            from tinker.lib.retry_handler import RetryConfig
            self.lifecycle_started_monotonic=time.monotonic()
            if type(self.base_mode) is not bool:
                raise selection.SelectionWorkerError('selection_sampling_mode_invalid')
            if self.config.get('model')!=model:
                raise selection.SelectionWorkerError('selection_configured_model_changed')
            if self.base_mode:
                command_identity=sha256(model.encode()).hexdigest()
                if self.checkpoint_path!=model or self.expected_base_checkpoint_sha256!=command_identity:
                    raise selection.SelectionWorkerError('selection_base_checkpoint_unbound')
            elif type(self.checkpoint_path) is not str or selection.campaign.TINKER_PATH.fullmatch(self.checkpoint_path) is None:
                raise selection.SelectionWorkerError('selection_checkpoint_path_invalid')
            self.renderer=vision.QwenVisionRenderer.load()
            self.service=tinker.ServiceClient(max_retries=0,user_metadata=vision.campaign_metadata('odoo-v22-'+selection._hash(self.attempt_id.encode())[:12]))
            try:
                client=self.service.create_sampling_client(retry_config=RetryConfig(enable_retry_logic=False),**(
                    {'base_model':model} if self.base_mode else {'model_path':self.checkpoint_path}))
                if client.get_base_model()!=model:
                    raise selection.SelectionWorkerError('selection_sampler_base_model_changed')
                self.backend=vision.TinkerVisionBackend(client,self.renderer,checkpoint=None if self.base_mode else self.checkpoint_path,seed=self.config['seed'])
                backend_identity=selection.vision_digest(model if self.base_mode else self.checkpoint_path)
                if self.backend.identity.get('sampling_kind')!=('base' if self.base_mode else 'checkpoint') or self.backend.identity.get('checkpoint_sha256')!=backend_identity:
                    raise selection.SelectionWorkerError('selection_sampler_checkpoint_changed')
            except Exception:
                try:self.service.close('errored').result(timeout=30)
                finally:self.service=None
                raise
            return self
    return Sampler
