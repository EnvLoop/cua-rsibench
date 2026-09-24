"""Versioned Qwen3.8-27B image/text rendering and one-step Tinker smoke.

This uses a generated red square and a toy JSON target. It proves API and
renderer compatibility only; it is not benchmark data or a task score.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time


MODEL = 'Qwen/Qwen3.8-27B'
RENDERER = 'qwen3_5_disable_thinking'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + '\n')
    path.chmod(0o600)


def render_example(model=MODEL):
    from PIL import Image
    from tinker_cookbook import renderers, tokenizer_utils
    from tinker_cookbook.image_processing_utils import get_image_processor
    from tinker_cookbook.renderers import Message, ImagePart, TextPart
    from tinker_cookbook.supervised.data import datum_from_model_input_weights

    image = Image.new('RGB', (112, 112), (220, 40, 40))
    tokenizer = tokenizer_utils.get_tokenizer(model)
    processor = get_image_processor(model)
    renderer = renderers.get_renderer(RENDERER, tokenizer, image_processor=processor)
    user = Message(role='user', content=[ImagePart(type='image', image=image),
        TextPart(type='text', text='Return exactly JSON with one action. This is a disposable visual API smoke.')])
    messages = [user, Message(role='assistant', content='{"action":{"type":"done"}}')]
    model_input, weights = renderer.build_supervised_example(messages)
    prompt = renderer.build_generation_prompt([user])
    if not any(type(chunk).__name__ == 'ImageChunk' for chunk in model_input.chunks):
        raise ValueError('supervised input has no image chunk')
    if not any(type(chunk).__name__ == 'ImageChunk' for chunk in prompt.chunks):
        raise ValueError('sampling prompt has no image chunk')
    if float(weights.sum().item()) <= 0:
        raise ValueError('assistant target has no loss weight')
    datum = datum_from_model_input_weights(model_input, weights, max_length=2048, reduction='none')
    return renderer, prompt, datum, {'image_processor': type(processor).__name__,
        'supervised_chunk_types': [type(chunk).__name__ for chunk in model_input.chunks],
        'sampling_chunk_types': [type(chunk).__name__ for chunk in prompt.chunks],
        'loss_weight_sum': float(weights.sum().item())}


def run(out, paid=False, model=MODEL):
    out = Path(out).resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    out.chmod(0o700)
    renderer, prompt, datum, local = render_example(model)
    receipt = {'schema': 'tinker-vision-compatibility-v1', 'model': model,
        'renderer': RENDERER, 'local_rendering': local,
        'paid_training_requested': bool(paid), 'optimizer_steps_completed': 0,
        'training_and_sampling_verified': False, 'benchmark_score': None}
    write_json(out / 'receipt.json', receipt)
    if not paid:
        return receipt
    if not os.environ.get('TINKER_API_KEY'):
        raise ValueError('Tinker key unavailable; no training started')
    # Exclusive creation prevents a second paid dispatch after a lost response.
    with (out / 'training-intent.json').open('x') as stream:
        json.dump({'model': model, 'rank': 8, 'steps': 1,
                   'created_at': time.time(), 'single_dispatch_only': True}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    import tinker
    from tinker import types
    service = tinker.ServiceClient(user_metadata={'purpose': 'cua-v06-vision-compatibility-smoke'})
    status = 'errored'
    try:
        client = service.create_lora_training_client(base_model=model, rank=8, seed=23)
        backward = client.forward_backward([datum], 'cross_entropy').result(timeout=240)
        client.optim_step(types.AdamParams(learning_rate=1e-4)).result(timeout=240)
        receipt['optimizer_steps_completed'] = 1
        receipt['loss_metrics_available'] = bool(getattr(backward, 'metrics', {}))
        write_json(out / 'receipt.json', receipt)
        checkpoint = client.save_weights_for_sampler('cua-v06-vision-smoke').result(timeout=240)
        private = {'checkpoint_path': checkpoint.path}
        write_json(out / 'private-checkpoint.json', private)
        sampling = service.create_sampling_client(model_path=checkpoint.path)
        result = sampling.sample(prompt=prompt, num_samples=1,
            sampling_params=types.SamplingParams(max_tokens=48, temperature=0,
                seed=23, stop=renderer.get_stop_sequences())).result(timeout=240)
        tokens = result.sequences[0].tokens
        receipt.update(training_and_sampling_verified=True,
            sample_tokens=len(tokens), sample_sha256=hashlib.sha256(bytes(str(tokens), 'utf-8')).hexdigest(),
            checkpoint_saved=True, cost_usd=None)
        write_json(out / 'receipt.json', receipt)
        status = 'success'
        return receipt
    except Exception as exc:
        receipt['failure_type'] = type(exc).__name__
        write_json(out / 'receipt.json', receipt)
        raise
    finally:
        service.close(status).result(timeout=30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--paid-one-step', action='store_true')
    parser.add_argument('--model', default=MODEL,
                        choices=('Qwen/Qwen3.8-27B', 'Qwen/Qwen3.5-4B'))
    args = parser.parse_args()
    result = run(args.out, args.paid_one_step, args.model)
    print(json.dumps({'model': result['model'],
        'image_rendered': 'ImageChunk' in result['local_rendering']['supervised_chunk_types'],
        'optimizer_steps_completed': result['optimizer_steps_completed'],
        'training_and_sampling_verified': result['training_and_sampling_verified'],
        'benchmark_score': None}))


if __name__ == '__main__':
    main()
