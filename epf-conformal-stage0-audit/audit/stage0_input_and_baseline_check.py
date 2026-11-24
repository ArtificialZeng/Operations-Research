"""Stage 0 bounded NON-OUTCOME feasibility, primary-source, input, and baseline-solver integration check.

STRICTLY NON-OUTCOME:
  * ZERO real electricity price levels, averages, volatilities, correlations, or holdout models are computed.
  * Checks ONLY:
      1. Live arXiv metadata verification for the closest primary sources (2307.16895, 2404.02270, 2507.15079).
      2. Live Zenodo 10.5281/zenodo.4624805 (`epftoolbox` 5-market benchmark) API metadata, file sizes,
         MD5 checksums, license, and streaming header/date/non-null row-count audit (NO price values read),
         plus GitHub `jeslago/epftoolbox` availability.
      3. Live official German Bundesnetzagentur SMARD API (`smard.de/app/chart_data/...`) index coverage
         (`2018-10` through `2026-11`) and 6 stratified weekly chunk schema/non-null/DST checks across
         `4169` (DE-LU price, presence-only!), `411` (day-ahead load forecast), `125` (solar forecast),
         `123` (wind onshore forecast), `3791` (wind offshore forecast), and `122` (total gen forecast).
      4. Pure synthetic baseline-solver integration & exact optimality/timing smoke in the pinned Python 3.14
         environment (`numpy`, `scipy`, `highspy`):
           - Exact LASSO coordinate descent (LEAR design matrix dimensions 1456 x 241) + KKT residual check
           - Exact Pool-Adjacent-Violators (PAVA / Isotonic Distributional Regression) monotonicity & timing
           - Exact Quantile Regression LP via `highspy` (QRA/iQRA dimensions) + optimality & timing
           - Online Conformal PID Controller (Angelopoulos et al. 2023) synthetic shift coverage tracking
           - Exact Battery Energy Storage System (BESS) day-ahead arbitrage LP via `highspy` + SoC check
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import highspy
import numpy as np

OUT_PATH = Path(__file__).resolve().parent / "stage0_input_and_baseline_check.json"
HEADERS = {"User-Agent": "Academic-Research-EPF-Stage0-Check/1.0", "Accept": "application/json"}


def fetch_bytes(url: str, timeout: float = 30.0) -> tuple[int, bytes | None, str | None, float]:
    t0 = perf_counter()
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=timeout) as resp:
            return int(resp.status), resp.read(), None, round(perf_counter() - t0, 3)
    except HTTPError as exc:
        return int(exc.code), None, f"HTTPError {exc.code}: {exc.reason}", round(perf_counter() - t0, 3)
    except URLError as exc:
        return 0, None, f"URLError: {exc.reason}", round(perf_counter() - t0, 3)
    except Exception as exc:  # noqa: BLE001
        return 0, None, f"{type(exc).__name__}: {exc}", round(perf_counter() - t0, 3)


def check_arxiv_primary_sources() -> dict:
    ids = ["2307.16895", "2404.02270", "2507.15079"]
    url = f"https://export.arxiv.org/api/query?id_list={','.join(ids)}"
    status, raw, err, dt = fetch_bytes(url, timeout=30.0)
    out = {"url": url, "http_status": status, "error": err, "elapsed_seconds": dt, "papers": []}
    if status == 200 and raw:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw.decode("utf-8"))
        for entry in root.findall("atom:entry", ns):
            eid = entry.findtext("atom:id", default="", namespaces=ns).strip()
            title = " ".join(entry.findtext("atom:title", default="", namespaces=ns).split())
            published = entry.findtext("atom:published", default="", namespaces=ns).strip()
            updated = entry.findtext("atom:updated", default="", namespaces=ns).strip()
            authors = [
                a.findtext("atom:name", default="", namespaces=ns).strip()
                for a in entry.findall("atom:author", ns)
            ]
            out["papers"].append(
                {
                    "id": eid,
                    "title": title,
                    "authors": authors,
                    "published": published,
                    "updated": updated,
                }
            )
    return out


def check_epftoolbox_zenodo_and_github() -> dict:
    zen_url = "https://zenodo.org/api/records/4624805"
    status, raw, err, dt = fetch_bytes(zen_url, timeout=30.0)
    res: dict = {
        "zenodo_api_url": zen_url,
        "zenodo_http_status": status,
        "zenodo_error": err,
        "zenodo_elapsed_seconds": dt,
        "files": {},
    }
    if status == 200 and raw:
        meta = json.loads(raw.decode("utf-8"))
        res["doi"] = meta.get("doi")
        res["title"] = meta.get("metadata", {}).get("title")
        res["license"] = meta.get("metadata", {}).get("license", {}).get("id")
        res["access_right"] = meta.get("metadata", {}).get("access_right")
        for f in meta.get("files", []):
            key = f.get("key")
            f_url = f.get("links", {}).get("self")
            entry = {
                "size_bytes": f.get("size"),
                "checksum": f.get("checksum"),
                "download_url": f_url,
            }
            # Inspect ONLY schema, date range, row count, and non-null count (ZERO price values!)
            if key and key.endswith(".csv") and f_url:
                fst, fraw, ferr, fdt = fetch_bytes(f_url, timeout=45.0)
                entry["stream_http_status"] = fst
                entry["stream_error"] = ferr
                entry["stream_elapsed_seconds"] = fdt
                if fst == 200 and fraw:
                    reader = csv.reader(io.StringIO(fraw.decode("utf-8", errors="replace")))
                    header = next(reader, [])
                    n_rows = 0
                    nonnull_counts = [0] * len(header)
                    first_ts = None
                    last_ts = None
                    for row in reader:
                        if not row:
                            continue
                        n_rows += 1
                        if first_ts is None:
                            first_ts = row[0]
                        last_ts = row[0]
                        for j, cell in enumerate(row[: len(header)]):
                            if cell.strip() != "" and cell.strip().lower() != "nan":
                                nonnull_counts[j] += 1
                    entry["columns"] = header
                    entry["row_count"] = n_rows
                    entry["complete_24h_days_approx"] = n_rows // 24
                    entry["min_timestamp"] = first_ts
                    entry["max_timestamp"] = last_ts
                    entry["nonnull_by_column"] = dict(zip(header, nonnull_counts))
            res["files"][key] = entry

    gh_url = "https://raw.githubusercontent.com/jeslago/epftoolbox/master/epftoolbox/models/_lear.py"
    gst, graw, gerr, gdt = fetch_bytes(gh_url, timeout=20.0)
    res["github_lear_reference"] = {
        "url": gh_url,
        "http_status": gst,
        "error": gerr,
        "elapsed_seconds": gdt,
        "bytes": len(graw) if graw else 0,
    }
    return res


def check_smard_germany_api() -> dict:
    # Official Bundesnetzagentur SMARD filter IDs for Germany / DE-LU
    series_spec = {
        "4169": {"region": "DE-LU", "fallback_region": "DE", "desc": "Day-Ahead Auction Price DE-LU (presence-only audit)"},
        "411": {"region": "DE", "fallback_region": "DE-LU", "desc": "Forecasted Total Grid Load (Day-Ahead)"},
        "125": {"region": "DE", "fallback_region": "DE-LU", "desc": "Forecasted Solar Generation (Day-Ahead)"},
        "123": {"region": "DE", "fallback_region": "DE-LU", "desc": "Forecasted Wind Onshore Generation (Day-Ahead)"},
        "3791": {"region": "DE", "fallback_region": "DE-LU", "desc": "Forecasted Wind Offshore Generation (Day-Ahead)"},
        "122": {"region": "DE", "fallback_region": "DE-LU", "desc": "Forecasted Total Generation (Day-Ahead)"},
    }
    # Target stratified probe timestamps (ms UTC) for non-null & DST verification (ZERO price values!)
    probe_dates_utc = [
        ("2018_10_bidding_zone_launch", datetime(2018, 10, 8, tzinfo=timezone.utc)),
        ("2020_03_spring_dst_23h", datetime(2020, 3, 29, tzinfo=timezone.utc)),
        ("2021_10_autumn_dst_25h", datetime(2021, 10, 31, tzinfo=timezone.utc)),
        ("2022_08_energy_crisis", datetime(2022, 8, 22, tzinfo=timezone.utc)),
        ("2024_06_solar_summer", datetime(2024, 6, 17, tzinfo=timezone.utc)),
        ("2026_11_latest_window", datetime(2026, 11, 16, tzinfo=timezone.utc)),
    ]
    out: dict = {"series": {}, "note": "Strictly non-null timestamp/presence audit; zero price values stored or summarized."}
    ts_cut_2018 = int(datetime(2018, 10, 1, tzinfo=timezone.utc).timestamp() * 1000)
    ts_cut_2024 = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)

    for fid, spec in series_spec.items():
        region = spec["region"]
        idx_url = f"https://www.smard.de/app/chart_data/{fid}/{region}/index_hour.json"
        st, raw, err, dt = fetch_bytes(idx_url, timeout=20.0)
        if st != 200:
            region = spec["fallback_region"]
            idx_url = f"https://www.smard.de/app/chart_data/{fid}/{region}/index_hour.json"
            st, raw, err, dt = fetch_bytes(idx_url, timeout=20.0)

        entry: dict = {
            "filter_id": fid,
            "region_used": region,
            "description": spec["desc"],
            "index_url": idx_url,
            "index_http_status": st,
            "index_error": err,
            "index_elapsed_seconds": dt,
        }
        if st == 200 and raw:
            ts_list = json.loads(raw.decode("utf-8")).get("timestamps", [])
            entry["total_weekly_chunks"] = len(ts_list)
            if ts_list:
                entry["min_chunk_utc"] = datetime.fromtimestamp(ts_list[0] / 1000, tz=timezone.utc).isoformat()
                entry["max_chunk_utc"] = datetime.fromtimestamp(ts_list[-1] / 1000, tz=timezone.utc).isoformat()
                chunks_ge_2018_10 = [t for t in ts_list if t >= ts_cut_2018]
                chunks_ge_2024 = [t for t in ts_list if t >= ts_cut_2024]
                entry["chunks_from_2018_10"] = len(chunks_ge_2018_10)
                entry["chunks_from_2024_01"] = len(chunks_ge_2024)
                entry["approx_days_from_2018_10"] = len(chunks_ge_2018_10) * 7
                entry["approx_days_from_2024_01"] = len(chunks_ge_2024) * 7

                # Stratified chunk presence check
                probes = {}
                for label, dt_obj in probe_dates_utc:
                    target_ms = int(dt_obj.timestamp() * 1000)
                    # Find nearest chunk <= target_ms (or last chunk for latest)
                    cands = [t for t in ts_list if t <= target_ms]
                    chosen = cands[-1] if cands else ts_list[0]
                    if label == "2026_11_latest_window":
                        chosen = ts_list[-2] if len(ts_list) >= 2 else ts_list[-1]
                    curl = f"https://www.smard.de/app/chart_data/{fid}/{region}/{fid}_{region}_hour_{chosen}.json"
                    cst, craw, cerr, cdt = fetch_bytes(curl, timeout=20.0)
                    if cst == 200 and craw:
                        series_rows = json.loads(craw.decode("utf-8")).get("series", [])
                        total_pts = len(series_rows)
                        nonnull_pts = sum(1 for row in series_rows if len(row) >= 2 and row[1] is not None)
                        probes[label] = {
                            "chunk_utc": datetime.fromtimestamp(chosen / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
                            "http_status": cst,
                            "total_hours_in_chunk": total_pts,
                            "nonnull_hours_in_chunk": nonnull_pts,
                            "nonnull_rate": round(nonnull_pts / total_pts, 4) if total_pts else 0.0,
                        }
                    else:
                        probes[label] = {"http_status": cst, "error": cerr}
                entry["stratified_chunk_presence_probes"] = probes
        out["series"][fid] = entry
    return out


def pava_nondecreasing(y: np.ndarray, w: np.ndarray | None = None) -> np.ndarray:
    """Exact O(n) Pool Adjacent Violators Algorithm (PAVA) for non-decreasing isotonic regression."""
    n = len(y)
    if w is None:
        w = np.ones(n, dtype=np.float64)
    # Blocks stored as [sum_wy, sum_w, start_idx, end_idx]
    vals = np.empty(n, dtype=np.float64)
    wts = np.empty(n, dtype=np.float64)
    starts = np.empty(n, dtype=np.int64)
    ends = np.empty(n, dtype=np.int64)
    top = -1
    for i in range(n):
        top += 1
        vals[top] = w[i] * y[i]
        wts[top] = w[i]
        starts[top] = i
        ends[top] = i
        while top > 0 and (vals[top - 1] / wts[top - 1]) > (vals[top] / wts[top]):
            vals[top - 1] += vals[top]
            wts[top - 1] += wts[top]
            ends[top - 1] = ends[top]
            top -= 1
    out = np.empty(n, dtype=np.float64)
    for k in range(top + 1):
        out[starts[k] : ends[k] + 1] = vals[k] / wts[k]
    return out


def lasso_coordinate_descent(X: np.ndarray, y: np.ndarray, lam: float, max_iter: int = 500, tol: float = 1e-7) -> tuple[np.ndarray, float]:
    """Exact cyclic coordinate descent solving min_{b} (1/(2n))||y - Xb||_2^2 + lam*||b||_1 on standardized X."""
    n, p = X.shape
    b = np.zeros(p, dtype=np.float64)
    r = y.copy()
    col_norm2 = np.sum(X * X, axis=0) / n
    for _ in range(max_iter):
        max_diff = 0.0
        for j in range(p):
            if col_norm2[j] == 0.0:
                continue
            bj_old = b[j]
            rho = float(np.dot(X[:, j], r)) / n + col_norm2[j] * bj_old
            if rho > lam:
                bj_new = (rho - lam) / col_norm2[j]
            elif rho < -lam:
                bj_new = (rho + lam) / col_norm2[j]
            else:
                bj_new = 0.0
            diff = bj_new - bj_old
            if diff != 0.0:
                b[j] = bj_new
                r -= diff * X[:, j]
                if abs(diff) > max_diff:
                    max_diff = abs(diff)
        if max_diff < tol:
            break
    # Verify exact KKT subgradient optimality
    grad = -(X.T @ r) / n  # d/db [(1/2n)||y - Xb||^2]
    kkt_err = 0.0
    for j in range(p):
        if b[j] > 0:
            kkt_err = max(kkt_err, abs(grad[j] + lam))
        elif b[j] < 0:
            kkt_err = max(kkt_err, abs(grad[j] - lam))
        else:
            kkt_err = max(kkt_err, max(0.0, abs(grad[j]) - lam))
    return b, float(kkt_err)


def solve_quantile_regression_highs(X: np.ndarray, y: np.ndarray, tau: float) -> tuple[np.ndarray, str]:
    """Exact LP quantile regression via HiGHS: min sum_i (tau * u_i + (1-tau) * v_i) s.t. X b + u - v = y."""
    n, p = X.shape
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    inf = highspy.kHighsInf
    # Variables: b (p, free), u (n, >=0), v (n, >=0)
    num_vars = p + 2 * n
    col_cost = np.concatenate([np.zeros(p), np.full(n, tau), np.full(n, 1.0 - tau)])
    col_lower = np.concatenate([np.full(p, -inf), np.zeros(2 * n)])
    col_upper = np.full(num_vars, inf)
    h.addCols(num_vars, col_cost, col_lower, col_upper, 0, np.array([], dtype=np.int32), np.array([], dtype=np.int32), np.array([], dtype=np.float64))

    # Build sparse rows: X[i, :] b + u_i - v_i = y_i
    starts = np.arange(0, n * (p + 2), p + 2, dtype=np.int32)
    indices = np.empty(n * (p + 2), dtype=np.int32)
    values = np.empty(n * (p + 2), dtype=np.float64)
    for i in range(n):
        base = i * (p + 2)
        indices[base : base + p] = np.arange(p, dtype=np.int32)
        values[base : base + p] = X[i]
        indices[base + p] = p + i
        values[base + p] = 1.0
        indices[base + p + 1] = p + n + i
        values[base + p + 1] = -1.0
    h.addRows(n, y.astype(np.float64), y.astype(np.float64), len(indices), starts, indices, values)
    h.run()
    sol = np.array(h.getSolution().col_value[:p], dtype=np.float64)
    return sol, str(h.getModelStatus())


def solve_bess_day_ahead_lp(prices: np.ndarray, e_max: float = 2.0, p_max: float = 1.0, eta: float = 0.92, s0: float = 1.0) -> dict:
    """Exact 24-hour BESS arbitrage LP via HiGHS:
    max sum_h prices[h] * (d_h - c_h)
    s.t. s_{h+1} = s_h + eta * c_h - (1/eta) * d_h, 0 <= s_h <= e_max, s_0 = s_24 = s0, 0 <= c_h, d_h <= p_max.
    """
    H = len(prices)
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    # Variables: c_0..c_{H-1}, d_0..d_{H-1}, s_1..s_H (s_H fixed to s0)
    # Minimize sum_h prices[h] * (c_h - d_h)
    num_vars = 3 * H
    col_cost = np.concatenate([prices, -prices, np.zeros(H)])
    col_lower = np.zeros(num_vars)
    col_upper = np.concatenate([np.full(H, p_max), np.full(H, p_max), np.full(H, e_max)])
    col_lower[2 * H + H - 1] = s0
    col_upper[2 * H + H - 1] = s0
    h.addCols(num_vars, col_cost, col_lower, col_upper, 0, np.array([], dtype=np.int32), np.array([], dtype=np.int32), np.array([], dtype=np.float64))

    # Constraints:
    # h = 0: s_1 - eta*c_0 + (1/eta)*d_0 = s0
    # h >= 1: s_{h+1} - s_h - eta*c_h + (1/eta)*d_h = 0
    row_lower = np.zeros(H)
    row_upper = np.zeros(H)
    row_lower[0] = s0
    row_upper[0] = s0
    starts = []
    indices = []
    values = []
    for t in range(H):
        starts.append(len(indices))
        indices.extend([t, H + t, 2 * H + t])
        values.extend([-eta, 1.0 / eta, 1.0])
        if t > 0:
            indices.append(2 * H + t - 1)
            values.append(-1.0)
    h.addRows(
        H,
        row_lower,
        row_upper,
        len(indices),
        np.array(starts, dtype=np.int32),
        np.array(indices, dtype=np.int32),
        np.array(values, dtype=np.float64),
    )
    h.run()
    col_val = np.array(h.getSolution().col_value, dtype=np.float64)
    c = col_val[:H]
    d = col_val[H : 2 * H]
    s = col_val[2 * H : 3 * H]
    # Check exact SoC conservation
    s_prev = np.concatenate([[s0], s[:-1]])
    max_soc_err = float(np.max(np.abs(s - (s_prev + eta * c - (1.0 / eta) * d))))
    profit = float(np.dot(prices, d - c))
    return {
        "status": str(h.getModelStatus()),
        "profit": round(profit, 6),
        "max_soc_conservation_err": max_soc_err,
        "end_soc_err": float(abs(s[-1] - s0)),
    }


def check_synthetic_baseline_solvers() -> dict:
    rng = np.random.default_rng(20261124)

    # 1. Exact LASSO coordinate descent at LEAR scale (N=1456, p=241)
    n_lear, p_lear = 1456, 241
    X = rng.standard_normal((n_lear, p_lear))
    X = (X - X.mean(axis=0)) / X.std(axis=0)
    b_true = np.zeros(p_lear)
    b_true[:12] = rng.uniform(-2.0, 2.0, size=12)
    y = X @ b_true + rng.standard_normal(n_lear)
    t0 = perf_counter()
    b_hat, kkt_err = lasso_coordinate_descent(X, y, lam=0.15)
    t_lasso = perf_counter() - t0

    # 2. Exact PAVA / IDR monotonicity & speed (N=182 calibration days, 99 thresholds)
    n_cal = 182
    scores_x = rng.standard_normal(n_cal)
    order = np.argsort(scores_x)
    y_cal = 50.0 + 10.0 * scores_x[order] + rng.standard_normal(n_cal) * 8.0
    thresholds = np.quantile(y_cal, np.linspace(0.01, 0.99, 99))
    t0 = perf_counter()
    max_mono_viol = 0.0
    for thr in thresholds:
        # IDR estimates P(Y <= thr | X = x) non-increasing in x => P(Y > thr | X = x) non-decreasing in x
        ind = (y_cal > thr).astype(np.float64)
        p_gt = pava_nondecreasing(ind)
        if len(p_gt) > 1:
            max_mono_viol = max(max_mono_viol, float(np.max(np.maximum(0.0, p_gt[:-1] - p_gt[1:]))))
    t_idr_99 = perf_counter() - t0

    # 3. Exact Quantile Regression LP via HiGHS (QRA: N=182, p=5, 19 deciles/quantiles)
    X_qra = np.column_stack([np.ones(n_cal), rng.standard_normal((n_cal, 4))])
    y_qra = 50.0 + X_qra[:, 1] * 8.0 + rng.standard_normal(n_cal) * 5.0
    t0 = perf_counter()
    statuses = set()
    for tau in np.linspace(0.05, 0.95, 19):
        _, st = solve_quantile_regression_highs(X_qra, y_qra, float(tau))
        statuses.add(st)
    t_qra_19 = perf_counter() - t0

    # 4. Online Conformal PID Controller (Angelopoulos et al. 2023) on synthetic regime shift (T=1000)
    T = 1000
    alpha = 0.10
    eta_pid = 0.05
    # Regime shift: noise jumps 3x at t=500
    errs_abs = np.concatenate([np.abs(rng.standard_normal(500)) * 5.0, np.abs(rng.standard_normal(500)) * 15.0])
    q_t = 8.0
    integrator = 0.0
    miscov = []
    for t in range(T):
        err_t = 1.0 if errs_abs[t] > q_t else 0.0
        miscov.append(err_t)
        integrator += err_t - alpha
        # Quantile tracker (P) + integral saturator (I, tan-like smooth saturation)
        q_t = max(0.0, q_t + eta_pid * (err_t - alpha) * 20.0 + 0.25 * np.tanh(integrator / 5.0))
    emp_cov = 1.0 - float(np.mean(miscov))

    # 5. Exact BESS Day-Ahead Arbitrage LP via HiGHS (1000 synthetic days)
    t0 = perf_counter()
    max_soc_err = 0.0
    bess_statuses = set()
    sample_profit = 0.0
    for d in range(1000):
        # Synthetic duck-curve day-ahead price profile
        h_idx = np.arange(24)
        p_day = 60.0 - 40.0 * np.exp(-0.5 * ((h_idx - 13.0) / 2.2) ** 2) + 55.0 * np.exp(-0.5 * ((h_idx - 19.0) / 1.8) ** 2) + rng.standard_normal(24) * 8.0
        res_lp = solve_bess_day_ahead_lp(p_day)
        bess_statuses.add(res_lp["status"])
        max_soc_err = max(max_soc_err, res_lp["max_soc_conservation_err"], res_lp["end_soc_err"])
        if d == 0:
            sample_profit = res_lp["profit"]
    t_bess_1000 = perf_counter() - t0

    return {
        "lear_lasso_cd_1456x241": {
            "elapsed_seconds_single_hour": round(t_lasso, 4),
            "nnz_recovered": int(np.sum(np.abs(b_hat) > 1e-8)),
            "max_kkt_optimality_error": kkt_err,
            "kkt_verified_le_1e_5": bool(kkt_err <= 1e-5),
        },
        "idr_exact_pava_182x99": {
            "elapsed_seconds_99_thresholds": round(t_idr_99, 4),
            "max_monotonicity_violation": max_mono_viol,
            "monotonicity_verified": bool(max_mono_viol <= 1e-12),
        },
        "qra_highs_lp_182x5_19quantiles": {
            "elapsed_seconds_19_quantiles": round(t_qra_19, 4),
            "highs_statuses": sorted(statuses),
            "all_optimal": statuses == {"HighsModelStatus.kOptimal"},
        },
        "conformal_pid_synthetic_3x_regime_shift_1000d": {
            "nominal_coverage": 1.0 - alpha,
            "empirical_coverage": round(emp_cov, 4),
            "abs_coverage_error": round(abs(emp_cov - (1.0 - alpha)), 4),
        },
        "bess_highs_lp_1000_days": {
            "elapsed_seconds_1000_days": round(t_bess_1000, 4),
            "highs_statuses": sorted(bess_statuses),
            "all_optimal": bess_statuses == {"HighsModelStatus.kOptimal"},
            "max_soc_conservation_error": max_soc_err,
            "sample_day0_profit": sample_profit,
        },
    }


def main() -> None:
    t_all = perf_counter()
    report = {
        "stage": "stage_0_non_outcome_input_literature_and_baseline_solver_check",
        "zero_real_holdout_outcomes_fitted_or_inspected": True,
        "arxiv_primary_sources": check_arxiv_primary_sources(),
        "epftoolbox_canonical_benchmark": check_epftoolbox_zenodo_and_github(),
        "smard_germany_live_api": check_smard_germany_api(),
        "synthetic_baseline_solver_integration": check_synthetic_baseline_solvers(),
        "total_elapsed_seconds": round(perf_counter() - t_all, 3),
    }
    OUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE={OUT_PATH} elapsed={report['total_elapsed_seconds']}s")
    print("ARXIV_PAPERS=", len(report["arxiv_primary_sources"]["papers"]))
    print("ZENODO_STATUS=", report["epftoolbox_canonical_benchmark"]["zenodo_http_status"], "FILES=", list(report["epftoolbox_canonical_benchmark"]["files"].keys()))
    print("SMARD_STATUSES=", {k: (v["index_http_status"], v["region_used"], v.get("chunks_from_2018_10"), v.get("chunks_from_2024_01")) for k, v in report["smard_germany_live_api"]["series"].items()})
    print("SOLVERS=", {k: v for k, v in report["synthetic_baseline_solver_integration"].items()})


if __name__ == "__main__":
    main()
