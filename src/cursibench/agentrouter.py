"""Responses transport with redacted receipts and bounded requests.

Prices are intentionally unknown unless supplied by the account owner. A reported
model ID is provider metadata, not an independently established model identity.
"""
import json
import os
import time
import httpx
from .http_transport import post_json

MODEL_CHOICES = ('gpt-6-astra', 'gpt-5.6-sol')

class ProviderFailure(RuntimeError):
    def __init__(self, kind, receipt):
        super().__init__(kind)
        self.receipt = receipt


def response_receipt(prompt, model='gpt-6-astra', max_output_tokens=900, timeout=60):
    if model not in MODEL_CHOICES:
        raise ValueError('model outside registered choices')
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise RuntimeError('OPENAI_API_KEY is not set')
    base = os.environ.get('OPENAI_BASE_URL', 'https://sub2api.agentrouterhub.com').rstrip('/')
    endpoint = base + ('/responses' if base.endswith('/v1') else '/v1/responses')
    payload = {'model': model, 'input': prompt, 'max_output_tokens': max_output_tokens, 'store': False, 'reasoning': {'effort':'low'}}
    started = time.monotonic()
    receipt = {'requested_model': model, 'max_output_tokens': max_output_tokens,
               'input_bytes': len(prompt.encode()), 'cost_usd': None, 'usage': None}
    try:
        body=post_json(endpoint,payload,{
            'Authorization': f'Bearer {key}', 'Content-Type':'application/json',
            'User-Agent':'cua-rsibench/0.4'},timeout)
        receipt['transport']='pooled_httpx_http2_connect_retries_2'
        receipt['connect_attempts']=body.get('__cua_transport',{}).get('connect_attempts')
        receipt.update({'response_id': body.get('id'), 'reported_model': body.get('model'),
                        'status': body.get('status'), 'usage': body.get('usage')})
        if body.get('error') or body.get('status') not in ('completed','incomplete'):
            raise ValueError('provider returned incomplete or failed response')
        text = '\n'.join(c['text'] for i in body.get('output', []) if i.get('type') == 'message'
                         for c in i.get('content', []) if c.get('type') == 'output_text')
        if not text and body.get('status')=='incomplete':text='[OUTPUT_TOKEN_LIMIT]'
        if not text:
            raise ValueError('empty output')
        receipt['elapsed_seconds'] = time.monotonic() - started
        return text, receipt
    except Exception as exc:
        receipt['elapsed_seconds'] = time.monotonic() - started
        receipt['network_reason_type']=type(exc).__name__
        if isinstance(exc,httpx.HTTPStatusError):receipt['error']=f'http_{exc.response.status_code}'
        elif isinstance(exc,httpx.TimeoutException):receipt['error']='TimeoutError'
        elif isinstance(exc,httpx.TransportError):receipt['error']='URLError'
        else:receipt['error']=type(exc).__name__
        # Never persist provider response bodies or auth headers.
        raise ProviderFailure(receipt['error'], receipt) from None


def responses_call(prompt, model='gpt-6-astra', max_output_tokens=900):
    return response_receipt(prompt, model, max_output_tokens)[0]
