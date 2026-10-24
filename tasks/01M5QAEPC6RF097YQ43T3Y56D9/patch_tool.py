"""Временная сборка патчей мутаций (удаляется к концу работы над набором).

python3 patch_tool.py <номер>[,<номер>…]  — пишет mutation-<nnn>.diff и
проверяет `git apply --check` на рабочей копии.
"""
import difflib
import subprocess
import sys
from pathlib import Path

D = Path("/Users/al.sidorenko/projects/artel/.artel/projects/artel/tasks/01M5QAEPC6RF097YQ43T3Y56D9")
WT = Path("/Users/al.sidorenko/projects/artel/.artel/projects/artel/worktrees/01M5QAEPC6RF097YQ43T3Y56D9")
OI = "orchestrator/advance_gates/outcome_integrity.py"
ACC = "orchestrator/advance_gates/acceptance.py"

FULL_RUN_IF = '''    if run.outcome in (acceptance.FULL_SUITE_NOT_STARTED,
                       acceptance.FULL_SUITE_TIMEOUT):
        raise _Prepare('''

RERUN_CHECKS = '''                if run.refusal:
                    raise _Prepare(f"{where}: {run.refusal}")
                if run.timed_out:
                    raise _Prepare(f"{where}: таймаут ({limit} с)")
                if run.state not in (outcome.GREEN, outcome.RED):
                    raise _Prepare(f"{where}: исход «{run.state}» — {run.reason}")
'''

BASE_CHECK = '''                    if side == BASE and (case is None
                                         or case.outcome == outcome.SKIPPED):
                        raise _Prepare(f"{where}: у теста {cid} {describe(case)}"
                                       f" — исход базы не судим")
'''

GREEN = "                    green = case is not None and in_pass_to_pass(case)\n"

PATCHES = {
    6: [(OI, '''    except _Prepare as exc:
        reason = str(exc)
    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой не пропуск
        reason = f"сбой {exc!r}"
    finally:''', '''    except _Prepare as exc:
        if "не определена" in str(exc):
            return None
        reason = str(exc)
    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой не пропуск
        reason = f"сбой {exc!r}"
    finally:''')],
    8: [(OI, FULL_RUN_IF, FULL_RUN_IF.replace(
        "        raise _Prepare(",
        "        if side == BASE and run.outcome == acceptance.FULL_SUITE_NOT_STARTED:\n"
        "            return []\n        raise _Prepare("))],
    15: [(OI, RERUN_CHECKS, RERUN_CHECKS.replace(
        '''                if run.state not in (outcome.GREEN, outcome.RED):
                    raise _Prepare(f"{where}: исход «{run.state}» — {run.reason}")
''', ""))],
    16: [(OI, BASE_CHECK, '''                    if side == BASE and case is None:
                        raise _Prepare(f"{where}: у теста {cid} {describe(case)}"
                                       f" — исход базы не судим")
''')],
    18: [(OI, GREEN, "                    green = case is not None and (\n"
                     "                        case.outcome == outcome.SKIPPED or in_pass_to_pass(case))\n")],
    31: [(OI, '''    if decision.refusal or decision.skip or \\
            not in_outcome_bounds(decision.profile):''',
          '''    if decision.refusal or decision.skip or \\
            not project_profile.reported(decision.profile):''')],
    32: [(OI, '''    profile = _bounds(t["is_canary"], t["target"])
    if profile is None:
        return None
    return _gate(''', '''    decision = project_profile.decide(t["target"])
    if decision.refusal and not t["is_canary"]:
        return GateRefusal(OUTCOME_REFUSAL_ACTION, decision.refusal, "")
    profile = _bounds(t["is_canary"], t["target"])
    if profile is None:
        return None
    return _gate(''')],
    33: [(OI, '''    decision = project_profile.decide(target)
    if decision.refusal or decision.skip or \\''', '''    decision = project_profile.decide(target)
    if decision.refusal:
        profiles = project_profile.component_profiles(target)
        return profiles[0] if profiles else None
    if decision.refusal or decision.skip or \\''')],
    34: [(OI, '''    return {side: _full_run(task_id, profile, side, tree)
            for side, tree in trees.items()}''', '''    trees = {**trees, HEAD: workspace.path(task_id)}
    return {side: _full_run(task_id, profile, side, tree)
            for side, tree in trees.items()}''')],
    35: [(OI, '''    return {side: _full_run(task_id, profile, side, tree)
            for side, tree in trees.items()}''', '''    return {side: _full_run(task_id, profile, side, trees[HEAD])
            for side, tree in trees.items()}''')],
    36: [(OI, '''    except _Prepare as exc:
        reason = str(exc)
    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой не пропуск
        reason = f"сбой {exc!r}"
    finally:''', '''    except _Prepare as exc:
        if "не прочитана" in str(exc):
            return None
        reason = str(exc)
    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой не пропуск
        reason = f"сбой {exc!r}"
    finally:''')],
    37: [(OI, FULL_RUN_IF, FULL_RUN_IF.replace(
        "        raise _Prepare(",
        "        if side == BASE and run.outcome == acceptance.FULL_SUITE_TIMEOUT:\n"
        "            return []\n        raise _Prepare("))],
    38: [(OI, FULL_RUN_IF, FULL_RUN_IF.replace(
        "        raise _Prepare(",
        "        if side == HEAD and run.outcome == acceptance.FULL_SUITE_TIMEOUT:\n"
        "            return list(run.tests)\n        raise _Prepare("))],
    39: [(OI, FULL_RUN_IF, FULL_RUN_IF.replace(
        "        raise _Prepare(",
        "        if side == HEAD and run.outcome == acceptance.FULL_SUITE_NOT_STARTED:\n"
        "            return list(run.tests)\n        raise _Prepare("))],
    40: [(OI, FULL_RUN_IF, FULL_RUN_IF.replace(
        "        raise _Prepare(",
        "        if side == HEAD and run.outcome == acceptance.FULL_SUITE_NOT_STARTED:\n"
        "            return []\n        raise _Prepare("))],
    41: [(OI, '''    findings = senior + [f for f in compare(base, head) if f.id not in taken]
''', '''    findings = senior + [f for f in compare(base, head) if f.id not in taken]
    if not base:
        findings += [Finding(GONE, c.id, "база: нет тестов") for c in head]
''')],
    42: [(OI, '''def _rerun(profile, trees: dict, red: list, history: dict,
           sides: tuple = (HEAD, BASE)) -> int:''', '''def _rerun(profile, trees: dict, red: list, history: dict,
           sides: tuple = (HEAD, BASE), paths=None) -> int:'''),
         (OI, "                run = acceptance.report_run(profile, trees[side], [path], limit)\n",
          "                run = acceptance.report_run(profile, trees[side], paths or [path], limit)\n"),
         (OI, "    file_runs = _rerun(profile, trees, red, history) if red else 0\n",
          "    file_runs = (_rerun(profile, trees, red, history,\n"
          "                        paths=sorted(_record_paths(base))) if red else 0)\n")],
    43: [(OI, "    limit = project_profile.component_limit(profile)[0]\n    count = 0\n",
          "    limit = config.FULL_SUITE_TIMEOUT_SEC\n    count = 0\n")],
    44: [(OI, "    limit = project_profile.component_limit(profile)[0]\n    count = 0\n",
          "    limit = config.ACCEPTANCE_TIMEOUT_SEC\n    count = 0\n")],
    45: [(OI, RERUN_CHECKS, RERUN_CHECKS.replace(
        '''                if run.refusal:
                    raise _Prepare(f"{where}: {run.refusal}")
''', '''                if run.refusal:
                    run = acceptance.report_run(profile, trees[side], None, limit)
'''))],
    46: [(OI, RERUN_CHECKS, RERUN_CHECKS.replace(
        '''                if run.timed_out:
                    raise _Prepare(f"{where}: таймаут ({limit} с)")
                if run.state not in (outcome.GREEN, outcome.RED):''',
        '''                if run.state not in (outcome.GREEN, outcome.RED) \\
                        and not run.timed_out:'''))],
    47: [(OI, BASE_CHECK, '''                    if side == BASE and case is not None \\
                            and case.outcome == outcome.SKIPPED:
                        raise _Prepare(f"{where}: у теста {cid} {describe(case)}"
                                       f" — исход базы не судим")
''')],
    48: [(OI, GREEN, "                    green = case is None or in_pass_to_pass(case)\n")],
    49: [(OI, GREEN, "                    if case is not None and case.outcome == outcome.SKIPPED:\n"
                     "                        raise _Prepare(f\"{where}: у теста {cid} пропуск\")\n"
                     + GREEN)],
    50: [(OI, GREEN, "                    if case is None:\n"
                     "                        raise _Prepare(f\"{where}: у теста {cid} нет записи\")\n"
                     + GREEN)],
    51: [(OI, GREEN, "                    green = case is not None and (\n"
                     "                        case.outcome == outcome.ERROR or in_pass_to_pass(case))\n")],
    52: [(OI, '''    flaky_lines = [f"{FLAKY_ON_BASE}: {cid}" for cid in flaky]
''', '''    flaky_lines = []
''')],
    53: [(OI, "        elif h.mode == _TODO_MODE and b.mode != _TODO_MODE:\n",
          "        elif h.mode == _TODO_MODE:\n")],
    54: [(OI, "        elif h.fails and not b.fails:\n",
          "        elif h.fails:\n")],
    55: [(OI, '''    for cid, h in head_map.items():
        if cid in base_map:
            continue
''', '''    for cid, h in ():
        if cid in base_map:
            continue
''')],
    56: [(OI, '''        elif h.fails and not b.fails:
            found.append(Finding(FAILS_APPEARED, cid, runs))
''', '''        elif h.fails and not b.fails:
            found.append(Finding(FAILS_APPEARED, cid, runs))
        if h is not None and h.mode == _TODO_MODE and b.mode != _TODO_MODE \\
                and h.outcome == outcome.SKIPPED and b.outcome != outcome.SKIPPED:
            found.append(Finding(BECAME_SKIPPED, cid, runs))
''')],
    57: [(OI, '''        growth = skip_growth(base, head)
        if growth:
            lines.append(growth)
''', '''        if skip_growth(base, head):
            lines += [f"пропуск: {c.id}" for c in head
                      if c.outcome == outcome.SKIPPED]
''')],
    58: [(OI, '''        if h is None:
            found.append(Finding(GONE, cid, runs))
        elif h.mode''', '''        if h is None:
            pass
        elif h.mode''')],
    59: [(OI, "    findings = senior + [f for f in compare(base, head) if f.id not in taken]\n",
          "    findings = [f for f in compare(base, head) if f.id not in taken] + senior\n"),
         (OI, '''    findings = ordered(findings + replaced_found
                       + _strict_findings(profile, files, entries)
                       + _code_exception_findings(files, entries, added))''',
          '''    findings = (findings + replaced_found
                + _strict_findings(profile, files, entries)
                + _code_exception_findings(files, entries, added))''')],
    60: [(OI, "    return sorted(findings, key=lambda f: (_RANK.get(f.kind, _OTHER_RANK), f.id))\n",
          "    return sorted(findings, key=lambda f: _RANK.get(f.kind, _OTHER_RANK))\n")],
    61: [(OI, '''        return GateRefusal(action, "\\n".join(lines + flaky_lines),''',
          '''        return GateRefusal(action, "; ".join(lines + flaky_lines),''')],
    62: [(OI, '''    store.journal(conn, task_id, "fsm", PASSED_ACTION, "\\n".join(
        [counts, proof,''', '''    (lambda *args: None)(conn, task_id, "fsm", PASSED_ACTION, "\\n".join(
        [counts, proof,''')],
    63: [(OI, "                run = acceptance.report_run(profile, trees[side], [path], limit)\n"
              "                count += 1\n",
          "                run = acceptance.report_run(profile, trees[side], [path], limit)\n")],
}


def build(number: int) -> str:
    edits = PATCHES[number]
    by_path: dict = {}
    for path, old, new in edits:
        by_path.setdefault(path, []).append((old, new))
    out = []
    for path, pairs in by_path.items():
        text = (WT / path).read_text(encoding="utf-8")
        new_text = text
        for old, new in pairs:
            count = new_text.count(old)
            if count != 1:
                sys.exit(f"мутация {number}: фрагмент в {path} встречается {count} раз")
            new_text = new_text.replace(old, new)
        compile(new_text, path, "exec")
        diff = difflib.unified_diff(text.splitlines(keepends=True),
                                    new_text.splitlines(keepends=True),
                                    f"a/{path}", f"b/{path}", n=3)
        out.append(f"diff --git a/{path} b/{path}\n" + "".join(diff))
    return "".join(out)


def main():
    for raw in sys.argv[1].split(","):
        number = int(raw)
        text = build(number)
        name = D / f"mutation-{number:03d}.diff"
        name.write_text(text, encoding="utf-8")
        res = subprocess.run(["git", "-C", str(WT), "apply", "--check", str(name)],
                             capture_output=True, text=True)
        print(name.name, "ok" if res.returncode == 0 else res.stderr.strip())


main()
