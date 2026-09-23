"""Reusable HTTPS pool, respecting proxy env; retries only before POST dispatch."""
import atexit,threading,time
import httpx
_lock=threading.Lock()
_client=None

def client():
    global _client
    with _lock:
        if _client is None:
            limits=httpx.Limits(max_connections=8,max_keepalive_connections=8,keepalive_expiry=120)
            _client=httpx.Client(http2=True,limits=limits,follow_redirects=False)
        return _client

def post_json(url,payload,headers,timeout):
    for attempt in range(3):
        try:
            response=client().post(url,json=payload,headers=headers,
                timeout=httpx.Timeout(timeout,connect=min(20,timeout),pool=min(20,timeout),write=min(20,timeout)))
            response.raise_for_status()
            body=response.json()
            if isinstance(body,dict):body['__cua_transport']={'connect_attempts':attempt+1}
            return body
        except (httpx.ConnectError,httpx.ConnectTimeout):
            if attempt==2:raise
            time.sleep(.5*(2**attempt))

def close():
    global _client
    if _client is not None:_client.close();_client=None
atexit.register(close)
