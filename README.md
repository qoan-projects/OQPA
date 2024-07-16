# Project Name: QPA (Quantum Purity Amplification) 

## Logistics
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

 1. The first step of QPA involves strong Schur sampling, is there a way to do it efficiently? Also compile it down to unitary gates for certain experimentally-relavant examples.

 2. The optimal construction for $n\to m$ qudit construction is still unknown, might require heavy rep-theory.

 3. Generalizing optimal QPA to non-spherically symmetric channels and bench mark them

**Reference**


2. **McWeeney QPA**

McWeeney polynomials are a type of classical methods $F(\rho)$ that recursively increase the purify of a given state. We would like to develope a quantum version of this.

**Open Questions**

Is it possible to implent McWeeney purifications based on QSP (Quantum signal processing) or LCU(linear compination of unitary) techniques?

**Reference**

3. Schur Transform/Sampling and HSP (Hidden Subgroup Problem)

**Open Questions**

Does measuring branching points of the Bratelli tree (generation of Young Tableaux) offer a potential method to solve the problem

**Reference**