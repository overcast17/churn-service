import json
import statistics

import httpx

URL = "http://127.0.0.1:8000/v1/predict/batch"
row = json.load(open("valid.json"))


def median_latency(n_rows, repeats=10):
    body = {"rows": [row] * n_rows}
    httpx.post(URL, json=body)  
    return statistics.median(
        httpx.post(URL, json=body).json()["latency_ms"] for _ in range(repeats)
    )


results = {n: median_latency(n) for n in (1, 100, 500, 1000)}

print("строк | median, ms")
for n, ms in results.items():
    print(f"{n:>5} | {ms:.1f}")
print(f"500 строк дороже одной в {results[500] / results[1]:.1f} раза")