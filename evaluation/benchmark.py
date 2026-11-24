"""Benchmark simples da API. Execute dentro do container api após popular o índice."""
import argparse, csv, json, statistics, time, urllib.parse, urllib.request


def percentile(values, p):
    ordered = sorted(values)
    if not ordered: return 0.0
    pos = (len(ordered) - 1) * p
    lo, hi = int(pos), min(int(pos) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--query", default="tecnologia")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--token", default="")
    parser.add_argument("--output", default="/app/data/benchmark.csv")
    args = parser.parse_args()
    url = args.url.rstrip("/") + "/questions?" + urllib.parse.urlencode({"q": args.query, "size": 10})
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    rows = []
    for mode in ("cold", "warm"):
        samples = []
        # A invalidação é restrita a professor e evita chamar consulta fria já cacheada.
        if mode == "warm":
            warm_req = urllib.request.Request(url, headers=headers)
            urllib.request.urlopen(warm_req, timeout=30).read()
        for i in range(args.iterations):
            if mode == "cold":
                invalidate = urllib.request.Request(args.url.rstrip("/") + "/admin/cache/invalidate", method="POST", headers=headers)
                with urllib.request.urlopen(invalidate, timeout=30) as inv_response:
                    if inv_response.status != 200: raise RuntimeError("Falha ao invalidar cache; use token de professor")
            req = urllib.request.Request(url, headers=headers)
            start = time.perf_counter()
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read())
                status = response.status
            elapsed = (time.perf_counter() - start) * 1000
            samples.append(elapsed)
            rows.append({"mode": mode, "iteration": i + 1, "latency_ms": round(elapsed, 3), "status": status, "total_hits": payload.get("total", 0)})
        print(f"{mode}: p50={percentile(samples,.50):.2f}ms p95={percentile(samples,.95):.2f}ms p99={percentile(samples,.99):.2f}ms")
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    print(f"CSV salvo em {args.output}")

if __name__ == "__main__": main()
