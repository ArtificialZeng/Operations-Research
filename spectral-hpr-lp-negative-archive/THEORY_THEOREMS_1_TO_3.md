# Exact Theoretical Proofs: Theorems 1–3 (`spectral_hpr_lp_20261124`)

This note records complete, self-contained proofs for the three mathematical results underpinning Certified Rank-$r$ Spectral Semi-Proximal HPR (`Spec-HPR`). All notation matches `HPR-LP` (`arXiv:2611.01872`, Section 2).

---

## Setup & Exact Matrix-Free Dual Sweep

Consider the standard equality-form LP (obtained from any general LP $l_c \le Gx \le u_c$, $l_v \le x \le u_v$ by adding box-bounded slack variables $s_i \in [l_{c,i}, u_{c,i}]$ only on rows with $l_{c,i} < u_{c,i}$):
$$\min_{x \in \mathcal{C}} \langle c, x \rangle \quad \text{subject to} \quad A x = b, \qquad \mathcal{C} = [l_v, u_v].$$
In `HPR-LP` Algorithm 1 (`arXiv:2611.01872`, eq. 3) with $\mathcal{K} = \{b\}$, $\delta_{\mathcal{K}}^*(-y) = -\langle b, y \rangle$, penalty $\sigma > 0$, and any self-adjoint $\mathcal{T}_1 \succeq 0$ such that $\mathcal{M}_y := A A^\top + \mathcal{T}_1 \succ 0$:
1. $\xi^k = x^k + \sigma(A^\top y^k - c)$, $\bar{x}^{k+1} = \Pi_{\mathcal{C}}(\xi^k)$, $\bar{z}^{k+1} = (\bar{x}^{k+1} - \xi^k)/\sigma$.
2. Step 4 minimizes
   $$-\langle b, y \rangle + \langle \bar{x}^{k+1}, A^\top y \rangle + \frac{\sigma}{2}\|A^\top y + \bar{z}^{k+1} - c\|^2 + \frac{\sigma}{2}\|y - y^k\|_{\mathcal{T}_1}^2$$
   over unconstrained $y \in \mathbb{R}^m$. Setting the gradient to zero and substituting $\sigma(\bar{z}^{k+1} - c) = \bar{x}^{k+1} - x^k - \sigma A^\top y^k$ yields:
   $$-b + A\bar{x}^{k+1} + \sigma A A^\top (\bar{y}^{k+1} - y^k) + A(\bar{x}^{k+1} - x^k) + \sigma \mathcal{T}_1(\bar{y}^{k+1} - y^k) = 0,$$
   and hence the exact closed-form dual sweep:
   $$\bar{y}^{k+1} = y^k + \frac{1}{\sigma} \mathcal{M}_y^{-1}\!\left(b - A(2\bar{x}^{k+1} - x^k)\right).$$

---

## Theorem 1 (Strict Loewner & HPR-Metric Dominance)

**Statement.** Let $A \in \mathbb{R}^{m \times n}$ have singular values $s_1 \ge s_2 \ge \dots \ge s_m \ge 0$ (padding with zeros if $m > n$) and orthonormal left singular vectors $u_1, \dots, u_m \in \mathbb{R}^m$. For any integer $r \in \{0, 1, \dots, m - 1\}$ with $s_{r+1} > 0$, define
$$\mathcal{M}_y^{(r)} := s_{r+1}^2 I_m + \sum_{i=1}^r (s_i^2 - s_{r+1}^2) u_i u_i^\top, \qquad \mathcal{T}_1^{(r)} := \mathcal{M}_y^{(r)} - A A^\top.$$
Then:
1. *(Admissibility and Loewner monotonicity)* For all $0 \le r_1 < r_2 \le m-1$ with $s_{r_2+1} > 0$,
   $$0 \preceq \mathcal{T}_1^{(r_2)} \preceq \mathcal{T}_1^{(r_1)} \preceq \mathcal{T}_1^{(0)} = s_1^2 I_m - A A^\top, \qquad A A^\top \preceq \mathcal{M}_y^{(r_2)} \preceq \mathcal{M}_y^{(r_1)} \preceq s_1^2 I_m,$$
   and $\mathcal{T}_1^{(r)} u_i = 0$ for every $i \in \{1, \dots, r+1\}$.
2. *(Universal dominance in HPR-LP Theorem 2)* Let $\mathcal{M}_\sigma^{(r)} = \begin{bmatrix}\sigma \mathcal{M}_y^{(r)} & 0 & A \\ 0 & 0 & 0 \\ A^\top & 0 & \sigma^{-1} I_n\end{bmatrix}$ be the metric in eq. (8) of `arXiv:2611.01872`. For every initialization $w^0 = (y^0, z^0, x^0)$, every KKT solution $w^* = (y^*, z^*, x^*)$ (with $\Delta y = y^0 - y^*$), and every $\sigma > 0$:
   $$\|w^0 - w^*\|_{\mathcal{M}_\sigma^{(r)}}^2 = \|w^0 - w^*\|_{\mathcal{M}_\sigma^{(0)}}^2 - \sigma \!\left[\sum_{i=1}^r (s_1^2 - s_i^2)\langle u_i, \Delta y \rangle^2 + (s_1^2 - s_{r+1}^2)\|\Pi_{U_r^\perp} \Delta y\|^2\right] \le \|w^0 - w^*\|_{\mathcal{M}_\sigma^{(0)}}^2,$$
   and $\|\sqrt{\mathcal{T}_1^{(r)}}\|_2 = \sqrt{s_{r+1}^2 - s_m^2} \le \sqrt{s_1^2 - s_m^2} = \|\sqrt{\mathcal{T}_1^{(0)}}\|_2$. Both inequalities are strict whenever $s_{r+1} < s_1$ and $\Delta y \notin \operatorname{span}(u_1)$.
3. *(Matrix-free Woodbury cost)* Applying $(\mathcal{M}_y^{(r)})^{-1} v = s_{r+1}^{-2}\!\left(v - \sum_{i=1}^r (1 - s_{r+1}^2/s_i^2)(u_i^\top v) u_i\right)$ and evaluating $\|v\|_{\mathcal{M}_y^{(r)}}^2 = s_{r+1}^2\|v\|^2 + \sum_{i=1}^r (s_i^2 - s_{r+1}^2)(u_i^\top v)^2$ each require $2mr + O(m)$ FLOPs and zero extra SpMVs.

**Proof.** Writing $A A^\top = \sum_{i=1}^m s_i^2 u_i u_i^\top$ gives $\mathcal{M}_y^{(r)} = \sum_{i=1}^r s_i^2 u_i u_i^\top + \sum_{i=r+1}^m s_{r+1}^2 u_i u_i^\top$ and $\mathcal{T}_1^{(r)} = \sum_{i=r+1}^m (s_{r+1}^2 - s_i^2) u_i u_i^\top$. Since $s_1 \ge \dots \ge s_m \ge 0$ and $s_{r+1} > 0$, $\mathcal{T}_1^{(r)} \succeq 0$, $\mathcal{M}_y^{(r)} \succeq s_{r+1}^2 I_m \succ 0$, and for $r_1 < r_2$:
$$\mathcal{T}_1^{(r_1)} - \mathcal{T}_1^{(r_2)} = \mathcal{M}_y^{(r_1)} - \mathcal{M}_y^{(r_2)} = \sum_{i=r_1+1}^{r_2}(s_{r_1+1}^2 - s_i^2) u_i u_i^\top + \sum_{i=r_2+1}^m (s_{r_1+1}^2 - s_{r_2+1}^2) u_i u_i^\top \succeq 0.$$
This proves (1). For (2), $\mathcal{M}_\sigma^{(0)} - \mathcal{M}_\sigma^{(r)} = \operatorname{diag}(\sigma(\mathcal{M}_y^{(0)} - \mathcal{M}_y^{(r)}), 0, 0) \succeq 0$, yielding the exact quadratic-form identity, while the largest eigenvalue of $\mathcal{T}_1^{(r)}$ is $s_{r+1}^2 - s_m^2$. Part (3) follows directly by orthonormality of $\{u_1, \dots, u_r\}$. $\square$

---

## Theorem 2 (Exact Diagonal-Preconditioning Impossibility vs. Rank-1 Collapse)

**Statement.** Fix $m \ge 2$ and $\rho \in (0, 1)$, and define the equicorrelated positive-definite matrix $M_\rho := (1 - \rho) I_m + \rho \mathbf{1}_m \mathbf{1}_m^\top$.
1. For **every** pair of positive diagonal matrices $D_r = \operatorname{diag}(r_1, \dots, r_m) \succ 0$ and $D_c = \operatorname{diag}(c_1, \dots, c_m) \succ 0$,
   $$\kappa_2(D_r M_\rho D_c) := \frac{s_1(D_r M_\rho D_c)}{s_m(D_r M_\rho D_c)} > \frac{(m - 1)\rho}{1 - \rho}.$$
2. For **any** rectangular constraint matrix $A \in \mathbb{R}^{m \times n}$ satisfying $A A^\top = M_\rho$ and **every** positive diagonal left-scaling $D_r \succ 0$,
   $$\kappa_2(D_r A) := \frac{s_1(D_r A)}{s_m(D_r A)} > \sqrt{\frac{(m - 1)\rho}{1 - \rho}}.$$
3. By contrast, for both $M_\rho$ and any $A$ with $A A^\top = M_\rho$, the rank-1 spectral operator $\mathcal{M}_y^{(1)}$ satisfies $\mathcal{T}_1^{(1)} = 0$ identically and yields $\kappa_2\!\left((\mathcal{M}_y^{(1)})^{-1/2} A\right) = 1$ at $O(m)$ FLOPs/iteration.

**Proof.** Let $a_i := r_i c_i > 0$ for $i = 1, \dots, m$, and order indices so that $0 < a_{(1)} \le a_{(2)} \le \dots \le a_{(m)}$.
- *Upper bound on $s_m(D_r M_\rho D_c)$:* Define $v \in \mathbb{R}^m$ supported only on indices $(1)$ and $(2)$ by
  $$v_{(1)} = \frac{c_{(2)}}{\sqrt{c_{(1)}^2 + c_{(2)}^2}}, \qquad v_{(2)} = \frac{-c_{(1)}}{\sqrt{c_{(1)}^2 + c_{(2)}^2}}.$$
  Then $\|v\|_2 = 1$ and $\mathbf{1}_m^\top (D_c v) = c_{(1)} v_{(1)} + c_{(2)} v_{(2)} = 0$, so $M_\rho D_c v = (1 - \rho) D_c v$. Consequently,
  $$s_m(D_r M_\rho D_c) \le \|D_r M_\rho D_c v\|_2 = (1 - \rho)\sqrt{a_{(1)}^2 v_{(1)}^2 + a_{(2)}^2 v_{(2)}^2} \le (1 - \rho) a_{(2)}.$$
- *Lower bound on $s_1(D_r M_\rho D_c)$:* Set unit vectors $u = r / \|r\|_2$ and $w = c / \|c\|_2$. Since $r_i, c_i > 0$, Cauchy–Schwarz gives $\|r\|_2 \|c\|_2 \ge \sum_{i=1}^m r_i c_i = \sum_{i=1}^m a_i = a_{(1)} + \sum_{i=2}^m a_{(i)} > (m - 1) a_{(2)}$. Hence
  $$s_1(D_r M_\rho D_c) \ge u^\top D_r M_\rho D_c w = (1 - \rho)\frac{\sum_{i=1}^m a_i^2}{\|r\|_2 \|c\|_2} + \rho \|r\|_2 \|c\|_2 > \rho (m - 1) a_{(2)}.$$
Dividing the two inequalities establishes (1). For (2), set $D_c = D_r$ in (1) and note $\kappa_2(D_r A)^2 = \kappa_2(D_r A A^\top D_r) = \kappa_2(D_r M_\rho D_r) > (m-1)\rho/(1-\rho)$. For (3), the eigenvalues of $M_\rho$ are $1 + (m-1)\rho$ (multiplicity $1$, eigenvector $\mathbf{1}_m/\sqrt{m}$) and $1 - \rho$ (multiplicity $m-1$), so $\mathcal{M}_y^{(1)} = M_\rho$ for $A A^\top = M_\rho$ (and $\mathcal{M}_y^{(1)} = M_\rho^2$ for $M_\rho$ itself), giving $\mathcal{T}_1^{(1)} = 0$ and $(\mathcal{M}_y^{(1)})^{-1/2} A A^\top (\mathcal{M}_y^{(1)})^{-1/2} = I_m$. $\square$

---

## Theorem 3 (Exact Schur-Complement PSD Certification for Inexact Subspaces)

**Statement.** Let $\hat{U} \in \mathbb{R}^{m \times r}$ have orthonormal columns ($\hat{U}^\top \hat{U} = I_r$), and let $P_\perp := I_m - \hat{U}\hat{U}^\top$. Define $H := \hat{U}^\top A A^\top \hat{U} \in \mathbb{S}_+^r$ and suppose $\hat{U}$ has been rotated into the Ritz eigenbasis of $H$ so that $H = \operatorname{diag}(\mu_1, \dots, \mu_r)$ with $\mu_i \ge 0$. Compute the exact block residual $R := P_\perp A A^\top \hat{U} = A(A^\top \hat{U}) - \hat{U} H \in \mathbb{R}^{m \times r}$, let $H^{\dagger/2} := \operatorname{diag}(\mu_i^{-1/2} \mathbb{I}[\mu_i > 0])$, and set
$$\beta := \| R H^{\dagger/2} \|_2.$$
Let $\theta_\perp^2$ satisfy $\theta_\perp^2 \ge \| P_\perp A \|_2^2$. Then for **every** $\epsilon > 0$, defining
$$\tilde{\theta}^2 := \theta_\perp^2 + \frac{\beta^2}{\epsilon}, \qquad \tilde{\mu}_i := \max\!\left((1 + \epsilon)\mu_i, \tilde{\theta}^2\right),$$
the operator
$$\mathcal{M}_y^{(r,\text{cert})} := \tilde{\theta}^2 I_m + \hat{U}\operatorname{diag}(\tilde{\mu}_1 - \tilde{\theta}^2, \dots, \tilde{\mu}_r - \tilde{\theta}^2)\hat{U}^\top$$
satisfies $\mathcal{M}_y^{(r,\text{cert})} \succeq A A^\top$ identically (i.e., $\mathcal{T}_1^{(r,\text{cert})} := \mathcal{M}_y^{(r,\text{cert})} - A A^\top \succeq 0$).

**Proof.** Complete $\hat{U}$ to an orthonormal basis $[\hat{U}, \hat{U}_\perp]$ of $\mathbb{R}^m$ so $P_\perp = \hat{U}_\perp \hat{U}_\perp^\top$. In this basis,
$$[\hat{U}, \hat{U}_\perp]^\top A A^\top [\hat{U}, \hat{U}_\perp] = \begin{pmatrix} H & B^\top \\ B & C \end{pmatrix},$$
where $B = \hat{U}_\perp^\top A A^\top \hat{U}$ and $C = \hat{U}_\perp^\top A A^\top \hat{U}_\perp \preceq \theta_\perp^2 I_{m-r}$. Since $R = \hat{U}_\perp B$ and $\hat{U}_\perp$ has orthonormal columns, $\|B H^{\dagger/2}\|_2 = \|R H^{\dagger/2}\|_2 = \beta$. Moreover, for any $i$ with $\mu_i = 0$, we have $\|A^\top \hat{u}_i\|_2^2 = \mu_i = 0$, so $A^\top \hat{u}_i = 0$ and the $i$-th column of $B$ is identically zero; hence $B = (B H^{\dagger/2}) H^{1/2}$.

Now let $(x, y) \in \mathbb{R}^r \times \mathbb{R}^{m-r}$ be arbitrary, and define the block matrix $\tilde{D} := \operatorname{diag}(\tilde{\mu}_1, \dots, \tilde{\mu}_r) \succeq (1 + \epsilon) H$. Then:
$$\begin{aligned}
\begin{pmatrix} x \\ y \end{pmatrix}^\top \!\left(\begin{pmatrix}\tilde{D} & 0 \\ 0 & \tilde{\theta}^2 I_{m-r}\end{pmatrix} - \begin{pmatrix} H & B^\top \\ B & C \end{pmatrix}\right)\! \begin{pmatrix} x \\ y \end{pmatrix}
&\ge \epsilon \|H^{1/2} x\|_2^2 - 2 y^\top (B H^{\dagger/2})(H^{1/2} x) + y^\top(\theta_\perp^2 I_{m-r} - C) y + \frac{\beta^2}{\epsilon}\|y\|_2^2 \\
&\ge \epsilon \|H^{1/2} x\|_2^2 - 2\beta \|y\|_2 \|H^{1/2} x\|_2 + \frac{\beta^2}{\epsilon}\|y\|_2^2 \\
&= \left(\sqrt{\epsilon}\|H^{1/2} x\|_2 - \frac{\beta}{\sqrt{\epsilon}}\|y\|_2\right)^2 \ge 0.
\end{aligned}$$
Transforming back from $[\hat{U}, \hat{U}_\perp]$ yields $\mathcal{M}_y^{(r,\text{cert})} - A A^\top \succeq 0$. $\square$
