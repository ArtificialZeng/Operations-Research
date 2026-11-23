"""Opening-stock scoring with the original overlap penalty."""

import numpy as np


def window_order(y, x, stock, d, s, a, b, cap, p, width, starts):
    starts_list = list(starts)
    num_windows = len(starts_list)
    if num_windows <= 1:
        return list(starts_list)

    num_periods = d.shape[1]

    # 2. Cumulative net inventory balance and opening stock footprint
    # cum_diff tracks cumulative production - demand across time
    cum_prod = np.cumsum(x, axis=1)
    cum_dem = np.cumsum(d, axis=1)
    inv = stock[:, None] + cum_prod - cum_dem  # full inventory profile

    # High unit opening price p[i] means consuming opening stock is costly;
    # where opening stock lingers, shifting production earlier inside a window frees stock.
    # Estimated active opening stock present in period t:
    active_opening_stock = np.maximum(0.0, np.minimum(stock[:, None], inv))
    stock_replace_value = np.sum(p[:, None] * active_opening_stock, axis=0)

    scores = np.zeros(num_windows, dtype=np.float64)
    for idx, st in enumerate(starts_list):
        en = min(st + width, num_periods)
        scores[idx] = np.sum(stock_replace_value[st:en])

    # Normalize base scores to [0, 1] range for stable penalty scaling
    min_sc, max_sc = np.min(scores), np.max(scores)
    norm_scores = (scores - min_sc) / (max_sc - min_sc + 1e-9)

    # 4. Greedy selection with spatial diversification to avoid near-duplicate windows
    # Downweight windows that heavily overlap with already selected ones in early iterations
    selected_indices = []
    remaining = list(range(num_windows))

    # Coverage dampening array across periods
    coverage = np.zeros(num_periods, dtype=np.float64)

    while remaining:
        best_cand = None
        best_cand_idx = -1
        best_val = -1e18

        for pos, r in enumerate(remaining):
            st = starts_list[r]
            en = min(st + width, num_periods)

            # Overlap penalty: mean coverage of the periods spanned by this candidate
            overlap = np.mean(coverage[st:en])
            # Diversity-discounted objective: penalize redundant consecutive windows
            discounted_score = norm_scores[r] - 0.65 * overlap

            # Stable deterministic tie-breaking by original index
            if discounted_score > best_val + 1e-9:
                best_val = discounted_score
                best_cand = r
                best_cand_idx = pos
            elif abs(discounted_score - best_val) <= 1e-9:
                if best_cand is None or starts_list[r] < starts_list[best_cand]:
                    best_val = discounted_score
                    best_cand = r
                    best_cand_idx = pos

        selected_indices.append(best_cand)
        remaining.pop(best_cand_idx)

        # Update period coverage with an exponential decay for older selections
        coverage *= 0.85
        st_sel = starts_list[best_cand]
        en_sel = min(st_sel + width, num_periods)
        coverage[st_sel:en_sel] += 1.0

    return [starts_list[i] for i in selected_indices]
