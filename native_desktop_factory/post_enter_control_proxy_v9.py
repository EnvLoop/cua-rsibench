"""Neutral Calc Enter settling for a fresh prospective control source epoch.

Five timestamped, no-input captures preserve the TRAIN v6 timing/window rule.
The next actor still obtains a fresh observation and exact predispatch check.
No task identity, gold or saved-file result influences this transport policy.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import time
from .post_enter_train_probe_v1 import SAMPLE_DELAYS_MS, MAX_PROBE_WALL_MS, _append_fsynced
from .qwen_v064_adapter import application_frame_digest
from .v066_storage_budget import reserve_and_write

MAX_ENTER_WINDOWS = 90


class PostEnterControlProxyV9:
    def __init__(self,sandbox,*,storage_root:Path,attempt_dir:Path,document_filename:str,
                 clock=time.monotonic_ns,sleep=time.sleep):
        if (not attempt_dir.is_dir() or attempt_dir.is_symlink() or
                attempt_dir.resolve().parent.parent!=storage_root.resolve() or
                not document_filename.endswith((".xlsx",".pptx",".docx"))):
            raise ValueError("Prospective control attempt scope invalid")
        self.sandbox=sandbox;self.storage_root=storage_root;self.attempt_dir=attempt_dir
        self.document_filename=document_filename;self.clock=clock;self.sleep=sleep
        self.enter_count=0;self.current_actor_step=None

    def __getattr__(self,name):return getattr(self.sandbox,name)

    def press(self,key):
        if str(key).lower() not in ("enter","return") or not self.document_filename.endswith(".xlsx"):
            return self.sandbox.press(key)
        if self.enter_count>=MAX_ENTER_WINDOWS or type(self.current_actor_step) is not int:
            raise ValueError("Prospective Enter window bound/actor step absent")
        prior_id=self.sandbox.get_current_window_id();prior_title=self.sandbox.get_window_title(prior_id)
        if self.document_filename not in prior_title:
            raise ValueError("Calc document/modal boundary changed before Enter")
        result=self.sandbox.press(key);ordinal=self.enter_count;self.enter_count+=1
        start=self.clock();application_hashes=[]
        for sample,delay in enumerate(SAMPLE_DELAYS_MS):
            if delay:self.sleep(delay/1000)
            before=self.clock();first_id=self.sandbox.get_current_window_id();first_title=self.sandbox.get_window_title(first_id)
            raw=bytes(self.sandbox.screenshot())
            second_id=self.sandbox.get_current_window_id();second_title=self.sandbox.get_window_title(second_id);after=self.clock()
            ref=reserve_and_write(self.storage_root,self.attempt_dir/f"post-enter-{ordinal:02d}-{sample:02d}.png",raw)
            row={"schema":"cua-native-wdi-post-enter-control-sample-v9","enter_ordinal":ordinal,
                 "preceding_actor_step":self.current_actor_step,"sample":sample,
                 "requested_delay_ms_before_sample":delay,"captured_utc":datetime.now(timezone.utc).isoformat(),
                 "monotonic_before_ns":before,"monotonic_after_ns":after,"elapsed_since_enter_ns":after-start,
                 "frame":ref,"full_frame_sha256":sha256(raw).hexdigest(),
                 "application_frame_sha256":application_frame_digest(raw),
                 "window_id_before_sha256":sha256(first_id.encode()).hexdigest(),
                 "window_id_after_sha256":sha256(second_id.encode()).hexdigest(),
                 "window_title_before_sha256":sha256(first_title.encode()).hexdigest(),
                 "window_title_after_sha256":sha256(second_title.encode()).hexdigest(),
                 "document_window_stable":first_id==second_id==prior_id and self.document_filename in first_title and self.document_filename in second_title}
            _append_fsynced(self.attempt_dir/"post-enter-samples.ndjson",row)
            application_hashes.append(row["application_frame_sha256"])
            if (not row["document_window_stable"] or before<start or after<before or
                    after-start>MAX_PROBE_WALL_MS*1_000_000):
                raise ValueError("Post-Enter document/modal/time boundary changed")
        transitions=[]
        for value in application_hashes:
            if not transitions or value!=transitions[-1]:transitions.append(value)
        if (application_hashes[-2]!=application_hashes[-1] or len(transitions)>2 or
                len(transitions)!=len(set(transitions)) or after-start<sum(SAMPLE_DELAYS_MS)*1_000_000):
            raise ValueError("Post-Enter application oscillated or did not settle")
        return result
