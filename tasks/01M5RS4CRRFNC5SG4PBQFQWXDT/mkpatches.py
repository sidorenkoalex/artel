"""Временный генератор патчей мутаций (удаляется после шага)."""
import difflib
import subprocess
import sys
from pathlib import Path

WT = Path("/Users/al.sidorenko/projects/artel/.artel/projects/artel/worktrees/01M5RS4CRRFNC5SG4PBQFQWXDT")
DOCS = Path(__file__).resolve().parent
O = "orchestrator/advance_gates/outcome_integrity.py"

PRIOR_IF = "    if prior_paths:\n        paths = sorted(prior_paths)\n"
PRIOR_LINE_OLD = "        prior_line = [PRIOR_LINE.format(files=len(paths), runs=prior_runs)]\n"
FULL_IF = "    if any(files.is_support(p) for p in paths):\n        records = _full_run(task_id, profile, PRIOR, tree)\n"
RUNS_TEXT = '        runs = f"прежняя версия: {prior}; база: {base}"\n'
RERUNS = ("    reruns = (_rerun(profile, trees, red, history, sides=(PRIOR, BASE))\n"
          "              if red else 0)\n")
C_STATUS = ('                   if not status.startswith(("A", "C"))\n'
            "                   and (files.is_test(path) or files.is_support(path))}\n")
REPL_PATHS = "    prior_paths |= {project_profile.parse_test_id(cid)[1]\n"
TIMEOUT_BLOCK = ('        if run.timed_out:\n'
                 '            raise _Prepare(f"{where}: таймаут ({limit} с)")\n'
                 '        if run.state not in (outcome.GREEN, outcome.RED):\n'
                 '            raise _Prepare(f"{where}: исход «{run.state}» — {run.reason}")\n'
                 '        records, ran = list(run.tests), set(paths)\n')

M = {
    1: [(PRIOR_IF, PRIOR_IF.replace("if prior_paths:", "if prior_paths and False:"))],
    2: [(PRIOR_LINE_OLD, '        prior_line = [f"{PRIOR}: файлов; прогонов"]\n')],
    3: [(PRIOR_LINE_OLD, PRIOR_LINE_OLD.replace("files=len(paths)", "files=len(files.base_paths)"))],
    4: [(FULL_IF, FULL_IF.replace("if any(files.is_support(p) for p in paths):", "if True:"))],
    5: [(PRIOR_IF, PRIOR_IF.replace("if prior_paths:", "if True:"))],
    6: [("            found.append(Finding(PRIOR_RED, cid, runs))\n",
         "            found.append(Finding(BROKEN, cid, runs))\n")],
    7: [(RUNS_TEXT, '        runs = f"{prior}; база: {base}"\n')],
    8: [(RUNS_TEXT, '        runs = f"прежняя версия: {prior}"\n')],
    9: [("        elif all(is_red for is_red, _text in sides[PRIOR]):\n            found.append(Finding(PRIOR_RED",
          "        elif any(is_red for is_red, _text in sides[PRIOR]):\n            found.append(Finding(PRIOR_RED")],
    10: [(RERUNS, "    reruns = 0\n")],
    11: [(RERUNS, RERUNS.replace("sides=(PRIOR, BASE)", "sides=(PRIOR,)"))],
    12: [(RUNS_TEXT + "        if any(is_red for is_red, _text in sides[BASE]):\n",
          RUNS_TEXT + "        if False:\n")],
    13: [("        flaky += [cid for cid in prior_flaky if cid not in flaky]\n",
          "        flaky += []\n")],
    14: [("        findings += [f for f in prior_found if f.id not in taken]\n",
          "        findings += prior_found\n")],
    15: [("                   and (files.is_test(path) or files.is_support(path))}\n",
          "                   and files.is_test(path)}\n")],
    16: [("    if any(files.is_support(p) for p in paths):\n", "    if False:\n")],
    17: [("        run = acceptance.report_run(profile, tree, list(paths), limit)\n",
          "        run = acceptance.report_run(profile, tree, sorted(files.base_paths), limit)\n")],
    18: [(C_STATUS, C_STATUS.replace('("A", "C")', '("A", "C", "D")'))],
    19: [('    res = gitcmd.in_repo(tree, "checkout", base_sha, "--",\n'
          '                         *(f":(literal){p}" for p in paths))\n',
          '    kept = [p for p in paths if (tree / p).exists()]\n'
          '    res = (gitcmd.in_repo(tree, "checkout", base_sha, "--",\n'
          '                          *(f":(literal){p}" for p in kept))\n'
          '           if kept else subprocess.CompletedProcess([], 0, "", ""))\n')],
    20: [("    prior_paths = {path for status, path, _new in entries\n",
          '    prior_paths = {(_new if status.startswith("R") and _new else path)\n'
          "                   for status, path, _new in entries\n")],
    21: [("            target.unlink()\n    return tree\n",
          "            target.unlink()\n"
          "    for status, _path, new in entries:\n"
          '        if status.startswith("R") and new:\n'
          "            (tree / new).unlink(missing_ok=True)\n"
          "    return tree\n")],
    22: [(C_STATUS, C_STATUS.replace('if not status.startswith(("A", "C"))',
                                     'if status.startswith(("M", "D", "R"))'))],
    23: [(REPL_PATHS, "    if not profile.tests:\n        prior_paths |= files.base_paths\n" + REPL_PATHS)],
    24: [(REPL_PATHS, "    prior_paths |= {path for status, path, _new in entries\n"
                      '                    if status.startswith("A") and path in files.head_paths}\n'
          + REPL_PATHS)],
    25: [("    for case in records:\n        try:\n",
          "    for case in records:\n        if case.file_level:\n            continue\n        try:\n")],
    26: [("        tree = _prior_checkout(repo, scratch, trees, base_sha, head_sha,\n"
          "                               paths, files, entries)\n"
          "        prior_history, prior_red, prior_runs = _prior_versions(\n"
          "            task_id, profile, trees, tree, paths, files, base)\n",
          "        try:\n"
          "            tree = _prior_checkout(repo, scratch, trees, base_sha, head_sha,\n"
          "                                   paths, files, entries)\n"
          "        except _Prepare:\n"
          "            tree, paths = None, []\n"
          "        prior_history, prior_red, prior_runs = (_prior_versions(\n"
          "            task_id, profile, trees, tree, paths, files, base)\n"
          "            if tree is not None else ({}, [], 0))\n")],
    27: [(TIMEOUT_BLOCK,
          '        if run.timed_out:\n'
          '            records, ran = [], set(paths)\n'
          '        elif run.state not in (outcome.GREEN, outcome.RED):\n'
          '            raise _Prepare(f"{where}: исход «{run.state}» — {run.reason}")\n'
          '        else:\n'
          '            records, ran = list(run.tests), set(paths)\n')],
    28: [(TIMEOUT_BLOCK, TIMEOUT_BLOCK.replace(
          '            raise _Prepare(f"{where}: таймаут ({limit} с)")\n',
          '            return {}, [], 1\n'))],
    29: [("        return _judge(conn, task_id, branch, artifact_branch, profile,\n"
          "                      repo, scratch, trees, base_of, merge, extra)\n"
          "    except _Prepare as exc:\n"
          "        reason = str(exc)\n"
          "    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой не пропуск\n"
          '        reason = f"сбой {exc!r}"\n'
          "    finally:\n"
          "        for tree in trees.values():\n"
          '            gitcmd.in_repo(repo, "worktree", "remove", "--force", str(tree))\n'
          "        shutil.rmtree(scratch, ignore_errors=True)\n",
          "        result = _judge(conn, task_id, branch, artifact_branch, profile,\n"
          "                        repo, scratch, trees, base_of, merge, extra)\n"
          "        for tree in trees.values():\n"
          '            gitcmd.in_repo(repo, "worktree", "remove", "--force", str(tree))\n'
          "        shutil.rmtree(scratch, ignore_errors=True)\n"
          "        return result\n"
          "    except _Prepare as exc:\n"
          "        reason = str(exc)\n"
          "    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой не пропуск\n"
          '        reason = f"сбой {exc!r}"\n')],
    30: [("    if entries is None:\n        raise _Prepare(f\"diff --name-status",
          "    if entries is None:\n        return []\n        raise _Prepare(f\"diff --name-status")],
    31: [("    if res.returncode != 0:\n        reason = (res.stderr or b\"\")",
          "    if res.returncode != 0:\n        return {}\n        reason = (res.stderr or b\"\")")],
    32: [("    tree = scratch / _PRIOR_DIR\n",
          '    tree = Path(tempfile.mkdtemp(prefix="artel-prior-")).resolve() / _PRIOR_DIR\n')],
    33: [("    trees[PRIOR] = tree\n", "")],
    34: [("        if self.is_support(path):\n            return True\n        if self.profile.tests:\n",
          "        if self.profile.tests:\n")],
    35: [("        if self.profile.tests:\n            return self.is_test(path)\n",
          "        if path not in self.head_paths:\n            return False\n"
          "        if self.profile.tests:\n            return self.is_test(path)\n")],
    36: [("        case = by_id.get(b.id)\n        green = case is not None and in_pass_to_pass(case)\n",
          "        case = by_id.get(b.id)\n"
          "        green = case is None or case.outcome not in (outcome.FAILED, outcome.ERROR)\n")],
    37: [("    if decision.refusal or decision.skip or \\\n"
          "            not in_outcome_bounds(decision.profile):\n",
          "    if decision.refusal or decision.skip or \\\n"
          "            not project_profile.reported(decision.profile):\n")],
}


def main():
    src = subprocess.run(["git", "-C", str(WT), "show", f"HEAD:{O}"],
                         capture_output=True, text=True, check=True).stdout
    for n, edits in sorted(M.items()):
        text = src
        for old, new in edits:
            if text.count(old) != 1:
                sys.exit(f"мутация {n}: якорь встречается {text.count(old)} раз")
            text = text.replace(old, new)
        compile(text, O, "exec")
        diff = difflib.unified_diff(src.splitlines(True), text.splitlines(True),
                                    f"a/{O}", f"b/{O}", n=3)
        body = f"diff --git a/{O} b/{O}\n" + "".join(diff)
        (DOCS / f"mutation-{n:03d}.diff").write_text(body, encoding="utf-8")
        check = subprocess.run(["git", "-C", str(WT), "apply", "--check",
                                str(DOCS / f"mutation-{n:03d}.diff")],
                               capture_output=True, text=True)
        print(n, "ok" if check.returncode == 0 else check.stderr.strip())


main()
