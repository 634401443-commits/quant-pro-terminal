import asyncio
import aiohttp
import ssl
import os
import socket

async def test():
    print("HTTP_PROXY:", os.environ.get('HTTP_PROXY', 'not set'))
    print("HTTPS_PROXY:", os.environ.get('HTTPS_PROXY', 'not set'))
    print("http_proxy:", os.environ.get('http_proxy', 'not set'))

    print("\nDNS resolution:")
    try:
        ip = socket.getaddrinfo('qt.gtimg.cn', 80)
        print("qt.gtimg.cn resolved to:", ip[0][4])
    except Exception as e:
        print("DNS FAIL:", str(e))

    print("\nTest 1: aiohttp default")
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as s:
            async with s.get('http://qt.gtimg.cn/q=sz000001', 
                           headers={"User-Agent": "Mozilla/5.0"}, 
                           timeout=aiohttp.ClientTimeout(total=15)) as r:
                text = await r.text(encoding='gbk', errors='ignore')
                print("SUCCESS:", repr(text[:100]))
    except Exception as e:
        print("FAIL:", type(e).__name__, str(e))
        import traceback
        traceback.print_exc()

    print("\nTest 2: urllib")
    try:
        import urllib.request
        resp = urllib.request.urlopen('http://qt.gtimg.cn/q=sz000001', timeout=15)
        print("SUCCESS:", resp.read()[:100])
    except Exception as e:
        print("FAIL:", type(e).__name__, str(e))

    print("\nTest 3: aiohttp with TraceConfig")
    try:
        trace = aiohttp.TraceConfig()
        async def on_request_start(session, ctx, params):
            print("  request start:", params.url)
        async def on_request_end(session, ctx, params):
            print("  request end:", params.url, params.response.status)
        async def on_request_exception(session, ctx, params):
            print("  request exception:", params.url, type(params.exception).__name__)
        trace.on_request_start.append(on_request_start)
        trace.on_request_end.append(on_request_end)
        trace.on_request_exception.append(on_request_exception)
        
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), trace_configs=[trace]) as s:
            async with s.get('http://qt.gtimg.cn/q=sz000001', 
                           headers={"User-Agent": "Mozilla/5.0"}, 
                           timeout=aiohttp.ClientTimeout(total=15)) as r:
                text = await r.text(encoding='gbk', errors='ignore')
                print("SUCCESS:", repr(text[:100]))
    except Exception as e:
        print("FAIL:", type(e).__name__, str(e))

asyncio.run(test())