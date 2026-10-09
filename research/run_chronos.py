"""Zero-shot AI time-series forecasts (Amazon Chronos-Bolt) of each player's next-game stat from his past games. Output: quantiles per row."""
import json, traceback, sys
out = {}
try:
    import torch
    from chronos import BaseChronosPipeline
except Exception:
    json.dump({'_errors': [traceback.format_exc()]}, open('research/chronos_out.json', 'w')); raise
rows = json.load(open('research/chronos_in.json'))
for name in ('amazon/chronos-bolt-small', 'amazon/chronos-bolt-base'):
  try:
    pipe = BaseChronosPipeline.from_pretrained(name, device_map='cpu')
    QS = [.1, .2, .3, .4, .5, .6, .7, .8, .9]
    for i in range(0, len(rows), 256):
        b = rows[i:i + 256]
        ctx = [torch.tensor(r['series'], dtype=torch.float32) for r in b]
        q, _ = pipe.predict_quantiles(ctx, prediction_length=1, quantile_levels=QS)
        for r, qq in zip(b, q): out.setdefault(r['key'], {})[name.split('/')[-1]] = [round(float(v), 2) for v in qq[0]]
    print(name, 'done', flush=True)
  except Exception:
    out.setdefault('_errors', []).append(traceback.format_exc()[-3000:]); print(traceback.format_exc(), flush=True)
json.dump(out, open('research/chronos_out.json', 'w'))
