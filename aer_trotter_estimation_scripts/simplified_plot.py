import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import argparse
import re
from collections import defaultdict
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit

# Set academic style for plots
plt.rcParams.update({
    "text.usetex": False,
    "font.family": "serif",
    # "font.serif": ["Times New Roman"], 
    "font.size": 14,
    "axes.labelsize": 16,
    "axes.titlesize": 18,
    "legend.fontsize": 14,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "figure.figsize": (8, 6),
    "lines.linewidth": 2,
    "lines.markersize": 8,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# ==========================================
# Data Loading
# ==========================================

def parse_filename(filepath):
    filename = os.path.basename(filepath)
    match = re.search(r"result_eps([\d\w]+)_steps(\d+)(_merged)?\.csv", filename)
    if match:
        eps_str = match.group(1).replace('p', '.')
        steps_str = match.group(2)
        return float(eps_str), int(steps_str)
    return None, None

def get_trials_folders(n_path):
    res = []
    if not os.path.exists(n_path): return res
    for d in os.listdir(n_path):
        path = os.path.join(n_path, d)
        if os.path.isdir(path) and d.startswith("trials") and d[6:].isdigit():
            res.append((int(d[6:]), path))
    return res

def load_data_from_simplified(base_dir, t, J, h, k, trials_request):
    """
    Loads data from SIMPLIFIED directory structure.
    Prioritizes 'results_merged.csv'.
    """
    params_path = f"t{str(t).replace('.','p')}_J{str(J).replace('.','p')}_h{str(h).replace('.','p')}"
    k_path = f"k{k}"
    root_search_path = os.path.join(base_dir, params_path, k_path)
    
    if not os.path.exists(root_search_path):
        print(f"Directory not found: {root_search_path}")
        return None

    aggregated = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'w_sum': 0.0, 'shots': 0}))))
    
    subdirs = [d for d in os.listdir(root_search_path) if os.path.isdir(os.path.join(root_search_path, d))]
    
    for subdir in subdirs:
        n_val = None
        current_n_path = os.path.join(root_search_path, subdir)
        
        if subdir == "unamplified":
            n_val = 1
            trials_list = [(1, current_n_path)] 
        elif subdir.startswith('n') and subdir[1:].isdigit():
            n_val = int(subdir[1:])
            trials_list = get_trials_folders(current_n_path)
        else:
            continue
            
        if not trials_list: continue
        
        if trials_request != 'max':
            req_t = int(trials_request)
            trials_list = [x for x in trials_list if x[0] == req_t]
            
        for t_val, t_path in trials_list:
            shots_folders = glob.glob(os.path.join(t_path, "shots*"))
            for shots_folder in shots_folders:
                # 1. Try reading merged file first
                merged_file = os.path.join(shots_folder, "results_merged.csv")
                found_data = False
                
                if os.path.exists(merged_file):
                    try:
                        df = pd.read_csv(merged_file)
                        # Expect columns: epsilon, steps, fidelity, shots
                        if {'epsilon', 'steps', 'fidelity', 'shots'}.issubset(df.columns):
                            for _, row in df.iterrows():
                                eps = float(row['epsilon'])
                                steps = int(row['steps'])
                                fid = float(row['fidelity'])
                                shots = int(row['shots'])
                                
                                aggregated[eps][n_val][steps][t_val]['w_sum'] += fid * shots
                                aggregated[eps][n_val][steps][t_val]['shots'] += shots
                            found_data = True
                    except Exception as e:
                        print(f"Error reading merged file {merged_file}: {e}")
                
                # 2. Fallback to individual files if no merged data found
                if not found_data:
                    csv_files = glob.glob(os.path.join(shots_folder, "*.csv"))
                    for csv_file in csv_files:
                        if "results_merged.csv" in csv_file: continue
                        
                        eps, steps = parse_filename(csv_file)
                        if eps is None or steps is None: continue
                        
                        try:
                            df = pd.read_csv(csv_file)
                            if not df.empty and 'fidelity' in df.columns:
                                # Determine shots from folder name
                                shot_count = 0
                                bname = os.path.basename(shots_folder)
                                if bname.startswith("shots"):
                                    try:
                                        shot_count = int(bname.replace("shots",""))
                                    except: pass
                                
                                if shot_count > 0:
                                    fid = df['fidelity'].iloc[0]
                                    aggregated[eps][n_val][steps][t_val]['w_sum'] += fid * shot_count
                                    aggregated[eps][n_val][steps][t_val]['shots'] += shot_count
                        except: pass

    return aggregated

def process_data_for_plotting(aggregated, mode='max'):
    final_data = defaultdict(dict)
    for eps, n_map in aggregated.items():
        for n_val, steps_map in n_map.items():
            s_list, f_list, t_list = [], [], []
            for steps, trials_map in steps_map.items():
                trial_fidelities = []
                for t_val, stats in trials_map.items():
                    if stats['shots'] > 0:
                        avg_fid = stats['w_sum'] / stats['shots']
                        trial_fidelities.append((avg_fid, t_val))
                if not trial_fidelities: continue
                best_fid, best_t = max(trial_fidelities, key=lambda x: x[0])
                s_list.append(steps)
                f_list.append(best_fid)
                t_list.append(best_t)
            if s_list:
                inds = np.argsort(s_list)
                final_data[eps][n_val] = pd.DataFrame({
                    'steps': np.array(s_list)[inds],
                    'fidelity': np.array(f_list)[inds],
                    'best_trial': np.array(t_list)[inds]
                })
    return final_data

# ==========================================
# Calculation Helpers
# ==========================================

def calculate_intersection_linear(x1, y1, x2, y2):
    if len(x1) < 2 or len(x2) < 2: return None
    p1 = np.polyfit(x1, y1, 1)
    p2 = np.polyfit(x2, y2, 1)
    m1, c1 = p1
    m2, c2 = p2
    if abs(m1 - m2) < 1e-9: return None
    x_int = (c2 - c1) / (m1 - m2)
    return x_int

def calculate_d0_for_n(aggregated_data, eps, n_target, trials_req):
    if 1 not in aggregated_data[eps] or n_target not in aggregated_data[eps]:
        return None
    
    steps_map_1 = aggregated_data[eps][1]
    x1, y1 = [], []
    for s in sorted(steps_map_1.keys()):
        for t, stats in steps_map_1[s].items():
            if stats['shots'] > 0:
                x1.append(s * 2)
                y1.append(stats['w_sum']/stats['shots'])
    if len(x1) < 2: return None
    x1, y1 = np.array(x1), np.array(y1)
    
    steps_map_n = aggregated_data[eps][n_target]
    all_trials = set()
    for s in steps_map_n: all_trials.update(steps_map_n[s].keys())
        
    d0_candidates = []
    for t_val in all_trials:
        x2, y2 = [], []
        for s in sorted(steps_map_n.keys()):
            if t_val in steps_map_n[s] and steps_map_n[s][t_val]['shots'] > 0:
                x2.append(s * 2)
                y2.append(steps_map_n[s][t_val]['w_sum'] / steps_map_n[s][t_val]['shots'])
        if len(x2) < 2: continue
        x2, y2 = np.array(x2), np.array(y2)
        d0 = calculate_intersection_linear(x1, y1, x2, y2)
        if d0 is not None: d0_candidates.append(d0)
            
    if not d0_candidates: return None
    return min(d0_candidates)

# ==========================================
# Plotting Functions
# ==========================================

def get_plot_dir(base_dir):
    plot_dir = os.path.join(base_dir, "plots")
    os.makedirs(plot_dir, exist_ok=True)
    return plot_dir

def get_markers_for_trials(trials_request):
    markers = {1: 'o', 2: 's', 3: '^', 4: 'D', 5: 'v', 6: '<', 7: '>'}
    if trials_request != 'max':
        try:
            fixed_marker = markers.get(int(trials_request), 'x')
            def get_m(t): return fixed_marker
            return get_m
        except: pass
    def get_m(t): return markers.get(int(t), 'x')
    return get_m

def plot_fidelity_vs_depth(data, target_eps, trials_req, plot_dir, raw_data=None):
    if target_eps not in data: return
    plt.figure()
    eps_data = data[target_eps]
    sorted_ns = sorted(eps_data.keys())
    colors = plt.cm.viridis(np.linspace(0, 0.8, len(sorted_ns)))
    get_marker = get_markers_for_trials(trials_req)
    
    if 1 in eps_data:
        df = eps_data[1]
        plt.plot(df['steps']*2, df['fidelity'], color='black', linestyle='--', label='Unamplified', zorder=1)
    
    for i, n in enumerate(sorted_ns):
        if n == 1: continue 
        df = eps_data[n]
        depths, fids, trials = df['steps']*2, df['fidelity'], df['best_trial']
        c = colors[i]
        plt.plot(depths, fids, color=c, linestyle='-', alpha=0.6)
        for t_val in np.unique(trials):
            mask = (trials == t_val)
            plt.scatter(depths[mask], fids[mask], color=c, marker=get_marker(int(t_val)), s=60, zorder=3)

    if raw_data is not None:
        for i, n in enumerate(sorted_ns):
            if n == 1: continue
            d0 = calculate_d0_for_n(raw_data, target_eps, n, trials_req)
            if d0 is not None and 1 in eps_data:
                df1 = eps_data[1]
                p1 = np.polyfit(df1['steps']*2, df1['fidelity'], 1)
                y_d0 = np.polyval(p1, d0)
                plt.scatter([d0], [y_d0], color='red', marker='X', s=100, zorder=10)

    plt.xlabel('Circuit Depth ($D = 2M$)')
    plt.ylabel('Fidelity')
    plt.title(f'Fidelity vs. Depth ($\epsilon={target_eps}$, Trials={trials_req})')
    
    from matplotlib.lines import Line2D
    legend_elements = [Line2D([0], [0], color='black', lw=2, linestyle='--', label='Unamplified')]
    for i, n in enumerate(sorted_ns):
        if n == 1: continue
        legend_elements.append(Line2D([0], [0], color=colors[i], lw=2, linestyle='-', label=f"n={n}"))
    
    if trials_req == 'max':
        used_trials = set()
        for n in sorted_ns:
            if n == 1: continue
            used_trials.update(eps_data[n]['best_trial'].unique())
        legend_elements.append(Line2D([0], [0], color='none', label=' '))
        legend_elements.append(Line2D([0], [0], color='none', label='Best Trial:'))
        for t_val in sorted(used_trials):
            legend_elements.append(Line2D([0], [0], marker=get_marker(int(t_val)), color='gray', label=f"k={int(t_val)}", markersize=8, lw=0))

    plt.legend(handles=legend_elements, loc='best')
    plt.savefig(os.path.join(plot_dir, f"fid_vs_depth_eps{str(target_eps).replace('.','p')}_trials{trials_req}.pdf"))
    plt.close()

def plot_fidelity_vs_epsilon(data, target_depth, trials_req, plot_dir):
    target_steps = target_depth // 2
    n_curves = defaultdict(list)
    sorted_epsilons = sorted(data.keys())
    for eps in sorted_epsilons:
        for n, df in data[eps].items():
            row = df[df['steps'] == target_steps]
            if not row.empty:
                n_curves[n].append((eps, row['fidelity'].iloc[0], row['best_trial'].iloc[0]))
    
    plt.figure()
    sorted_ns = sorted(n_curves.keys())
    colors = plt.cm.viridis(np.linspace(0, 0.8, len(sorted_ns)))
    get_marker = get_markers_for_trials(trials_req)

    if 1 in n_curves:
        pts = np.array(n_curves[1])
        plt.plot(pts[:,0], pts[:,1], color='black', linestyle='--', label='Unamplified', zorder=1)

    for i, n in enumerate(sorted_ns):
        if n == 1: continue
        pts = np.array(n_curves[n])
        if len(pts) == 0: continue
        x, y, t = pts[:,0], pts[:,1], pts[:,2]
        c = colors[i]
        plt.plot(x, y, color=c, linestyle='-', alpha=0.6)
        for t_val in np.unique(t):
            mask = (t == t_val)
            plt.scatter(x[mask], y[mask], color=c, marker=get_marker(int(t_val)), s=60, zorder=3)

    plt.xlabel('Noise Strength ($\epsilon$)')
    plt.ylabel('Fidelity')
    plt.title(f'Fidelity vs. Epsilon (Depth={target_depth}, Trials={trials_req})')
    
    from matplotlib.lines import Line2D
    legend_elements = [Line2D([0], [0], color='black', lw=2, linestyle='--', label='Unamplified')]
    for i, n in enumerate(sorted_ns):
        if n == 1: continue
        legend_elements.append(Line2D([0], [0], color=colors[i], lw=2, linestyle='-', label=f"n={n}"))
    if trials_req == 'max':
        used_trials = set()
        for n in n_curves:
            if n == 1: continue
            used_trials.update([x[2] for x in n_curves[n]])
        legend_elements.append(Line2D([0], [0], color='none', label=' '))
        legend_elements.append(Line2D([0], [0], color='none', label='Best Trial:'))
        for t_val in sorted(used_trials):
            legend_elements.append(Line2D([0], [0], marker=get_marker(int(t_val)), color='gray', label=f"k={int(t_val)}", markersize=8, lw=0))

    plt.legend(handles=legend_elements)
    plt.savefig(os.path.join(plot_dir, f"fid_vs_eps_depth{target_depth}_trials{trials_req}.pdf"))
    plt.close()

def plot_D0_vs_epsilon(raw_data, trials_req, plot_dir):
    d0_curves = defaultdict(list)
    sorted_epsilons = sorted(raw_data.keys())
    all_ns = set()
    for eps in raw_data: all_ns.update(raw_data[eps].keys())
    if 1 in all_ns: all_ns.remove(1)
    sorted_ns = sorted(list(all_ns))

    for eps in sorted_epsilons:
        for n in sorted_ns:
            d0 = calculate_d0_for_n(raw_data, eps, n, trials_req)
            if d0 is not None: d0_curves[n].append((eps, d0))

    if not d0_curves: 
        print("No D0 points found.")
        return

    plt.figure()
    colors = plt.cm.viridis(np.linspace(0, 0.8, len(sorted_ns)))
    markers = ['o', 's', '^', 'D', 'v', '<', '>']
    for i, n in enumerate(sorted_ns):
        if n not in d0_curves: continue
        pts = np.array(d0_curves[n])
        plt.plot(pts[:,0], pts[:,1], label=f"$n={n}$", marker=markers[i%7])

    plt.xlabel('Noise Strength ($\epsilon$)')
    plt.ylabel('Crossover Depth ($D_0$)')
    plt.title(f'Crossover Depth $D_0$ vs. Epsilon (Trials={trials_req})')
    plt.legend()
    plt.savefig(os.path.join(plot_dir, f"D0_vs_eps_trials{trials_req}.pdf"))
    plt.close()

def main():
    parser = argparse.ArgumentParser(description="Automated QPA Plots from Simplified Data")
    parser.add_argument('--base-dir', type=str, default='simplified_aer_trotter_data')
    parser.add_argument('--trials', type=str, required=True, help='Number of trials (int) or "max"')
    
    t, J, h, k = 1.0, 1.0, 1.0, 2
    args = parser.parse_args()
    
    print(f"Loading data from {args.base_dir}...")
    raw_data = load_data_from_simplified(args.base_dir, t, J, h, k, args.trials)
    
    if not raw_data:
        print("No data found.")
        return
        
    plot_data = process_data_for_plotting(raw_data, mode=args.trials)
    plot_dir = get_plot_dir(args.base_dir)

    print("Generating Plot 1: Fidelity vs Depth (eps=0.001)")
    plot_fidelity_vs_depth(plot_data, 0.001, args.trials, plot_dir, raw_data=raw_data)
    
    print("Generating Plot 2: Fidelity vs Epsilon (Depth=20)")
    plot_fidelity_vs_epsilon(plot_data, 20, args.trials, plot_dir)
    
    print("Generating Plot 3: D0 vs Epsilon")
    plot_D0_vs_epsilon(raw_data, args.trials, plot_dir)

if __name__ == "__main__":
    main()
