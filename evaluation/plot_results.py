"""Gera gráfico de latência a partir do CSV produzido pelo benchmark."""
import argparse, csv, statistics
from pathlib import Path
import matplotlib.pyplot as plt

p = argparse.ArgumentParser(); p.add_argument("csv", nargs="?", default="data/benchmark.csv"); p.add_argument("--output", default="reports/latencia-cache.png"); a = p.parse_args()
groups = {"cold": [], "warm": []}
with open(a.csv, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f): groups.setdefault(row["mode"], []).append(float(row["latency_ms"]))
labels = [k for k, v in groups.items() if v]
values = [groups[k] for k in labels]
if not values: raise SystemExit("CSV sem amostras")
fig, ax = plt.subplots(figsize=(8, 5)); ax.boxplot(values, tick_labels=labels, showmeans=True)
ax.set_title("Latência da API por condição de cache"); ax.set_ylabel("Latência (ms)"); ax.set_xlabel("Condição"); ax.grid(axis="y", alpha=.25)
Path(a.output).parent.mkdir(parents=True, exist_ok=True); fig.tight_layout(); fig.savefig(a.output, dpi=160)
print(a.output)
