#!/usr/bin/env python3
"""combine_eps_csvs.py

Batch‑utility to consolidate per‑ε fidelity CSVs into one file per `index/*/nqpa*` folder.
After concatenation the original individual ε‑files are **deleted**.

Usage (from repo root):
    python shared_data/ryd_estimations/combine_eps_csvs.py \
        --root shared_data/ryd_estimations/simulation_outputs/ryd_estimation_125_eigenstates_k4_shots102400_eps0.0-0.01_s41

If --dry is supplied, no files are written/removed – actions are only printed.
"""

import argparse
import os
import sys
from pathlib import Path
import pandas as pd


def combine_eps_files(folder: Path, dry: bool = False) -> None:
    """Combine all CSVs in *folder* into a single CSV, then delete the originals."""
    csv_files = sorted(folder.glob("*.csv"))
    if not csv_files:
        return

    # Concatenate preserving identical header order
    dfs = [pd.read_csv(f) for f in csv_files]
    combined = pd.concat(dfs, ignore_index=True)

    # Output file name → e.g. combined_eps.csv (unique inside nqpa folder)
    out_file = folder / "combined_eps.csv"
    if dry:
        print(f"[DRY] Would write {out_file}  (rows={len(combined)})")
    else:
        combined.to_csv(out_file, index=False)
        print(f"[+] Wrote {out_file} ({len(combined)} rows)")
        # Delete source files
        for f in csv_files:
            f.unlink()
        print(f"[-] Removed {len(csv_files)} original ε‑CSV files in {folder}")


def walk_and_combine(root: Path, dry: bool = False) -> None:
    """Traverse root/index*/nqpa*/ and combine CSVs in each nqpa folder."""
    if not root.exists():
        sys.exit(f"[ERR] root path not found: {root}")

    for index_dir in sorted(root.glob("index*")):
        for nqpa_dir in sorted(index_dir.glob("nqpa*")):
            combine_eps_files(nqpa_dir, dry=dry)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combine ε‑resolved CSVs into single file per nqpa folder.")
    parser.add_argument("--root", required=True, help="Path to ryd_estimation_... top folder")
    parser.add_argument("--dry", action="store_true", help="Dry‑run: don’t write/delete, just report")
    args = parser.parse_args()

    walk_and_combine(Path(args.root).resolve(), dry=args.dry)
