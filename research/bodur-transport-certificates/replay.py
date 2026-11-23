"""Run one Bodur treatment on a hash-pinned public input on a Linux host."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from urllib.request import Request, urlopen

from audit_witness import audit, read
from instrument import ENTRY, integrated_source


HERE = Path(__file__).resolve().parent
INPUTS = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
ARMS = ("clp", "tree", "tree-pivot")
SOLVER_SHA = "33102f8e324f2d283eb51b253002f20d8c76d5407012f35b7f5d935552a39ec2"
OUTPUT_CAP = 16 * 1024**2


def fetch_input(label, cache):
    item = INPUTS["checker"] if label == "checker" else INPUTS["cases"][label]
    name = item["url"].rsplit("/", 1)[-1]
    path = cache / name
    if path.exists():
        data = path.read_bytes()
    else:
        request = Request(item["url"], headers={"User-Agent": "Bodur-public-replay/1.0"})
        with urlopen(request, timeout=30) as response:
            data = response.read(item["bytes"] + 1)
    if len(data) != item["bytes"] or sha256(data).hexdigest() != item["sha256"]:
        raise ValueError(f"Public source size or SHA-256 mismatch for {name}")
    cache.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("xb") as stream:
            stream.write(data)
    return path.resolve()


def run_worker(command, workspace, log, cpus, wall):
    env = {**os.environ, "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}
    started = perf_counter()
    status = "completed"
    with log.open("wb") as stream:
        with subprocess.Popen(command, cwd=workspace, env=env, stdin=subprocess.DEVNULL,
                              stdout=stream, stderr=subprocess.STDOUT, start_new_session=True,
                              preexec_fn=lambda: os.sched_setaffinity(0, cpus)) as proc:
            try:
                proc.wait(timeout=max(0, wall - (perf_counter() - started)))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
                status = "deadline"
    return status, proc.returncode, perf_counter() - started


def replay(args, instance, checker, cpus):
    package = integrated_source()
    if sha256(package.encode()).hexdigest() != SOLVER_SHA:
        raise ValueError("Instrumented solver differs from the measured core")
    result = {"environment": "local_linux_host", "case": args.case, "arm": args.arm,
              "wall_limit_seconds": args.seconds, "cpu_affinity": sorted(cpus),
              "solver_python": sys.version.split()[0], "solver_packages": {k: version(k) for k in ("numpy", "ortools")},
              "input_sha256": INPUTS["cases"][args.case]["sha256"],
              "checker_sha256": INPUTS["checker"]["sha256"], "instrumented_core_sha256": SOLVER_SHA}
    witness = args.output / "solution.json"
    log = args.output / "solver.log"
    with TemporaryDirectory(prefix="bodur-replay-") as temporary:
        workspace = Path(temporary)
        (workspace / "solver_core.py").write_text(package, encoding="utf-8")
        for filename in ("official_tree.py", "tree_pivot.py"):
            (workspace / filename).write_bytes((HERE / filename).read_bytes())
        entry = workspace / "solve.py"
        entry.write_text(ENTRY.replace("__ARM__", repr(args.arm)), encoding="utf-8")
        command = [sys.executable, "-B", str(entry), "--problem", "bodur2017", "--instance", str(instance),
                   "--output", str(witness), "--time-limit", str(args.seconds)]
        status, rc, elapsed = run_worker(command, workspace, log, cpus, args.seconds)
    result.update(status=status, solver_exit=rc, host_wall_seconds=elapsed)
    trace_line = next((line.removeprefix("BODUR_TRACE ") for line in log.read_text(errors="replace").splitlines()
                       if line.startswith("BODUR_TRACE ")), None)
    result["trace"] = json.loads(trace_line) if trace_line else None
    if status != "completed" or rc != 0 or elapsed >= args.seconds:
        result["status"] = "deadline" if status == "deadline" or elapsed >= args.seconds else "solver_failed"
        return result
    if not witness.is_file() or witness.is_symlink() or witness.stat().st_size > OUTPUT_CAP:
        result["status"] = "invalid_witness_file"
        return result

    verdict = args.output / "public_checker.json"
    try:
        result["checker_python"] = subprocess.check_output([args.checker_python, "-V"], text=True, timeout=5).strip()
        check = subprocess.run([args.checker_python, "-I", "-B", str(checker), "--instance_path", str(instance),
                                "--solution_path", str(witness), "--result_path", str(verdict)],
                               stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
        (args.output / "checker.log").write_bytes(check.stdout + check.stderr)
        official = check.returncode == 0 and verdict.is_file() and json.loads(verdict.read_text()).get("feasible") is True
        independent = audit(read(instance), read(witness))
        result.update(official_checker=official, independent_audit=independent,
                      status="ok" if official and independent["valid"] else "failed_check")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, subprocess.SubprocessError) as error:
        result.update(status="failed_check", error=str(error))
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--case", choices=tuple(INPUTS["cases"]), required=True)
    cli.add_argument("--arm", choices=ARMS, required=True)
    cli.add_argument("--seconds", type=int, help="Defaults to 15 for tiny, 60 otherwise")
    cli.add_argument("--cpus", help="Comma-separated Linux CPU numbers. Defaults to two available CPUs")
    cli.add_argument("--checker-python", default=sys.executable, help="Prefer a separate CPython 3.12 binary")
    cli.add_argument("--cache", type=Path, default=Path(".bodur-inputs"))
    cli.add_argument("--output", type=Path, required=True, help="New path for local results")
    args = cli.parse_args()
    if not sys.platform.startswith("linux"):
        cli.error("The replay harness requires Linux")
    args.seconds = args.seconds if args.seconds is not None else (15 if args.case == "tiny" else 60)
    allowed = os.sched_getaffinity(0)
    cpus = set(map(int, args.cpus.split(","))) if args.cpus else set(sorted(allowed)[:2])
    if args.seconds < 1 or not cpus or not cpus <= allowed:
        cli.error("Use a positive deadline and available CPU numbers")
    instance = fetch_input(args.case, args.cache)
    checker = fetch_input("checker", args.cache)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True)
    result = replay(args, instance, checker, cpus)
    (args.output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"{args.case} {args.arm}: {result['status']}")
    if result["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
