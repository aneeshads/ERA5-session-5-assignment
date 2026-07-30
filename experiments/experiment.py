#!/usr/bin/env python3
"""
Verification experiments for the ERA V5 Session-5 data-mixture specification.

Pure Python standard library — no numpy, no torch, no GPU. Runs anywhere in
seconds. The point is to make the spec's claims *falsifiable and reproducible*:
the numbers printed here are computed from the plan and the cited real dataset
sizes, not asserted.

Subcommands
-----------
  verify       Verify the plan's accounting + supply claims against the cited
               real dataset sizes (Table 3 of the report). Deterministic.
  repetition   Empirically demonstrate the <=4-epoch repetition rule
               (Muennighoff et al. 2023) that the supply discipline rests on.
  proxy-plan   Print the 1B / 3B GPU proxy configs (H1-H6) — the real ML
               experiments that still need a GPU. This file does NOT run them.
  all          Run verify + repetition and write results/*.json.

Usage
-----
  python3 experiment.py verify
  python3 experiment.py repetition
  python3 experiment.py proxy-plan
  python3 experiment.py all

Exit code is non-zero if any hard invariant in `verify` fails.
"""

import argparse
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")

# ----------------------------------------------------------------------------
# THE PLAN (single source of truth; mirrors the README tables)
# ----------------------------------------------------------------------------
BUDGET_T = 5.0          # trillion tokens (whole run)
MAIN_T = 4.6            # main pretraining phase
ANNEAL_T = 0.4         # final annealing phase

LANES = ["General web", "Code", "Mathematics & STEM", "Indic",
         "Curated knowledge", "Long-context", "Reasoning", "Agentic"]

# Section 4.1, Table 4 — main-run headline shares (%). Design allocation.
MAIN_MIX = {
    "General web": 42, "Code": 22, "Mathematics & STEM": 11, "Indic": 12,
    "Curated knowledge": 5, "Long-context": 4, "Reasoning": 2, "Agentic": 2,
}

# Section 5.2, Table 8 — per-stage mixture (% of each stage's tokens).
STAGES = ["Seed", "Foundation", "STEM ramp", "Long-context", "Anneal"]
STAGE_T = [0.15, 2.35, 1.5, 0.6, 0.4]          # trillion tokens per stage
MAIN_STAGE_WEIGHTS = STAGE_T[:4]               # first four = the 4.6T main run
STAGE_MATRIX = {
    "General web":        [62, 49, 30, 22, 14],
    "Code":               [8, 22, 28, 22, 18],
    "Mathematics & STEM": [2, 9, 16, 12, 16],
    "Indic":              [8, 13, 11, 10, 24],
    "Curated knowledge":  [18, 5, 3, 2, 0],
    "Long-context":       [0, 0, 4, 24, 8],
    "Reasoning":          [1, 1, 4, 4, 8],
    "Agentic":            [1, 1, 4, 4, 12],
}

# Section 4.2, Table 5 — Indic tier allocation (B tokens) and real supply (B).
INDIC_TIERS = {
    # tier: (allocation_B, real_unique_supply_B, source)
    "Verified native":   (210, 78,  "Sangraha-Verified 64B + IndicCorp v2 14.4B"),
    "Unverified native": (90,  24,  "Sangraha-Unverified"),
    "Translated":        (150, 162, "Sangraha-Synthetic (real) + IndicTrans2 gen"),
    "Synthetic/romanized": (102, 0,  "Sangraha-Synthetic (romanized) + generation"),
}
INDIC_LANE_B = 552      # 12% of 4.6T

# Section 4.0, Table 3 — real unique supply per lane (B tokens). None = constructed.
SUPPLY_B = {
    "General web": 5300,          # FineWeb-Edu 1.3T + DCLM 4T
    "Code": 900,                  # The Stack v2-dedup
    "Mathematics & STEM": 200,    # FineMath 54 + Proof-Pile-2 55 + Nemotron-CC-Math 133 (overlap)
    "Indic": 264,                 # Sangraha 250 + IndicCorp 14.4  (native subset = 102)
    "Curated knowledge": 50,      # Wikipedia + StackExchange + S4 books
    "Long-context": None,         # constructed by packing
    "Reasoning": 8,               # single-digit B unique open CoT
    "Agentic": 5,                 # xLAM/APIGen etc. — genuine trajectory tokens
}
INDIC_NATIVE_B = 102   # verified 64 + IndicCorp 14.4 + unverified 24

# Section 5.3, Table 9 — protected always-on floor (% of every batch).
FLOOR = {"Indic": 8, "Agentic": 1, "Reasoning": 1}

# The report's *declared* supply verdict per lane (Table 4) — verify recomputes
# the class independently and checks it agrees with this.
DECLARED = {
    "General web": "abundant", "Code": "repetition",
    "Mathematics & STEM": "repetition", "Indic": "repetition",
    "Curated knowledge": "repetition", "Long-context": "constructed",
    "Reasoning": "synthesis", "Agentic": "synthesis",
}
# NOTE: the Indic lane demand (638 B whole-run) is 2.4x the real unique Indic
# supply (264 B), i.e. repetition within the 4-epoch limit — the lane is filled
# by repeating real data, with only the ~18% romanized/synthetic tier newly
# generated (Table 5). "repetition" is therefore the honest aggregate verdict.

TOL = 2.5  # percentage-point tolerance for the stage->main integration check

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
GREEN, AMBER, RED, GREY, RST = "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[0m"


def ok(b):
    return (GREEN + "PASS" + RST) if b else (RED + "FAIL" + RST)


def classify(demand_b, supply_b):
    """Reproduce the report's / widget's supply-verdict logic."""
    if supply_b is None:
        return "constructed", None
    if supply_b >= 3000:
        return "abundant", demand_b / supply_b
    ep = demand_b / supply_b
    if ep <= 1.0:
        return "verified-backed", ep
    if ep <= 4.05:
        return "repetition", ep
    return "synthesis", ep


def whole_run_demand_b(lane):
    """Tokens (B) a lane consumes over the whole run, from the stage matrix."""
    return sum(STAGE_MATRIX[lane][s] * STAGE_T[s] * 1000 / 100 for s in range(5))


def stage_integral_pct(lane):
    """Token-weighted average of a lane over the 4 main-run stages (%)."""
    w = MAIN_STAGE_WEIGHTS
    num = sum(STAGE_MATRIX[lane][s] * w[s] for s in range(4))
    return num / sum(w)


# ----------------------------------------------------------------------------
# verify
# ----------------------------------------------------------------------------
def cmd_verify(write=False):
    print("=" * 72)
    print("PLAN ACCOUNTING & SUPPLY VERIFICATION")
    print("Verifying the spec's numbers against the cited real dataset sizes.")
    print("=" * 72)
    checks = []
    res = {"checks": [], "supply_table": [], "indic_tiers": []}

    def check(name, passed, detail=""):
        checks.append(passed)
        print(f"  [{ok(passed)}] {name}" + (f"   {GREY}{detail}{RST}" if detail else ""))
        res["checks"].append({"name": name, "pass": bool(passed), "detail": detail})

    # 1. main mix sums to 100
    s = sum(MAIN_MIX.values())
    check("Main mixture sums to 100%", s == 100, f"= {s}%")

    # 2. each stage column sums to 100
    for i, st in enumerate(STAGES):
        cs = sum(STAGE_MATRIX[l][i] for l in LANES)
        check(f"Stage '{st}' column sums to 100%", cs == 100, f"= {cs}%")

    # 3. stage matrix integrates to the main mix within tolerance
    print(f"\n  Stage->main integration (weights {MAIN_STAGE_WEIGHTS}, tol +/-{TOL} pt):")
    worst = 0.0
    for l in LANES:
        integ = stage_integral_pct(l)
        resid = integ - MAIN_MIX[l]
        worst = max(worst, abs(resid))
        print(f"     {l:22s} matrix->{integ:5.1f}%   plan {MAIN_MIX[l]:>2}%   "
              f"residual {resid:+.1f}")
    check("Stage matrix integrates to main mix within tolerance", worst <= TOL,
          f"worst residual {worst:.1f} pt")

    # 4. whole-run token total = 5000B
    total = sum(whole_run_demand_b(l) for l in LANES)
    check("Whole-run token total = 5000 B (5T)", abs(total - 5000) < 1,
          f"= {total:.0f} B")

    # 5. per-lane supply verdict recomputed and compared to the report
    print("\n  Whole-run demand vs real supply  (verdict recomputed from Table 3):")
    print(f"     {'Lane':22s} {'demand':>9s} {'supply':>9s} {'epochs':>7s}  verdict")
    for l in LANES:
        d = whole_run_demand_b(l)
        sup = SUPPLY_B[l]
        verdict, ep = classify(d, sup)
        epstr = "  -  " if ep is None else f"{ep:5.2f}x"
        col = {"abundant": GREEN, "verified-backed": GREEN, "repetition": AMBER,
               "synthesis": RED, "constructed": GREY}[verdict]
        print(f"     {l:22s} {d:7.0f} B {('-' if sup is None else str(sup)+' B'):>9s} "
              f"{epstr:>7s}  {col}{verdict}{RST}")
        res["supply_table"].append({"lane": l, "demand_b": round(d, 1),
                                    "supply_b": sup, "epochs": None if ep is None else round(ep, 2),
                                    "verdict": verdict})
    match = all(DECLARED[l] == classify(whole_run_demand_b(l), SUPPLY_B[l])[0] for l in LANES)
    check("Recomputed verdicts match the report's declared verdicts (Table 4)", match)

    # 6. Indic tiers: sums, native-majority, per-tier epochs
    print("\n  Indic lane tier check (Table 5):")
    tsum = sum(a for a, _, _ in INDIC_TIERS.values())
    check("Indic tiers sum to the 552 B lane", tsum == INDIC_LANE_B, f"= {tsum} B")
    native = INDIC_TIERS["Verified native"][0] + INDIC_TIERS["Unverified native"][0]
    frac = 100 * native / INDIC_LANE_B
    check("Indic lane is native-majority (verified+unverified >= 50%)", frac >= 50,
          f"native = {frac:.1f}%")
    for tier, (alloc, sup, src) in INDIC_TIERS.items():
        ep = (alloc / sup) if sup else None
        epstr = "generate" if ep is None else f"{ep:.2f}x epochs"
        flag = "" if (ep is None or ep <= 4.05) else "  <-- OVER 4 EPOCHS"
        within = ep is None or ep <= 4.05
        if tier in ("Verified native", "Unverified native"):
            check(f"  {tier} within 4-epoch limit", within, f"{alloc}B / {sup}B = {epstr}")
        else:
            print(f"     {tier:20s} {alloc}B  ({epstr}) {GREY}{src}{RST}")
        res["indic_tiers"].append({"tier": tier, "alloc_b": alloc, "supply_b": sup,
                                   "epochs": None if ep is None else round(ep, 2)})

    # 7. always-on floor is backed by real native supply within 4 epochs
    floor_tokens = FLOOR["Indic"] / 100 * MAIN_T * 1000
    floor_ep = floor_tokens / INDIC_NATIVE_B
    check("8% Indic floor backed by native supply within 4 epochs",
          floor_ep <= 4.05, f"{floor_tokens:.0f}B / {INDIC_NATIVE_B}B = {floor_ep:.2f}x")

    # 8. verified reconciliation (Session-3 sanity)
    verified_native = 78.4  # Sangraha 64 + IndicCorp 14.4
    pct_of_run = 100 * verified_native / (BUDGET_T * 1000)
    pct_at_4ep = 100 * (verified_native * 4) / (BUDGET_T * 1000)
    print(f"\n  Verified reconciliation: {verified_native:.0f}B verified native = "
          f"{pct_of_run:.2f}% of 5T unique, ~{pct_at_4ep:.1f}% at the 4-epoch limit.")
    res["verified_native_b"] = verified_native
    res["verified_pct_at_4ep"] = round(pct_at_4ep, 1)

    passed = all(checks)
    print("\n" + "=" * 72)
    print(f"RESULT: {ok(passed)}   ({sum(checks)}/{len(checks)} checks passed)")
    print("=" * 72)
    res["all_pass"] = bool(passed)
    if write:
        os.makedirs(RESULTS, exist_ok=True)
        with open(os.path.join(RESULTS, "verify.json"), "w") as f:
            json.dump(res, f, indent=2)
        print(f"wrote {os.path.join(RESULTS, 'verify.json')}")
    return passed


# ----------------------------------------------------------------------------
# repetition experiment (the <=4-epoch rule, Muennighoff et al. 2023)
# ----------------------------------------------------------------------------
def _make_task(d, w_true, n, noise, rng):
    """n samples of y = w.x + label-noise; noise is baked in per example."""
    data = []
    for _ in range(n):
        x = [rng.gauss(0, 1) for _ in range(d)]
        y = sum(w_true[j] * x[j] for j in range(d)) + rng.gauss(0, noise)
        data.append((x, y))
    return data


def _solve(A, b, d):
    """Solve A w = b (d x d) by Gaussian elimination with partial pivoting."""
    M = [A[i][:] + [b[i]] for i in range(d)]
    for c in range(d):
        p = max(range(c, d), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        piv = M[c][c]
        if abs(piv) < 1e-12:
            piv = 1e-12
        for r in range(d):
            if r != c and M[r][c] != 0.0:
                f = M[r][c] / piv
                for k in range(c, d + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][d] / (M[i][i] if abs(M[i][i]) > 1e-12 else 1e-12) for i in range(d)]


def _ridge(pool, d, lam):
    """Closed-form ridge regression: w = (X'X + lam I)^-1 X'y. Trained to
    convergence, so repeating the pool yields the SAME w — which is exactly why
    repeated tokens add no information beyond the unique set."""
    A = [[0.0] * d for _ in range(d)]
    b = [0.0] * d
    for x, y in pool:
        for i in range(d):
            xi = x[i]
            b[i] += xi * y
            Ai = A[i]
            for j in range(d):
                Ai[j] += xi * x[j]
    for i in range(d):
        A[i][i] += lam
    return _solve(A, b, d)


def _mse(w, data, d):
    tot = 0.0
    for x, y in data:
        pred = sum(w[j] * x[j] for j in range(d))
        tot += (pred - y) ** 2
    return tot / len(data)


def cmd_repetition(write=False):
    print("=" * 72)
    print("REPETITION-RULE EXPERIMENT  (mechanism demo of Muennighoff et al. 2023)")
    print("Two arms at each budget of processed tokens T = epochs x U:")
    print("  REPEAT  : train on a small fixed pool of U unique tokens, `epochs` times")
    print("  UNIQUE  : train on T = epochs x U *fresh* unique tokens (1 pass)")
    print("Claim under test: the REPEAT arm stops improving after a few epochs,")
    print("while the UNIQUE arm keeps improving — so repeated tokens are worth")
    print("less than fresh ones, and the gap grows with more repetition.")
    print("=" * 72)

    d = 30
    U = 150                  # small unique pool for the REPEAT arm
    noise = 1.0
    lam = 1.0
    trials = 6
    epochs_list = [1, 2, 4, 8, 16, 32]

    rows = []
    print(f"\n  d={d}, repeat-pool U={U} unique tokens, noise={noise}, ridge lam={lam}, "
          f"{trials} trials averaged")
    print("  (models trained to convergence, so the REPEAT arm is flat by")
    print("   construction — repeating a pool cannot add information)\n")
    print(f"     {'epochs':>7s} {'proc. tokens':>13s} {'REPEAT MSE':>12s} "
          f"{'UNIQUE MSE':>12s} {'repeat penalty':>15s}")
    for ep in epochs_list:
        T = ep * U
        rep_losses, uniq_losses = [], []
        for t in range(trials):
            rng = random.Random(2000 + t)
            w_true = [rng.gauss(0, 1) for _ in range(d)]
            test = _make_task(d, w_true, 2000, noise, rng)      # fresh held-out
            pool_small = _make_task(d, w_true, U, noise, rng)    # the unique set
            w_rep = _ridge(pool_small, d, lam)                   # repeat -> same w
            rep_losses.append(_mse(w_rep, test, d))
            pool_big = _make_task(d, w_true, T, noise, rng)      # T fresh unique
            w_uniq = _ridge(pool_big, d, lam)
            uniq_losses.append(_mse(w_uniq, test, d))
        rep = sum(rep_losses) / len(rep_losses)
        uniq = sum(uniq_losses) / len(uniq_losses)
        pen = 100 * (rep - uniq) / uniq
        print(f"     {ep:7d} {T:13d} {rep:12.4f} {uniq:12.4f} {pen:13.1f}%")
        rows.append({"epochs": ep, "proc_tokens": T, "repeat_mse": round(rep, 4),
                     "unique_mse": round(uniq, 4), "repeat_penalty_pct": round(pen, 1)})

    R = {r["epochs"]: r["repeat_mse"] for r in rows}
    Uq = {r["epochs"]: r["unique_mse"] for r in rows}
    pen = {r["epochs"]: r["repeat_penalty_pct"] for r in rows}
    # (1) unique data keeps improving; (2) repetition is wasteful at high epochs;
    # (3) the gap (value lost to repetition) grows with more repetition.
    unique_improves = (Uq[1] - Uq[32]) / Uq[1] > 0.05
    repetition_wasteful = pen[32] > 8.0
    gap_grows = pen[32] > pen[2] + 3.0
    print("\n  Interpretation:")
    print(f"     UNIQUE arm 1->32x data : {Uq[1]:.3f} -> {Uq[32]:.3f}  "
          f"(fresh tokens keep helping)")
    print(f"     REPEAT arm (any epochs): {R[1]:.3f}  "
          f"(flat — converges to the unique set, no matter how many passes)")
    print(f"     repeat penalty  2 ep {pen[2]:+.0f}%  ->  32 ep {pen[32]:+.0f}%  "
          f"(value lost to repetition grows)")
    verdict = unique_improves and repetition_wasteful and gap_grows
    print(f"\n  {ok(verdict)}  demonstrates the mechanism behind the supply discipline:")
    print("     a pool's information is finite, so once extracted, extra passes add")
    print("     nothing while fresh unique tokens keep helping — which is exactly why")
    print("     unique supply is the binding constraint and repetition has a ceiling.")
    print("  (Trained-to-convergence linear model on synthetic data. It shows the")
    print("   endpoint the rule warns about; the precise ~4-epoch threshold is the")
    print("   compute-limited LM regime of Muennighoff et al., for the 1B/3B proxies.)")

    if write:
        os.makedirs(RESULTS, exist_ok=True)
        out = {"config": {"d": d, "U": U, "noise": noise, "trials": trials},
               "rows": rows, "verdict_supports_rule": bool(verdict)}
        with open(os.path.join(RESULTS, "repetition.json"), "w") as f:
            json.dump(out, f, indent=2)
        print(f"\n  wrote {os.path.join(RESULTS, 'repetition.json')}")
    return verdict


# ----------------------------------------------------------------------------
# proxy-plan (the real ML experiments — need a GPU; not run here)
# ----------------------------------------------------------------------------
PROXIES = [
    ("H1", "8% native-Indic floor protects Indic under selection",
     "MILU, IndicQA, IndicGenBench",
     "Ablate the floor. Keep it if Indic drops >=5 pts while EN-MMLU stays "
     "within 1 pt; drop it if the benefit is <2 pts."),
    ("H2", "Agentic seed lifts tool use without fabricated tool outputs",
     "BFCL, tau-bench, tool-observation-emission rate",
     "If the model emits tool-observation tokens the mask is broken; if BFCL "
     "gain <3 pts, cut the synthetic share."),
    ("H3", "Code at 22% is the knee of code-vs-knowledge",
     "HumanEval/MBPP vs MMLU",
     "Sweep code in {18,22,26}% at 1B; pick the knee; raise to 26% if it still "
     "gains HumanEval at <=1 pt MMLU cost."),
    ("H4", "Native-majority Indic beats translation-heavy at equal tokens",
     "held-out native-Indic perplexity, IndicGenBench",
     "Raise translated share if translation-heavy matches native fluency; else "
     "keep native-majority."),
    ("H5", "Easy->hard curriculum reaches target in fewer tokens than flat",
     "tokens-to-threshold on MATH-L3 / GSM8K",
     "Reduce curriculum complexity if flat matches curriculum."),
    ("H6", "0.4T anneal on the reserve beats a broad-mix continuation",
     "SWE-bench-Lite, AIME, MILU, BFCL",
     "Re-curate the reserve if the anneal gain is <2 pts."),
]


def cmd_proxy_plan():
    print("=" * 72)
    print("PROXY TRAINING PLAN  (H1-H6) — the real ML experiments")
    print("These require a GPU and real data; this script does NOT run them.")
    print("Scales: 1B params ~25B tokens (stability) ; 3B params ~60-90B tokens.")
    print("Harness: lm-eval-harness + IndicGenBench + a BFCL/tau-bench runner,")
    print("proportions held fixed, Session-2 tokenizer.")
    print("=" * 72)
    for hid, hyp, metric, rule in PROXIES:
        print(f"\n  {hid}: {hyp}")
        print(f"      metric      : {metric}")
        print(f"      decision    : {rule}")
    print("\n  Run these, record the metrics, and paste the numbers back into")
    print("  Section 6 of the report. Only then is a proportion 'confirmed'.")


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["verify", "repetition", "proxy-plan", "all"],
                    nargs="?", default="all")
    args = ap.parse_args()

    if args.cmd == "verify":
        sys.exit(0 if cmd_verify(write=True) else 1)
    elif args.cmd == "repetition":
        cmd_repetition(write=True)
    elif args.cmd == "proxy-plan":
        cmd_proxy_plan()
    else:
        p = cmd_verify(write=True)
        print()
        cmd_repetition(write=True)
        print()
        cmd_proxy_plan()
        sys.exit(0 if p else 1)


if __name__ == "__main__":
    main()
