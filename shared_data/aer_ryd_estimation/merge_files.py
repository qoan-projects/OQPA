import os
import csv

# ====== CONFIGURATION ======
safe_run = False  # If False, delete old files after merging
base_path = "shared_data/aer_ryd_estimation/simulation_outputs/ryd_estimation_125_eigenstates_k4_shots102400_eps0.0-0.01_s41"  # Base folder where the results are stored

# ===========================
def parse_csv(filepath):
    """Reads a CSV file and returns (epsilon, fidelity) as floats."""
    with open(filepath, "r") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) >= 2:
                try:
                    return float(row[0]), float(row[1])
                except ValueError:
                    pass
    return None

def merge_files(index_path, nqpa_path):
    files = os.listdir(nqpa_path)
    eps_files = sorted([f for f in files if f.startswith("eps") and f.endswith(".csv")])

    seen_eps = set()
    merged_data = []

    for file in eps_files:
        eps_val = file.split("_")[0].replace("eps", "")
        if eps_val in seen_eps:
            continue
        seen_eps.add(eps_val)

        filepath = os.path.join(nqpa_path, file)
        result = parse_csv(filepath)
        if result:
            merged_data.append(result)

    merged_data.sort(key=lambda x: x[0])  # sort by epsilon
    header = f"epsilon,QPA_{os.path.basename(nqpa_path)}[-1]"

    # Save the new merged CSV
    output_file = os.path.join(nqpa_path, "merged_results.csv")
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header.split(","))
        for row in merged_data:
            writer.writerow(row)

    # Delete old individual CSV files if not a safe run
    if not safe_run:
        for file in eps_files:
            try:
                os.remove(os.path.join(nqpa_path, file))
            except Exception as e:
                print(f"Error deleting {file}: {e}")

    print(f"[✔] Created: {output_file} ({len(merged_data)} values)")

# ===== Run the script =====
for index in os.listdir(base_path):
    index_path = os.path.join(base_path, index)
    if not os.path.isdir(index_path):
        continue

    for nqpa in os.listdir(index_path):
        nqpa_path = os.path.join(index_path, nqpa)
        if not os.path.isdir(nqpa_path):
            continue

        merge_files(index_path, nqpa_path)
