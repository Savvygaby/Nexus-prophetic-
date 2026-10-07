"""Snapshot XO Sports' public Performance Hub: rendered text, every JSON/XHR response, and admin-ajax/wp-json calls.
Output: logs/xo/{stamp}/ (page.html, page.txt, net_*.json, index.json). No odds credits used."""
import json, os, re, datetime as dt, asyncio
from playwright.async_api import async_playwright
STAMP = dt.datetime.utcnow().strftime('%Y%m%dT%H%MZ')
OUT = f'logs/xo/{STAMP}'; os.makedirs(OUT, exist_ok=True)
PAGES = ['https://xosports.ai/performance-hub/', 'https://xosports.ai/', 'https://xosports.ai/#todays-picks']
async def main():
    idx = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36')
        pg = await ctx.new_page(); n = [0]
        async def on_resp(r):
            try:
                ct = r.headers.get('content-type', '')
                if 'json' in ct or 'admin-ajax' in r.url or 'wp-json' in r.url:
                    body = await r.text(); n[0] += 1
                    fn = f'net_{n[0]:03d}.txt'; open(f'{OUT}/{fn}', 'w').write(body)
                    idx.append(dict(file=fn, url=r.url, status=r.status, ct=ct, method=r.request.method, post=r.request.post_data, size=len(body)))
            except Exception as e: idx.append(dict(err=str(e), url=r.url))
        pg.on('response', on_resp)
        for i, u in enumerate(PAGES):
            try:
                await pg.goto(u, wait_until='networkidle', timeout=60000); await pg.wait_for_timeout(4000)
                # click any "load more"/tabs/date pickers to expose history
                for _ in range(15):
                    btn = pg.locator('text=/load more|show more|view more|older|previous/i')
                    if await btn.count() == 0: break
                    try: await btn.first.click(timeout=3000); await pg.wait_for_timeout(1500)
                    except Exception: break
                open(f'{OUT}/page{i}.html', 'w').write(await pg.content())
                open(f'{OUT}/page{i}.txt', 'w').write(await pg.inner_text('body'))
            except Exception as e: idx.append(dict(page=u, err=str(e)))
        # try WordPress REST discovery too
        for u in ['https://xosports.ai/wp-json/', 'https://xosports.ai/wp-json/wp/v2/types']:
            try:
                r = await ctx.request.get(u, timeout=30000); t = await r.text(); n[0] += 1
                fn = f'net_{n[0]:03d}.txt'; open(f'{OUT}/{fn}', 'w').write(t); idx.append(dict(file=fn, url=u, status=r.status, size=len(t)))
            except Exception as e: idx.append(dict(url=u, err=str(e)))
        await b.close()
    json.dump(idx, open(f'{OUT}/index.json', 'w'), indent=1)
    print(len(idx), 'captured')
asyncio.run(main())
