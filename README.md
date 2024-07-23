# Project Name: QPA (Quantum Purity Amplification) 

## Collaboration
### Current Members ("The Puritans")
Zhaoyi "Nitan" Li (2nd year PhD in Physics)\
Takuya Isogawa (3rd year PhD in Nuclear Science)\
Honghao Fu (Faculty @ Concordia)\
**Supervisor** Ike Chuang
### Meetings
Weekly meetings (TBD) to catch up on progress
Notion page:
(TBA)

## Project Goal
QEC is great (theoretically), but the resource budget is jaw dropping. We want to develop alternative method to gated-based QEC more applicable to NISQ applications that can actually make a difference.

 ## Current Directions

### 1. OQPA (Optimal Quantum Purity Amplification), previously known as Quantum state purification
 QPA is a class of quantum protocol that increases the purity of quantum states by consuming copies of noisy states, and OQPA is the info theoretic optimal construction under certain FOM. This question has been studied by many for the past 20 years, but the only solved instance is for qubits. In April 2024 we have solved the problem for $n\to 1$ OQPAs for *qudits* and developed an explicit construction for it. Now we are aiming to find more practical applications of the scheme. (Work to be published)

 **Open questions**

 1. The first step of QPA involves strong Schur sampling (measuring the Specht basis), is there a way to do it efficiently? Also we need to figure out how to compile it down to unitary gates for certain experimentally-relavant examples.

 2. The optimality of the $n\to m$ qudit OPQC construction is still unproven, might require heavy rep-theory (or even new math!). Suppose this can be proven, we also need to figure out the operation definition and gate-level implementation for the scheme.

 3. Generalizing optimal QPA to non-spherically symmetric channels and benchmark them.

 4. Futher taylor the current scheme and make it more experimentally feasible, potentially collaborating with experimental groups for POP demo.

 5. The study of PQPA (Probabilistic QPA). The optimal PQPA is conjectured to simply be the symmetrizer, but we need to prove this (Should be a simple proof). See [Protocols and Trade-Offs of Quantum State Purification](https://arxiv.org/abs/2404.01138), an attempt has been made but they weren't able to give a full proof.


**Reference**

- Earlier predecessors of QPA include
[Error symmetrization in quantum computers](https://arxiv.org/abs/quant-ph/9605009).

- The qubit QPA ([Optimal purification of single qubits](https://arxiv.org/abs/quant-ph/9812075), [The Rate of Optimal Purification procedures](https://arxiv.org/abs/quant-ph/9910124)) is intimately connected with [Quantum Majority Vote](https://arxiv.org/abs/2211.11729) and Quantum Cloning, e.g. [Optimal Cloning of Pure States](https://arxiv.org/abs/quant-ph/9804001).

- Experimentally, the $n=2$ case have been studied [Experimental Purification of Single Qubits](https://arxiv.org/abs/quant-ph/0403118).

- Attempts to generalize the scheme to qudits, albeit not optimal, have been attented by Honghao et al. previously [Streaming quantum state purification](https://arxiv.org/abs/2309.16387). 

### 2. **MQPA (McWeeney QPA)/VQPA (Virtual QPA)**
  
McWeeney polynomials are a type of classical methods $F(\rho)$ that recursively increase the purify of a given state. A "Quantized" version of this might bring unexpected gains for fault tolerance.

**Open Questions**

- Is it possible to implent McWeeney purifications based on QSP (Quantum signal processing) or LCU(linear compination of unitary) techniques?

- Sometimes, instead of performing the full QPA, we only need to "purify" the measurement outcome for specific target operators. This is called VQPA (Virtural QPA) To what extent we can do this?

**Reference**
- [Generalized canonical purification for density matrix minimization](https://arxiv.org/abs/1512.07236)

### 3. TQPA (Tomographical QPA)

Instead of using a quantum channel to perform the work, there might be a suboptimal procedure that only involves  measurement and state preparation, i.e. using an entanglement-breaking channel. This might have the advantage of being more expreimentally friendly. 

**Open Questions**
How does these constructions compare with QST (Quantum state tomography/estimation) schemes? 

**Reference**

[Principal eigenstate classical shadows](https://arxiv.org/abs/2405.13939)

### 4. Schur Transform/Sampling and HSP (Hidden Subgroup Problem)

**Open Questions**

Does measuring branching points of the Bratelli tree (generation of Young Tableaux) offer a potential method to solve the problem?

**Reference**