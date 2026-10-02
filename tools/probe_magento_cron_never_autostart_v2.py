"""Train-only Magento startup probe with cron disabled before supervisord."""

from __future__ import annotations

import hashlib
import json
import os

from magento_catalog_factory.plan import ROOT
from tools.start_magento_native_sidecar_clone_v1 import prepare

EXPECTED_SEARCH = '54ca1d8ef5cb82ed879338e6740a589a930e50cd8a54f495c234c5f5b0acf6fb'
OUT = ROOT / 'work/magento-original/cron-never-autostart-train-probe-20260927-v2'


def main() -> None:
    OUT.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(OUT, 0o700)
    try:
        result = prepare(EXPECTED_SEARCH,
                         train_probe_disable_cron_autostart=True)
        result.update({'schema': 'envloop-magento-cron-never-autostart-train-probe-v2',
                       'split': 'train_only', 'model_calls': 0,
                       'official_final_tasks_admitted': 0})
        raw = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode()
        fd = os.open(OUT / 'startup.private.json',
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
        print(json.dumps({'status': 'unseeded_cron_never_autostart_probe_ready',
                          'receipt_sha256': hashlib.sha256(raw).hexdigest(),
                          'search_document_count': result['search_document_count'],
                          'price_changed_rows_at_all_stages': [
                              row['price_changed_rows'] for row in
                              result['train_probe_price_stages'].values()],
                          'official_final_admitted': 0}, sort_keys=True))
    except Exception as error:
        failure = {'schema': 'envloop-magento-cron-never-autostart-train-failure-v2',
                   'error_type': type(error).__name__,
                   'error_message_sha256': hashlib.sha256(str(error).encode()).hexdigest(),
                   'model_calls': 0, 'official_final_admitted': 0}
        fd = os.open(OUT / 'startup-failure.private.json',
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write((json.dumps(failure, sort_keys=True, indent=2) + '\n').encode())
        raise


if __name__ == '__main__':
    main()
