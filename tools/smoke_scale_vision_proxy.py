"""One bounded paid sampling smoke for the versioned Qwen3.8 vision proxy.

Uses a generated non-benchmark image. The private journal provides exactly-once
intent handling; stdout is an allowlisted receipt without model text or keys.
"""
import argparse
import io
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw

from cursibench.scale_vision_proxy import (
    Limits, QwenVisionRenderer, TinkerVisionBackend, VisionSamplingAdapter,
    public_receipt,
)


def image_bytes():
    image = Image.new('RGB', (128, 128), (255, 255, 255))
    ImageDraw.Draw(image).rectangle((32, 32, 96, 96), fill=(25, 95, 165))
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get('TINKER_API_KEY'):
        raise SystemExit('TINKER_API_KEY is required; no provider call made')
    import tinker
    renderer = QwenVisionRenderer.load()
    service = tinker.ServiceClient(user_metadata={'purpose': 'scale-vision-proxy-paid-smoke-v1'})
    status = 'errored'
    try:
        backend = TinkerVisionBackend.from_service(service, renderer)
        adapter = VisionSamplingAdapter(backend, args.journal,
            limits=Limits(output_tokens=16, max_actions=1, request_timeout_seconds=120))
        result = adapter.sample(request_id='vision-proxy-smoke-20260924',
            image_bytes=image_bytes(), instruction='Look at the image. Reply with one short English color name.',
            visible_text='Disposable synthetic image compatibility check.')
        print(json.dumps(public_receipt(result), sort_keys=True), flush=True)
        status = 'success' if result['status'] == 'completed' else 'errored'
        raise SystemExit(0 if status == 'success' else 1)
    finally:
        try:
            service.close(status).result(timeout=30)
        except Exception:
            pass


if __name__ == '__main__':
    main()
