#!/usr/bin/env python3
"""Noninteractive project-parallel wrapper for official MuMuTestUp sample runner.

One worker per repository preserves the official checkout/build isolation.
This wrapper records terminal task outcomes without equating them to test passes.
"""
import argparse
import contextlib
import dataclasses
from datetime import datetime, timezone
from enum import Enum
import fcntl
import functools
import hashlib
import inspect
import json
import multiprocessing
import os
from pathlib import Path
import re
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor, as_completed


def now():
    return datetime.now(timezone.utc).isoformat()


def json_default(value):
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(data, default=json_default, ensure_ascii=False, indent=2) + "\n")
    os.replace(temp, path)


def report_fingerprint(path):
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size, hashlib.sha256(path.read_bytes()).hexdigest())


def select_sample_java(row, project_path, fallback, evidence):
    raw = row.get("tgt_java_version")
    if raw is not None and str(raw).strip():
        version = str(raw).strip().removesuffix(".0")
        if version not in ("8", "11", "17", "21"):
            raise ValueError(f"Unsupported dataset tgt_java_version: {raw}")
        evidence.update(source="dataset.tgt_java_version", actual_version=version)
    else:
        version = fallback(project_path)
        evidence.update(source="fallback_pom_detection", actual_version=version)
    return version


def focal_metadata_evidence(row):
    focal = row.get("focal_method", {})
    before = focal.get("b_focal_method_code", {})
    after = focal.get("a_focal_method_code", {})
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    declared, old, new = focal.get("focal_method_name"), before.get("simpleName"), after.get("simpleName")
    return {"declared_name": declared, "declared_before_name": old, "declared_after_name": new,
            "name_mismatch": bool(old and new and old != new),
            "declared_after_name_mismatch": bool(declared and new and declared != new),
            "before_lines": [before.get("startLine"), before.get("endLine")],
            "after_lines": [after.get("startLine"), after.get("endLine")],
            "after_path": focal.get("a_focal_method_path"),
            "interpretation": "Metadata only; possible rename or incorrect pairing; official focal selection retained."}


def surefire_report_paths(report_dir):
    return [*report_dir.glob("TEST-*.xml"), *report_dir.glob("*.txt")]


def exact_test_selector(maven_commands, test_class, test_method):
    expected = {f"{test_class}#{test_method}", f"{test_class.rsplit('.', 1)[-1]}#{test_method}"}
    provenance = []
    for index, command in enumerate(maven_commands or []):
        arguments = command.get("command", [])
        selectors = [argument[len("-Dtest="):] for argument in arguments
                     if isinstance(argument, str) and argument.startswith("-Dtest=")]
        ambiguous = any(argument == "-Dtest" or
                        (index > 0 and arguments[index - 1] == "-D" and
                         isinstance(argument, str) and argument.startswith("test="))
                        for index, argument in enumerate(arguments))
        provenance.append({"command_index": index, "selectors": selectors,
                           "ambiguous_selector": ambiguous,
                           "exact_target": not ambiguous and len(selectors) == 1 and selectors[0] in expected})
    return bool(test_class and test_method and provenance) and all(
        row["exact_target"] for row in provenance), provenance


def surefire_evidence(report_paths, before, started, test_class, test_method, maven_commands=None):
    paths = sorted(set(report_paths))
    evidence = {"target_class": test_class, "target_method": test_method,
                "format": "xml", "matched": 0, "passed": 0, "failed": 0, "skipped": 0, "reports": []}
    for path in (path for path in paths if path.suffix == ".xml"):
        fingerprint = report_fingerprint(path)
        fresh = fingerprint != before.get(str(path)) and path.stat().st_mtime >= started - 1.0
        row = {"path": str(path), "format": "xml", "fresh": fresh, "matched": 0}
        try:
            root = ET.parse(path).getroot()
            for case in root.iter("testcase"):
                name = case.get("name", "")
                class_name = case.get("classname", root.get("name", ""))
                if class_name != test_class or not (name == test_method or name.startswith(test_method + "[") or name.startswith(test_method + "(")):
                    continue
                row["matched"] += 1
                if not fresh:
                    continue
                evidence["matched"] += 1
                if case.find("skipped") is not None:
                    evidence["skipped"] += 1
                elif case.find("failure") is not None or case.find("error") is not None:
                    evidence["failed"] += 1
                else:
                    evidence["passed"] += 1
        except ET.ParseError as error:
            row["parse_error"] = str(error)
        evidence["reports"].append(row)
    # Even a stale matching XML report blocks fallback: never hide its evidence
    # behind a more permissive report format.
    if any(row["matched"] for row in evidence["reports"]):
        return evidence
    selector_ok, provenance = exact_test_selector(maven_commands, test_class, test_method)
    evidence["selector_provenance"] = provenance
    for path in (path for path in paths if path.suffix == ".txt"):
        fresh = report_fingerprint(path) != before.get(str(path)) and path.stat().st_mtime >= started - 1.0
        row = {"path": str(path), "format": "txt", "fresh": fresh, "matched": 0}
        evidence["reports"].append(row)
        text = path.read_text(encoding="utf-8", errors="replace")
        classes = re.findall(r"^Test set:\s*([^\r\n]+)", text, re.MULTILINE)
        counts = re.findall(r"^Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)(?:,|\s*$)",
                            text, re.MULTILINE)
        if len(classes) != 1 or classes[0].strip() != test_class or len(counts) != 1:
            row["rejected_reason"] = "missing_or_mismatched_test_set_or_counts"
            continue
        tests, failures, errors, skipped = map(int, counts[0])
        row["counts"] = {"tests": tests, "failures": failures, "errors": errors, "skipped": skipped}
        if tests != 1 or failures + errors + skipped > 1:
            row["rejected_reason"] = "not_exactly_one_test_or_inconsistent_counts"
            continue
        if not selector_ok:
            row["rejected_reason"] = "maven_did_not_select_exact_target_method"
            continue
        row["matched"] = 1
        evidence["format"] = "txt"
        if fresh:
            evidence["matched"] += 1
            evidence["failed"] += failures + errors
            evidence["skipped"] += skipped
            evidence["passed"] += tests - failures - errors - skipped
    return evidence


def install_execution_guards(executor_class, phase_evidence=None):
    """Stop if the generated test was not installed; never run the reference test.

    The upstream runner catches exceptions and returns None, so retain the reason
    outside the executor as well. These guards do not change pass criteria.
    """
    violations = []
    if phase_evidence is None:
        phase_evidence = []

    def fail(message):
        violations.append(message)
        raise RuntimeError("MuMuTestUp execution guard: " + message)

    execute = executor_class.execute_test
    execute_signature = inspect.signature(execute)

    @functools.wraps(execute)
    def execute_guard(self, *args, **kwargs):
        self._mumu_installed_test = None
        self._mumu_maven_commands = []
        bound = execute_signature.bind(self, *args, **kwargs)
        bound.apply_defaults()
        path = bound.arguments.get("test_rel_path")
        if not path or not (self.project_path / path).is_file():
            fail(f"Target test file is unavailable: {path}")
        return execute(self, *args, **kwargs)

    executor_class.execute_test = execute_guard

    command_executor = executor_class._execute_maven_command

    @functools.wraps(command_executor)
    def command_recorder(self, cmd):
        # Disable build-time source rewriting and unrelated integration tests.
        # Keep generated-source hash guards and unit-test execution unchanged.
        cmd = list(cmd)
        project = str(self.project_path)
        if 'Wikidata-Toolkit' in project:
            cmd += ['-Dlicense.skipUpdateLicense=true', '-Dlicense.skipUpdateProjectLicense=true']
        if 'neo4j-java-driver' in project and 'install' in cmd:
            cmd += ['-DskipITs=true']
        entry = {"command": list(cmd), "started_at": now()}
        self._mumu_maven_commands.append(entry)
        try:
            result = command_executor(self, cmd)
            entry["returncode"] = result.get("returncode")
            directory = getattr(self, "current_iteration_dir", None)
            if directory:
                directory = Path(directory)
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / f"maven-command-{len(self._mumu_maven_commands):02d}.log"
                path.write_text(result.get("output", ""))
                entry["output_log"] = str(path)
            return result
        except Exception as error:
            entry["exception"] = repr(error)
            raise
        finally:
            entry["finished_at"] = now()

    executor_class._execute_maven_command = command_recorder

    def make_replace_guard(original):
        @functools.wraps(original)
        def replace_guard(self, test_file, *args, **kwargs):
            result = original(self, test_file, *args, **kwargs)
            if not result or not result[0]:
                fail(f"Generated test replacement failed: {test_file}")
            path = Path(test_file)
            if not path.is_file():
                fail(f"Replaced test file disappeared: {path}")
            self._mumu_installed_test = (path, hashlib.sha256(path.read_bytes()).hexdigest())
            return result
        return replace_guard

    for name in ("_replace_test_method_in_file", "_replace_test_method_in_file_simple"):
        setattr(executor_class, name, make_replace_guard(getattr(executor_class, name)))

    def make_phase_guard(original, phase):
        signature = inspect.signature(original)
        @functools.wraps(original)
        def phase_guard(self, *args, **kwargs):
            installed = getattr(self, "_mumu_installed_test", None)
            if not installed:
                fail(f"{phase} requested without successful generated-test installation")
            path, digest = installed
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                fail(f"Installed generated test changed before {phase}: {path}")
            bound = signature.bind(self, *args, **kwargs)
            bound.apply_defaults()
            test_class = bound.arguments.get("test_class", "")
            test_method = bound.arguments.get("test_method", "")
            pom = self._find_parent_pom(path)
            report_dir = (pom.parent if pom else self.project_path) / "target" / "surefire-reports"
            before = {str(p): report_fingerprint(p) for p in surefire_report_paths(report_dir)}
            pit_dir = Path(self.current_iteration_dir) / "pitest" if self.current_iteration_dir else None
            pit_before = {str(p): report_fingerprint(p) for p in pit_dir.rglob("mutations.xml")} if pit_dir else {}
            started = time.time()
            command_start = len(self._mumu_maven_commands)
            event = {"phase": phase, "started_at": now(), "test_file": str(path), "installed_sha256": digest,
                     "iteration_directory": str(getattr(self, "current_iteration_dir", ""))}
            phase_evidence.append(event)
            try:
                result = original(self, *args, **kwargs)
            except Exception as error:
                event["exception"] = repr(error)
                raise
            finally:
                event["finished_at"] = now()
                event["maven_commands"] = self._mumu_maven_commands[command_start:]
            status = result.get("status") if isinstance(result, dict) else None
            event["upstream_status"] = status
            if phase == "_run_jacoco":
                evidence = surefire_evidence(surefire_report_paths(report_dir), before, started,
                                             test_class, test_method, event["maven_commands"])
                event["surefire"] = evidence
                # Genuine compiler and test failures remain model-visible failures.
                if status in ("COMPILE_ERROR", "RUN_FAIL"):
                    return result
                if status != "SUCCESS":
                    fail(f"JaCoCo infrastructure did not complete: {status}")
                if evidence["matched"] - evidence["skipped"] <= 0:
                    fail("Maven reported success without a fresh, non-skipped target Surefire testcase")
                if evidence["failed"]:
                    result["status"] = "RUN_FAIL"
                    result["error_message"] = f"Fresh Surefire reports {evidence['failed']} failure(s) for {test_class}#{test_method}"
                    result["raw_error_output"] = result["error_message"]
                    event["effective_status"] = "RUN_FAIL"
            else:
                if status != "SUCCESS":
                    fail(f"PIT infrastructure did not complete: {status}")
                commands = event["maven_commands"]
                if any(command.get("returncode") != 0 for command in commands):
                    fail("PIT returned SUCCESS despite a failed Maven command")
                reports = sorted(p for p in pit_dir.rglob("mutations.xml")
                                 if p.stat().st_mtime >= started - 1.0 and report_fingerprint(p) != pit_before.get(str(p))) if pit_dir else []
                event["mutation_reports"] = [str(p) for p in reports]
                if not reports:
                    fail("PIT returned SUCCESS without a fresh mutations.xml report")
                try:
                    mutations = [m for report in reports for m in ET.parse(report).getroot().iter("mutation")]
                except ET.ParseError as error:
                    fail(f"PIT mutation report is malformed: {error}")
                event["mutation_count_in_xml"] = len(mutations)
                event["killing_tests"] = sorted({m.findtext("killingTest") for m in mutations if m.findtext("killingTest")})
            return result
        return phase_guard

    for name in ("_run_jacoco", "_run_pitest"):
        setattr(executor_class, name, make_phase_guard(getattr(executor_class, name), name))
    return violations


def worker(job):
    upstream, dataset_path, output, indices, resume = job
    upstream, dataset_path, output = map(Path, (upstream, dataset_path, output))
    project = "/".join(dataset_path.parts[-3:-1])
    project_out = output / "projects" / project
    project_out.mkdir(parents=True, exist_ok=True)
    os.environ["MUMU_FRAMEWORK_LOG"] = str(project_out / "framework.log")
    os.environ["MUMU_LOGS_DIR"] = str(output / "sample-logs")
    os.environ["MUMU_REPORTS_DIR"] = str(output / "reports")
    os.environ["MUMU_INDEX_DIR"] = str(output / "index_data")
    os.chdir(upstream)
    sys.path.insert(0, str(upstream))
    rows = json.loads(dataset_path.read_text())
    statuses = {}
    with (project_out / "worker.log").open("a", buffering=1) as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        # Import only after per-process runtime/log configuration has been set.
        import run_complete_beam_multi as official_runner
        run_beam_with_real_execution = official_runner.run_beam_with_real_execution
        original_java_detector = official_runner.detect_java_version
        from java_test_executor import JavaTestExecutor
        phase_evidence = []
        guard_violations = install_execution_guards(JavaTestExecutor, phase_evidence)
        for index in indices:
            row = rows[index]
            destination = project_out / "samples" / f"{index:04d}.json"
            if resume and destination.exists():
                previous = json.loads(destination.read_text())
                if previous.get("state") == "finished":
                    statuses[previous.get("test_status", "no_result")] = statuses.get(previous.get("test_status", "no_result"), 0) + 1
                    continue
            start = time.monotonic()
            record = {"sample_id": row.get("ID"), "index": index, "project": project,
                      "aCommit": row["aCommit"], "bCommit": row["bCommit"],
                      "state": "running", "started_at": now(), "worker_pid": os.getpid()}
            java_choice = {"dataset_tgt_java_version": row.get("tgt_java_version")}
            def select_java(project_path):
                return select_sample_java(row, project_path, original_java_detector, java_choice)
            official_runner.detect_java_version = select_java
            record["java_selection"] = java_choice
            record["focal_metadata"] = focal_metadata_evidence(row)
            save(destination, record)
            save(project_out / "progress.json", {"state": "running", "current_index": index,
                 "sample_id": row.get("ID"), "pid": os.getpid(), "updated_at": now(), "statuses": statuses})
            try:
                guard_violations.clear()
                phase_evidence.clear()
                result = run_beam_with_real_execution(index, str(dataset_path), None)
                record["result"] = result
                record["test_status"] = result.test_result.status.value if result is not None else "no_result"
            except Exception:
                record["test_status"] = "harness_error"
                record["traceback"] = traceback.format_exc()
            if guard_violations:
                record["test_status"] = "harness_error"
                record["execution_guard_violations"] = list(guard_violations)
            record["phase_evidence"] = list(phase_evidence)
            record.update(state="finished", finished_at=now(), elapsed_seconds=round(time.monotonic() - start, 3))
            save(destination, record)
            status = record["test_status"]
            statuses[status] = statuses.get(status, 0) + 1
            save(project_out / "progress.json", {"state": "running", "completed": sum(statuses.values()),
                 "total": len(indices), "pid": os.getpid(), "updated_at": now(), "statuses": statuses})
    report = {"project": project, "state": "finished", "total": len(indices), "statuses": statuses, "finished_at": now()}
    save(project_out / "progress.json", report)
    return report


def preflight(upstream, dataset_root, projects):
    sys.path.insert(0, str(upstream))
    from config import config
    required_env = ("MUMU_EMBEDDING_BASE_URL", "MUMU_EMBEDDING_MODEL")
    for variable in required_env:
        if not os.getenv(variable):
            raise RuntimeError(f"Missing {variable}; semantic retrieval must remain enabled")
    if config.llm.provider != "openai" or not config.llm.api_url:
        raise RuntimeError("Set LLM_PROVIDER=openai and LLM_API_URL to the local /v1/chat/completions endpoint")
    if not (Path(config.java.maven_home) / "bin/mvn").is_file():
        raise RuntimeError(f"Maven missing: {config.java.maven_home}")
    for version, home in config.java.java_homes.items():
        if not (Path(home) / "bin/java").is_file():
            raise RuntimeError(f"JDK {version} missing: {home}")
    for project in projects:
        if not (Path(config.java.repos_dir) / project / ".git").exists():
            raise RuntimeError(f"Repository missing: {project}")
    for name in ("ablation_disable_mutation", "ablation_disable_coverage", "ablation_disable_retrieval",
                 "all_ablation_disable_mutation", "all_ablation_disable_coverage", "all_ablation_disable_error"):
        if getattr(config.framework, name):
            raise RuntimeError(f"Core component is disabled: {name}")
    return {"execution_protocol": "generated-test-and-fresh-phase-evidence-v2", "model": config.llm.model, "api_url": config.llm.api_url, "temperature": config.llm.temperature,
            "max_iterations": config.framework.max_iterations, "embedding_model": os.environ["MUMU_EMBEDDING_MODEL"],
            "embedding_url": os.environ["MUMU_EMBEDDING_BASE_URL"], "repo_dir": config.java.repos_dir,
            "maven_home": config.java.maven_home, "java_homes": config.java.java_homes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--project", action="append", help="Optional explicit project restriction; omit for all ten")
    parser.add_argument("--samples-per-project", type=int, help="Smoke-test limit only; omit for full dataset")
    parser.add_argument("--sample-index", type=int, help="One explicit sample; requires exactly one --project")
    parser.add_argument("--extra-sample", action="append", default=[], metavar="PROJECT:INDEX",
                        help="Append an explicit dataset index after the per-project limit; repeatable")
    parser.add_argument("--selection-file", type=Path)
    parser.add_argument("--resume", action="store_true", help="Skip recorded terminal samples, including failed tests")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    upstream, output = args.upstream.resolve(), args.output.resolve()
    dataset_root = (args.dataset_root or upstream / "dataset").resolve()
    if args.workers < 1 or (args.samples_per_project is not None and args.samples_per_project < 1):
        parser.error("Worker and sample counts must be positive")
    if args.sample_index is not None and len(args.project or []) != 1:
        parser.error("--sample-index requires exactly one --project")
    output.mkdir(parents=True, exist_ok=True)
    # A source-tree-wide lock protects shared checkout paths across separate launches.
    with (upstream / ".local-run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another MuMuTestUp launch owns this source tree")
        paths = sorted(dataset_root.glob("*/*/data.json"))
        if args.project:
            paths = [p for p in paths if "/".join(p.parts[-3:-1]) in args.project]
            if len(paths) != len(set(args.project)):
                parser.error("At least one requested project is absent")
        if not paths:
            parser.error("No dataset files found")
        selection = json.loads(args.selection_file.read_text()) if args.selection_file else None
        if selection is not None:
            paths = [p for p in paths if "/".join(p.parts[-3:-1]) in selection]
            if len(paths) != len(selection):
                parser.error("Selection contains unknown project")
        projects = ["/".join(p.parts[-3:-1]) for p in paths]
        extra_indices = {}
        for item in args.extra_sample:
            try:
                project, raw_index = item.rsplit(":", 1)
                extra_index = int(raw_index)
            except ValueError:
                parser.error("--extra-sample must be PROJECT:INDEX with an integer dataset index")
            if project not in projects or extra_index < 0:
                parser.error("--extra-sample requires a selected project and a nonnegative index")
            extra_indices.setdefault(project, []).append(extra_index)
        runtime = preflight(upstream, dataset_root, projects)
        jobs, records = [], []
        for p in paths:
            data = json.loads(p.read_text())
            indices = list(range(len(data)))
            if args.sample_index is not None:
                if args.sample_index < 0 or args.sample_index >= len(data):
                    parser.error("Sample index out of range")
                indices = [args.sample_index]
            elif args.samples_per_project is not None:
                indices = indices[:args.samples_per_project]
            project = "/".join(p.parts[-3:-1])
            for extra_index in extra_indices.get(project, []):
                if extra_index >= len(data):
                    parser.error(f"Extra sample index out of range: {project}:{extra_index}")
                if extra_index in indices:
                    parser.error(f"Extra sample is already selected: {project}:{extra_index}")
                indices.append(extra_index)
            if selection is not None:
                indices = selection[project]
                if not indices or len(indices) != len(set(indices)) or any(not isinstance(i, int) or i < 0 or i >= len(data) for i in indices):
                    parser.error("Invalid recovery indices")
            jobs.append((str(upstream), str(p), str(output), indices, args.resume))
            records.append({"project": "/".join(p.parts[-3:-1]), "path": str(p),
                            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "available": len(data),
                            "selected_indices": indices, "sample_ids": [data[i].get("ID") for i in indices]})
        manifest = {"created_at": now(), "pid": os.getpid(), "runtime": runtime,
                    "workers": min(args.workers, len(jobs)), "datasets": records,
                    "selected_count": sum(len(x[3]) for x in jobs), "scope": "full" if selection is None and not args.project and args.samples_per_project is None else "explicit_subset"}
        previous_manifest = output / "run-manifest.json"
        if previous_manifest.exists() and (output / "status.json").exists():
            if not args.resume:
                raise SystemExit("Output already contains a run; use --resume or a new output directory")
            previous = json.loads(previous_manifest.read_text())
            for key in ("runtime", "datasets", "scope"):
                if previous.get(key) != manifest[key]:
                    raise SystemExit(f"Resume configuration differs in {key}; use a new output directory")
            manifest["original_created_at"] = previous.get("original_created_at", previous["created_at"])
        save(output / "run-manifest.json", manifest)
        print(json.dumps({"manifest": str(output / "run-manifest.json"), "selected_count": manifest["selected_count"], "workers": manifest["workers"]}), flush=True)
        if args.preflight_only:
            return
        state = {"state": "running", "pid": os.getpid(), "started_at": now(), "completed_projects": []}
        save(output / "status.json", state)
        with ProcessPoolExecutor(max_workers=manifest["workers"], mp_context=multiprocessing.get_context("spawn")) as pool:
            futures = {pool.submit(worker, job): "/".join(Path(job[1]).parts[-3:-1]) for job in jobs}
            for future in as_completed(futures):
                try:
                    report = future.result()
                except Exception:
                    report = {"project": futures[future], "state": "worker_failed", "traceback": traceback.format_exc()}
                state["completed_projects"].append(report)
                state["updated_at"] = now()
                save(output / "status.json", state)
                print(json.dumps(report), flush=True)
        state.update(state="finished", finished_at=now())
        save(output / "status.json", state)


if __name__ == "__main__":
    main()
