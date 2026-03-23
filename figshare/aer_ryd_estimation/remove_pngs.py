import os

# === CONFIGURATION ===
base_folder = "shared_data/aer_ryd_estimation/simulation_outputs/ryd_estimation_125_eigenstates_k4_shots102400_eps0.0-0.01_s41"
safe_run = False  # Set to False to actually delete files

def delete_pngs_in_nqpa(base_path):
    for index_folder in os.listdir(base_path):
        index_path = os.path.join(base_path, index_folder)
        if not os.path.isdir(index_path) or not index_folder.startswith("index"):
            continue

        for nqpa_folder in os.listdir(index_path):
            nqpa_path = os.path.join(index_path, nqpa_folder)
            if not os.path.isdir(nqpa_path) or not nqpa_folder.startswith("nqpa"):
                continue

            for file in os.listdir(nqpa_path):
                if file.endswith(".png"):
                    full_path = os.path.join(nqpa_path, file)
                    if safe_run:
                        print(f"[SAFE MODE] Would delete: {full_path}")
                    else:
                        try:
                            os.remove(full_path)
                            print(f"[DELETED] {full_path}")
                        except Exception as e:
                            print(f"[ERROR] Failed to delete {full_path}: {e}")

# Run it
delete_pngs_in_nqpa(base_folder)
