
## Hybrid Analog–Digital QPA Simulation Plan

### Goal

Simulate a hybrid quantum protocol combining analog adiabatic evolution and digital QPA under **dephasing noise**, controlled by a single coherence time parameter $T_2$. Sweep $T_2$ to evaluate performance.

[White paper](https://cdn.prod.website-files.com/643b94c382e84463a9e52264/648f5bf4d19795aaf36204f7_Whitepaper%20June%2023.pdf)
[Jupyter](https://github.com/QuEraComputing/QuEra-braket-examples/blob/main/AquilaWhitepaper/Example_3.ipynb)

---

###  Analog Part: Adiabatic Preparation with Lindblad Noise

* **Hamiltonian**:

  $$
  H(t) = \frac{\Omega(t)}{2} \sum_j \left(e^{i \phi(t)}|g_j\rangle\langle r_j| +  e^{-i \phi(t)}|r_j\rangle\langle g_j|\right) - \sum_j \Delta(t)\hat{n}_j + \sum_{j<k} V_{jk}\hat{n}_j\hat{n}_k
  $$
We take $\phi(t)=0$. 
* **Procedure**:

  * Perform adiabatic state preparation into a $\mathbb{Z}_2$ phase by ramping $\Omega(t)$ and sweeping $\Delta(t)$.

We need to ramp $\Omega(t)$ to avoid level crossing, see Rydberg.nb。

| Without $\Omega$                     | With $\Omega$                        |
| ----------------------------------- | ----------------------------------- |
| ![](src/Pasted%20image%2020250522110331.png) | ![](src/Pasted%20image%2020250522110340.png) |


* **Noise model**:

  * Solve Lindblad master equation with dephasing jump operators:

    $$
    L_j = \sqrt{\gamma} \hat{n}_j, \quad \hat{n}_j = |r_j\rangle\langle r_j|, \quad \gamma = \frac{1}{T_2}
    $$
  * This models **pure dephasing** in the Rydberg basis (e.g., laser phase noise), ignoring amplitude damping ($T_1 \sim 100\,\mu\text{s}$) since it's negligible compared to ramp time (\~4 μs).

* **Optimization Pipeline**:

	We will treat the analog simulation as an **inner loop** whose output (a mixed state $\rho(T_2,\theta)$) you *first* optimize for fixed, lab-realistic T₂ before handing the “best” density matrix to the digital QPA stage:


### Suitable Params for Aquila simulations

To guarantee we are feeding QPA the best achievable state under realistic experimental decoherence.

#### $T_2$
The **Aquila 1.0 white-paper datasheet** (§ 1.5, “Ground–Rydberg qubit coherence”) lists

| protocol          | symbol                 | value (μs) |
| ----------------- | ---------------------- | ---------- |
| Ramsey dephasing  | $\tau^{\!*}$           | **5.8**    |
| Spin-echo         | $\tau_{\mathrm{echo}}$ | 11.4       |
| Driven Rabi decay | $\tau_{\mathrm{Rabi}}$ | 7.5        |

For a **conservative, hardware-realistic** model use  

$$
T_2 = \tau^{\!*} \;\approx\; 6\,\mu\text{s},
$$


| step                                   | action                                                                          | details                                                                                                                        |
| -------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **1 Choose control knob set $\Theta$** | tunables: $\Omega_{\max},\;\Delta,\;t_{\mathrm{tot}},\;V_0,\;$ lattice spacing  | restrict to values admissible on **Aquila 1.0** (datasheet §1.5): $\Omega<3\cdot 2\pi \mathrm{MHz}$, $t_\mathrm{tot}> 1 \mu s$ |
| **2 Lindblad evolution**               | solve $\dot\rho=\mathcal L_{H(t)}[\rho]+\sum_j\gamma\,\mathcal D[\hat n_j]\rho$ | use the Python snippet with $\gamma=1/T_2$.                                                                                    |
| **3 Figure-of-merit**                  | $F(\rho,\sigma)$, $\sigma=\frac{1}{\sqrt{2}}\left(\ket{0101}+\ket{1010}\right)$ | Compare target state with prepared state                                                                                       |
| **4 Search**                           | 10x10x20 grid                                                                   |                                                                                                                                |
| **5 Extract eigen‐ensemble**           | diagonalise $\rho(\Theta)=\sum_i p_i\lvert\psi_i\rangle\!\langle\psi_i\rvert$   | store $\{p_i,\lvert\psi_i\rangle\}$.                                                                                           |

* **Post-processing**:

  * Obtain mixed state $\rho$ at end of analog stage.
  * Diagonalize $\rho$ and **truncate** to largest eigencomponents.
  * Sample pure states from dominant eigenvectors to feed into digital QPA stage.

---
### Digital Part: QPA Circuit with Phase Damping

* Run QPA in **Qiskit** on each sampled state.
* **Noise model**:

  * Use phase damping channel with:

    $$
    p = 1 - e^{-t_g / T_2}
    $$
  * $t_g$: fixed gate duration
  * Ensures noise model is consistent across analog and digital stages.

* **Sampling** – draw $\lvert\psi_i\rangle$ with probability $p_i$ and load as a `DensityMatrix` in Qiskit.  
* **Circuit** – run the QPA gate sequence.  
* **Consistent noise** – apply *phase-damping* channel  
  $$
    p = 1-e^{-t_g/T_2},\qquad
    \mathcal E_{\text{PD}}(\rho)= 
      \begin{pmatrix}
         1 & 0 \\ 0 & \sqrt{1-p}
      \end{pmatrix}\!
      \rho\,
      \begin{pmatrix}
         1 & 0 \\ 0 & \sqrt{1-p}
      \end{pmatrix},
  $$
  with the **same** $T_2$ used in the analog loop and $t_g$ equal to your native single-qubit gate time.

### Post-analysis

Compare final QPA fidelity versus the analog-only $\rho(\theta)$ baseline.

---



### Final Presentable

We evaluate the hybrid analog–digital QPA workflow at one(three) representative coherence times, $T₂ = 3 µs, 6 µs, and 11.4 µs$. For each value we  
1. perform optimisation of the Rydberg ramp,  
2. obtain the final mixed state $\rho_{\text{opt}}$,  
3. truncate its spectrum to the two largest eigenvectors that capture at least 95 % of the weight, and  
4. run phase-damped QPA on pure-state samples drawn from that ensemble.

| Figure                                             | Purpose/Comments                                               |
| -------------------------------------------------- | -------------------------------------------------------------- |
| Fidelity scatter (before vs after QPA)             | Visualise purification gain for each $T_2$                     |
| Overlaid optimal $\Omega(t)$ and $\Delta(t)$ ramps | Show how the optimiser compensates for dephasing (supps)       |
| Resource summary table                             | List ramp time, copy count, and final fidelity for every $T_2$ |
| Semi-log eigenvalue histograms                     | Justify the two-eigenvector truncation (supps)                 |


The narrative emphasises that even at the worst coherence the dominant eigenvector survives, QPA recovers most of its purity, and performance trends nearly linearly with $\gamma =\frac{1}{T_2}$, so three points suffice to interpolate the full behaviour.