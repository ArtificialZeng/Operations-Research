"""Replay one recorded ten-second arm with the original public checker on Linux."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from shutil import copyfile
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter


HERE = Path(__file__).resolve().parent
ARMS = {name: ("cutoff_solver.py", name, None) for name in ("cold", "fallback", "warm", "cutoff")}
ARMS.update({
    "window": ("window_solver.py", "window", "checkpoint_1.py"),
    "adaptive_original": ("window_solver.py", "adaptive_window", "checkpoint_1.py"),
    "adaptive_repaired": ("window_solver.py", "adaptive_window", "policy_matrix_compat.py"),
    "adaptive_stock_only": ("window_solver.py", "adaptive_window", "policy_stock_only.py"),
    "adaptive_without_stock": ("window_solver.py", "adaptive_window", "policy_without_stock.py"),
})


def verified(path, expected):
    if sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"SHA-256 mismatch for {path}")


def select_cpus(requested):
    available = os.sched_getaffinity(0)
    cpus = set(map(int, requested.split(","))) if requested else set(sorted(available)[:2])
    if len(cpus) != 2 or not cpus <= available:
        raise ValueError("Replay requires two distinct CPUs permitted by the current affinity")
    return cpus


def run_solver(folder, instance, output, solver_log):
    command = [sys.executable, str(folder / "solve.py"), "--problem", "degraeve2007",
               "--instance", str(instance), "--output", str(output), "--time-limit", "10"]
    started = perf_counter()
    with solver_log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=folder, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            status = process.wait(timeout=max(0.001, 10 - (perf_counter() - started)))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            return process.returncode, perf_counter() - started, "timeout"
    return status, perf_counter() - started, "ok" if status == 0 else "solver_or_setup_failed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--variant", choices=ARMS, required=True)
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--checker", type=Path, required=True)
    parser.add_argument("--checker-python", default="python3.12")
    parser.add_argument("--cpus", help="Two permitted CPU IDs separated by a comma")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    roster = json.loads((HERE / "provenance/conversion_manifest.json").read_bytes())["cases"]
    benchmark = json.loads((HERE / "provenance/replays.json").read_bytes())
    if args.case not in roster:
        parser.error("Unknown case for the 44-case benchmark")

    case = roster[args.case]
    instance, checker = (args.instances / case["file"]).resolve(), args.checker.resolve()
    verified(instance, case["sha256"])
    verified(checker, benchmark["checker_sha256"])
    cpus = select_cpus(args.cpus)
    os.sched_setaffinity(0, cpus)
    solver, arm, policy = ARMS[args.variant]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    solution, score = output / "solution.json", output / "public_checker.json"

    with TemporaryDirectory(prefix="fragkos-replay-") as temp:
        package = Path(temp)
        copyfile(HERE / solver, package / "warm_solver.py")
        copyfile(HERE / "opening_incumbent.py", package / "opening_incumbent.py")
        if solver == "window_solver.py":
            copyfile(HERE / "cutoff_solver.py", package / "cutoff_solver.py")
        if policy:
            copyfile(HERE / "policies" / policy, package / "window_policy.py")
        (package / "solve.py").write_text(
            "import sys\nfrom warm_solver import main\n\n"
            "if __name__ == '__main__':\n"
            f"    sys.argv.extend(['--experiment-arm', '{arm}'])\n    main()\n",
            encoding="utf-8",
        )
        exit_code, wall, status = run_solver(package, instance, solution, output / "solver.log")

    summary = {"case": args.case, "variant": args.variant, "arm": arm, "solver_exit": exit_code,
               "wall_limit_seconds": 10, "wall_seconds": wall, "cpus": sorted(cpus),
               "input_sha256": case["sha256"], "checker_sha256": benchmark["checker_sha256"],
               "status": status}
    if status == "ok" and solution.is_file():
        with (output / "checker.log").open("w", encoding="utf-8") as log:
            return_code = subprocess.run([args.checker_python, str(checker), "--instance_path", str(instance),
                "--solution_path", str(solution), "--result_path", str(score)],
                stdout=log, stderr=subprocess.STDOUT, check=False).returncode
        feasible = (return_code == 0 and score.is_file()
                    and json.loads(score.read_bytes()).get("feasible") is True)
        summary["official_checker"] = feasible
        if feasible:
            summary["objective"] = json.loads(solution.read_bytes())["objective_value"]
        else:
            summary["status"] = "checker_failed"
    elif status == "ok":
        summary["status"] = "missing_solution"
    summary_bytes = json.dumps(summary, indent=2, allow_nan=False) + "\n"
    (output / "result.json").write_text(summary_bytes, encoding="utf-8")
    print(summary_bytes, end="")


if __name__ == "__main__":
    main()
