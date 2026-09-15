import json
from collections import defaultdict


def compute_kpis(enriched_path: str) -> dict:
    with open(enriched_path, encoding="utf-8") as f:
        rows = json.load(f)

    total = sum(r["cost_usd"] for r in rows)
    attributed = [r for r in rows if r["initiated_by"] != "not-found-in-cloudtrail"]
    unattributed = [r for r in rows if r["initiated_by"] == "not-found-in-cloudtrail"]

    attributed_cost = sum(r["cost_usd"] for r in attributed)
    unknown_cost = sum(r["cost_usd"] for r in unattributed)

    attribution_rate = round(attributed_cost / total * 100, 2) if total else 0.0
    unknown_pct = round(unknown_cost / total * 100, 2) if total else 0.0

    by_spender: dict[str, float] = defaultdict(float)
    for r in attributed:
        by_spender[r["initiated_by"]] += r["cost_usd"]
    top_spenders = sorted(by_spender.items(), key=lambda x: x[1], reverse=True)[:3]

    by_service: dict[str, float] = defaultdict(float)
    for r in unattributed:
        by_service[r["service"]] += r["cost_usd"]
    top_unattr = sorted(by_service.items(), key=lambda x: x[1], reverse=True)[:3]

    return {
        "total_cost_usd": round(total, 2),
        "attributed_cost_usd": round(attributed_cost, 2),
        "unknown_cost_usd": round(unknown_cost, 2),
        "attribution_rate_pct": attribution_rate,
        "unknown_cost_pct": unknown_pct,
        "top_spenders": [{"identity": k, "cost_usd": round(v, 2)} for k, v in top_spenders],
        "top_unattributed_services": [{"service": k, "cost_usd": round(v, 2)} for k, v in top_unattr],
    }


def print_kpis(kpis: dict) -> None:
    print("\n--- KPI Summary ------------------------------------")
    print(f"  Total cost          : ${kpis['total_cost_usd']:.2f}")
    print(f"  Attributed cost     : ${kpis['attributed_cost_usd']:.2f}")
    print(f"  Unknown cost        : ${kpis['unknown_cost_usd']:.2f}")
    print(f"  Attribution rate    : {kpis['attribution_rate_pct']}%")
    print(f"  Unknown cost %      : {kpis['unknown_cost_pct']}%")
    print("\n  Top spenders:")
    for s in kpis["top_spenders"]:
        print(f"    {s['identity']:32} ${s['cost_usd']:.2f}")
    print("\n  Top unattributed services:")
    for s in kpis["top_unattributed_services"]:
        print(f"    {s['service']:20} ${s['cost_usd']:.2f}")
    print("----------------------------------------------------\n")
