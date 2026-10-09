"""Zero-shot AI time-series forecasts (Amazon Chronos-Bolt) of each player's next-game stat from his past games. Output: quantiles per row."""
import json, numpy as np, torch
from chronos import BaseChronosPipeline
rows = json.load(open('research/chronos_in.json'))
out = {}
for name in ('amazon/chronos-bolt-small', 'amazon/chronos-bolt-base'):
    pipe = BaseChronosPipeline.from_pretrained(name, device_map='cpu', torch_dtype=torch.float32)
    QS = [.1, .2, .3, .4, .5, .6, .7, .8, .9]
    for i in range(0, len(rows), 256):
        b = rows[i:i + 256]
        ctx = [torch.tensor(r['series'], dtype=torch.float32) for r in b]
        q, _ = pipe.predict_quantiles(ctx, prediction_length=1, quantile_levels=QS)
        for r, qq in zip(b, q): out.setdefault(r['key'], {})[name.split('/')[-1]] = [round(float(v), 2) for v in qq[0]]
    print(name, 'done', flush=True)
json.dump(out, open('research/chronos_out.json', 'w'))
