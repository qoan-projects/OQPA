# Project Name: QPA (Quantum Purity Amplification) 

## Collaboration
### Current Members ("The Puritans")
Zhaoyi Li (2nd year PhD in Physics)\
Takuya Isogawa (3rd year PhD in Nuclear Science)\
Honghao Fu (Faculty @ Concordia)\
**Supervisor** Ike Chuang
### Meetings
Weekly meetings (TBD) to catch up on progress
Notion page:
(TBA)

## Project Goal
QEC is great, but the resource budget is jaw dropping. We want to develop alternative method to gated-based QEC more applicable to NISQ applications. 

 ### Current Directions

1. **OQPA (Optimal Quantum Purity Amplification), previously known as Quantum state purification**\
 QPA is a class of quantum protocol that increases the purity of quantum states by consuming copies of noisy states, and OQPA is the info theoretic optimal construction under certain FOM. This question has been studied by many for the past 20 years, but the only solved instance is for qubits. In April 2023 we have solved the problem for $n\to 1$ OQPAs for qudits and developed an explicit construction *qudits*, aiming for more practical applications. (Work to be published)

 **Open questions**

 1. The first step of QPA involves strong Schur sampling, is there a way to do it efficiently? Also we need to figure out how to compile it down to unitary gates for certain experimentally-relavant examples.

 2. The optimal construction for $n\to m$ qudit construction is still unknown, might require heavy rep-theory.

 3. Generalizing optimal QPA to non-spherically symmetric channels and bench mark them

**Reference**

Earlier predecessors of similar methods include
[Error symmetrization in quantum computers](https://arxiv.org/abs/quant-ph/9605009).

The qubit QPA ([Optimal purification of single qubits](https://arxiv.org/abs/quant-ph/9812075), [The Rate of Optimal Purification procedures](https://arxiv.org/abs/quant-ph/9910124)) is intimately connected with [Quantum Majority Vote](https://arxiv.org/abs/2211.11729) and Quantum Cloning, e.g. [Optimal Cloning of Pure States](https://arxiv.org/abs/quant-ph/9804001).

Experimentally the $n=2$ case have been studied [Experimental Purification of Single Qubits](https://arxiv.org/abs/quant-ph/0403118).

Attempts to generalize the scheme to qudits, albeit not optimal, have been attented by Honghao et al. previously [Streaming quantum state purification](https://arxiv.org/abs/2309.16387). 

2. **MQPA (McWeeney QPA)**

McWeeney polynomials are a type of classical methods $F(\rho)$ that recursively increase the purify of a given state. We would like to develope a quantum version of this.

**Open Questions**

Is it possible to implent McWeeney purifications based on QSP (Quantum signal processing) or LCU(linear compination of unitary) techniques?

**Reference**\
[Generalized canonical purification for density matrix minimization](https://arxiv.org/abs/1512.07236)



3. Schur Transform/Sampling and HSP (Hidden Subgroup Problem)

**Open Questions**

Does measuring branching points of the Bratelli tree (generation of Young Tableaux) offer a potential method to solve the problem

**Reference**