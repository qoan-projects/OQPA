import os
import re
import pandas as pd
import matplotlib.pyplot as plt

# === Set your fixed parameters here ===
K = 2
SHOTS = 102400
J = 1.0
H = 1.0
TROTTER = False
SINGLECONTROL = True

# === Root directory for data ===
BASE_ROOT = f"simulation_outputs/new_fake_backend_estimation_k{K}_shots{SHOTS}"
OUTPUT_DIR = f"plotting_results/fake_backend_estimation_k{K}_shots{SHOTS}"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Tag prefix ===
fidelity_type = "Trotterized_Fidelity" if TROTTER else "Unitary_Fidelity"
# prefix = f"{fidelity_type}_{'single_control' if SINGLECONTROL else 'GHZ'}_t"
prefix = f"{fidelity_type}_t"
pattern = re.compile(rf"{prefix}([\d\.]+)_J{J}_h{H}_ntrot(\d+)_\d+\.csv")

# === Collect all results grouped by nqpa ===
results = {}

for nqpa_dir in os.listdir(BASE_ROOT):
    if not nqpa_dir.startswith("nqpa"):
        continue
    nqpa = int(nqpa_dir.replace("nqpa", ""))
    subdir = os.path.join(BASE_ROOT, nqpa_dir)
    if not os.path.isdir(subdir):
        continue

    ntrots = []
    fidelities = []

    for file in os.listdir(subdir):
        match = pattern.match(file)
        if match:
            _, ntrot = match.groups()
            ntrot = int(ntrot)
            print(os.path.join(subdir, file))
            df = pd.read_csv(os.path.join(subdir, file))
            fidelity = df["Fidelities"].values[0]
            ntrots.append(ntrot)
            fidelities.append(fidelity)

    if ntrots:
        ntrots, fidelities = zip(*sorted(zip(ntrots, fidelities)))
        results[nqpa] = (ntrots, fidelities)

# === Plotting ===
plt.figure(figsize=(10, 6))
for nqpa, (ntrots, fidelities) in sorted(results.items()):
    label = f"nqpa={nqpa} ({'Trotterized' if TROTTER else 'Exact'})"
    plt.plot(ntrots, fidelities, marker='o', label=label)

plt.xlabel("Number of Trotter Steps (ntrot)")
plt.ylabel("Fidelity")
plt.title(f"QPA Fidelity vs Trotter Steps\nk={K}, t=3.0, J={J}, h={H}, SC={SINGLECONTROL}")
plt.grid(True)
plt.legend()

# === Save output ===
plot_name = f"Fidelity_vs_ntrot_K{K}_shots{SHOTS}_J{J}_H{H}_{'Trotter' if TROTTER else 'Unitary'}_{'SC' if SINGLECONTROL else 'GHZ'}.png"
plot_path = os.path.join(OUTPUT_DIR, plot_name)
plt.savefig(plot_path)
print(f"[+] Plot saved to {plot_path}")
