# Extending a transportation dual across facility layouts

For fixed demand (d), let (Q_d(x)) minimize (sum_{ij} c_{ij}y_{ij}) subject to (sum_j y_{ij}le s_i x_i), (sum_i y_{ij}ge d_j) and (y_{ij}ge0). In the balanced representation, normalize the unused-capacity sink's potential to zero. Its zero-cost arcs enforce (u_ile0) for every anchor facility. For nonnegative real shipping costs, replacing a negative customer potential by zero preserves dual feasibility. Keep the resulting customer potentials (v_jge0) and the anchor facility potentials. For each other facility set

\[
u_i=\min\bigl(0,\min_j(c_{ij}-v_j)\bigr).
\]

This is the largest feasible (u_i) for that fixed (v). It yields (u_i+v_jle c_{ij}) for every facility–customer pair, regardless of which facilities are open. By the signs of the dual variables, every feasible shipment satisfies

\[
\sum_{ij}c_{ij}y_{ij}
\ge \sum_i u_i\sum_j y_{ij}+\sum_j v_j\sum_i y_{ij}
\ge \sum_i u_i s_i x_i+\sum_j v_j d_j.
\]

Thus the extended affine cut is a lower bound on recourse under any layout. A globally feasible extension can still be loose away from the anchor.

## Exact CAP101 check

Use the maximum-total-demand scenario of the original frozen CAP101 draws and their capacity-cover layout `[0, 10]`. Move its first facility to the lowest available source index, giving `[1, 10]` with unchanged capacity. The selected scenario has 69,245.200 units of demand. All 1,250 original arc inequalities and the capacity and demand dual signs pass exact integer checks. The alternative recourse uses its own certified optimal transportation tree. [Source instance](https://people.brunel.ac.uk/~mastjjb/jeb/orlib/files/cap101.txt) · [Exact values and duals](cut_extension.json)

| Open facility IDs, zero-based | Extended cut | Exact recourse |
| --- | ---: | ---: |
| `[0, 10]` | 1,520,295.482150 | 1,520,295.482150 |
| `[1, 10]` | 374,600.932150 | 1,405,376.608950 |

The cut is tight at the anchor and reaches 26.65% of recourse at the alternate layout. This checks validity and illustrates a substantial bound gap on one external scenario. It uses only two fixed-layout LPs, and the demands are from the existing external CAP101 pilot. [Probe](check_cut_extension.py)
