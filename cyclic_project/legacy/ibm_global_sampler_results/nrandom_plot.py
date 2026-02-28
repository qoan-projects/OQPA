#!/usr/bin/env python3
"""
Scan Sherbrooke-run folders that *end with “…_faketrue”* and plot
fidelity(r) for λ = 0.30, 0.36 and N_QPA = 0,1.

Expected layout
 └─ simulation_outputs/
      ibm_global_sampler_k2_…_r3000_…_faketrue/
          nqpa0/ nqpa1/
              nqpa{0|1}_lambda{0|1}_*.csv
"""

import re
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# ------------------------------------------------------------------------
BASE = Path("data/ibm_global_sampler/simulation_outputs")

RUN_RE = re.compile(        # only match folders that end with faketrue
    r"ibm_global_sampler_k2.*?_r(\d+)_.*_faketrue$"
)
LAMBDA_COL = "lambda"       # csv column holding λ
# ------------------------------------------------------------------------

records = []  # {r, nqpa, lam, fid}

for run_dir in BASE.iterdir():
    m = RUN_RE.match(run_dir.name)
    if not m:                # skip if folder doesn't end with faketrue
        continue
    r_val = int(m.group(1))  # r extracted from folder name

    for nqpa_dir in run_dir.glob("nqpa*"):
        nqpa = int(nqpa_dir.name[-1])    # 0 or 1
        for csv_file in nqpa_dir.glob("*.csv"):
            df = pd.read_csv(csv_file)
            lam  = float(df[LAMBDA_COL].iloc[0])
            fid_col = next(c for c in df.columns if c.startswith("QPA_"))
            fid  = float(df[fid_col].iloc[0])
            records.append({"r": r_val, "nqpa": nqpa, "lam": lam, "fid": fid})

# ------------------------------------------------------------------------
df_all = pd.DataFrame(records)
if df_all.empty:
    raise RuntimeError("No faketrue-runs found; check folder names.")

for lam_val in sorted(df_all["lam"].unique()):
    df_lam = df_all[df_all["lam"] == lam_val]

    plt.figure(figsize=(6, 4))
    for nqpa_val, style in zip([0, 1], ["--", "-"]):
        sub = df_lam[df_lam["nqpa"] == nqpa_val].sort_values("r")
        plt.plot(
            sub["r"], sub["fid"],
            linestyle=style, marker="o",
            label=f"N$_{{\\rm QPA}}$ = {nqpa_val}",
        )

    plt.title(
        rf"Fidelity vs $r$ (λ={lam_val:.2f}, k=2, shots=9·10$^5$)",
        fontsize=11,
    )
    plt.xlabel("$r$")
    plt.ylabel("Fidelity")
    plt.grid(alpha=0.3)
    plt.legend()
    out_name = f"data/ibm_global_sampler/plotting_results/fidelity_vs_r_lambda{lam_val:.2f}.png"
    plt.tight_layout()
    plt.savefig(out_name, dpi=300)
    print(f"Saved  →  {out_name}")
