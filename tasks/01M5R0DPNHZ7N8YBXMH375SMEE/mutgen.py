"""Генератор патчей мутаций задачи 01M5R0DPNHZ7N8YBXMH375SMEE: правки
(файл, было, стало) к коду `orchestrator/` рабочей копии -> unified-диф
`mutation-<nnn>.diff` в каталоге документов; каждый проверяется
`git apply --check`. Запуск: python3 mutgen.py <корень рабочей копии>."""
import difflib
import subprocess
import sys
from pathlib import Path

OI = "orchestrator/advance_gates/outcome_integrity.py"
FMG = "orchestrator/fsm_merge_gate.py"
RC = "orchestrator/advance_gates/refusal_classes.py"
RV = "orchestrator/review.py"
TS = "orchestrator/advance_gates/two_sided.py"
AC = "orchestrator/advance_gates/acceptance.py"

JOURNAL = "        [counts, proof, *prior_line, *flaky_lines, *replaced_lines,"
PROOF = ('    proof = (f"голова {head_sha}; база {base_sha}; ключ {key}; мандат "')
KEY_CALL = "    key = (acceptance.report_suite_result_key(tree, profile, False,"
KEY_RAISE = "    if key is None:\n        raise _Prepare(f\"ключ компонента"
PROVEN_IF = "    if merge and _proven(conn, task_id, artifact_branch, head_sha, base_sha,"
PROVEN_TEXT = '                      f"для головы {head_sha[:7]} и базы {base_sha[:7]}")'
FIELDS3 = "        if fields is None or fields[:3] != (head_sha, base_sha, key):"
MB = ('        res = gitcmd.in_repo(repo, "merge-base", head_sha, main_sha)\n'
      '        base_sha = (res.stdout.strip()\n'
      '                    if res is not None and res.returncode == 0 else "")')
GATE_CALL = "    if _outcome_integrity_merge_gate(conn, task_id, state, ctx):"
GATE_THEN_LOCKS = ("    if _outcome_integrity_merge_gate(conn, task_id, state, ctx):\n"
                   "        return (\"stopped\",)\n"
                   "    if _acceptance_locks_refuse(conn, task_id):\n"
                   "        return (\"stopped\",)\n")
SYNC_THEN_GATE = ("    sync_outcome = _sync_main_or_wait(conn, task_id, t, state, branch, ctx)\n"
                  "    if sync_outcome != \"fresh\":\n"
                  "        return sync_outcome\n"
                  "    if _outcome_integrity_merge_gate(conn, task_id, state, ctx):\n"
                  "        return (\"stopped\",)\n")
REVIEW_HEAD = ("        if fields is None or fields[0] != head_sha:\n"
               "            continue\n"
               "        lines = [line for line in detail.splitlines()")
STRICT = ("        if strict and (case.outcome in (outcome.FAILED, outcome.ERROR)\n"
          "                       or (case.outcome == outcome.PASSED and case.retries)):")
PREFIX_RAISE = ('            else:\n'
                '                raise _Prepare(f"diff -M -U0 базы {base_sha[:12]} и головы "\n'
                '                               f"{head_sha[:12]}: заголовок {line[:200]!r} "\n'
                '                               f"без префикса b/")')

# номер: [(файл, было, стало)]
M = {
    # Ac1 test_ac1_passed_record_carries_head_base_key_and_mandate
    1: [(OI, JOURNAL, "        [counts, *prior_line, *flaky_lines, *replaced_lines,")],
    2: [(OI, JOURNAL, "        [proof, counts, *prior_line, *flaky_lines, *replaced_lines,")],
    3: [(OI, PROOF, '    proof = (f"голова {base_sha}; база {head_sha}; ключ {key}; мандат "')],
    4: [(OI, KEY_CALL, "    key = (acceptance.report_suite_result_key(head_sha, profile, False,")],
    5: [(OI, KEY_CALL, "    key = (acceptance.report_suite_result_key(tree, profile, True,")],
    6: [(OI, "    used = sorted(set(elements_used))\n",
          "    used = sorted(set(elements_used), reverse=True)\n")],
    7: [(OI, "    used = [element for _f, (element, _s) in covered]\n",
          "    used = [element for _f, (element, _s) in covered] + list(mandate)\n")],
    8: [(OI, '    return hashlib.sha256("\\n".join(used).encode("utf-8")).hexdigest()',
          '    return hashlib.sha256(",".join(used).encode("utf-8")).hexdigest()')],
    9: [(OI, "    if not used:\n        return MANDATE_NONE",
          "    if not used:\n        return \"\"")],
    # Ac1 key None; Ac3 «ключ None сравнивается как значение»
    10: [(OI, KEY_RAISE, "    if key is None and False:\n        raise _Prepare(f\"ключ компонента")],
    11: [(OI, KEY_RAISE, "    if key is None and False:\n        raise _Prepare(f\"ключ компонента"),
         (OI, JOURNAL, "        [counts, *([proof] if key else []), *prior_line, *flaky_lines, *replaced_lines,")],
    # Ac2 finding escalates
    12: [(FMG, GATE_CALL, "    if False and _outcome_integrity_merge_gate(conn, task_id, state, ctx):")],
    13: [(OI, '    store.journal(conn, task_id, "fsm", MERGE_REFUSAL_ACTION, refusal.detail)',
          '    store.journal(conn, task_id, "fsm", refusal.action.replace(\n'
          '        OUTCOME_REFUSAL_ACTION, MERGE_REFUSAL_ACTION), refusal.detail)')],
    14: [(OI, '    store.set_state(conn, task_id, "escalated", "fsm", expected_state=state,',
          '    store.set_state(conn, task_id, "in_dev", "fsm", expected_state=state,')],
    15: [(OI, "    if refusal is None:\n        return False\n    if refusal.action == PREPARE_REFUSAL_ACTION:",
          "    if refusal is None:\n        return False\n"
          "    if refusal.action == OUTCOME_REFUSAL_ACTION:\n        return False\n"
          "    if refusal.action == PREPARE_REFUSAL_ACTION:")],
    # Ac2 refusal class key
    16: [(RC, "    OUTCOME_MERGE_REFUSAL_ACTION: OPERATOR_FIXES,\n", "")],
    17: [(RC, "    OUTCOME_MERGE_REFUSAL_ACTION: OPERATOR_FIXES,\n",
          "    OUTCOME_MERGE_REFUSAL_ACTION: ROLE_FIXES,\n")],
    # Ac3 prepare failures
    18: [(OI, "    if refusal.action == PREPARE_REFUSAL_ACTION:\n        store.journal(",
          "    if refusal.action == PREPARE_REFUSAL_ACTION:\n        return False\n        store.journal(")],
    19: [(OI, "    except _Prepare as exc:\n        reason = str(exc)\n    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой не пропуск\n        reason = f\"сбой {exc!r}\"\n    finally:",
          "    except _Prepare as exc:\n        return None\n    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой не пропуск\n        reason = f\"сбой {exc!r}\"\n    finally:")],
    20: [(OI, "        main_sha = main_sha_of()\n        if not main_sha:",
          "        main_sha = main_sha_of()\n        if not main_sha:\n"
          "            main_sha = gitcmd.diff_base(_branch, repo=repo)\n        if not main_sha:")],
    # Ac4 proof
    21: [(OI, PROVEN_IF, "    if False and merge and _proven(conn, task_id, artifact_branch, head_sha, base_sha,")],
    22: [(OI, "        used = [element for element, _source in pairs]",
          "        used = [source for _element, source in pairs]")],
    23: [(OI, PROVEN_TEXT, '                      f"для головы {head_sha} и базы {base_sha[:7]}")')],
    24: [(OI, PROVEN_TEXT, '                      f"для головы {head_sha[:7]}")')],
    # Ac5 mismatch
    25: [(OI, FIELDS3, "        if fields is None or fields[:1] != (head_sha,):")],
    26: [(OI, FIELDS3, "        if fields is None or fields[:2] != (head_sha, base_sha):")],
    27: [(OI, "        if fingerprint(used + _replacement_elements(replacements)) == \\\n                fields[3]:\n            return True",
          "        if True:\n            return True")],
    # Ac6 legacy
    28: [(OI, FIELDS3 + "\n            continue",
          "        if fields is None:\n            return True\n"
          "        if fields[:3] != (head_sha, base_sha, key):\n            continue")],
    # Ac7 merge base
    29: [(OI, MB, "        res = None\n        base_sha = gitcmd.diff_base(_branch, repo=repo) or \"\"")],
    30: [(OI, MB, "        res = None\n        base_sha = main_sha")],
    31: [(OI, "        if not base_sha:\n            raise _Prepare(f\"merge-base головы",
          "        if not base_sha or base_sha != main_sha:\n            raise _Prepare(f\"merge-base головы")],
    32: [(FMG, GATE_THEN_LOCKS,
          "    if _acceptance_locks_refuse(conn, task_id):\n"
          "        return (\"stopped\",)\n"
          "    if _outcome_integrity_merge_gate(conn, task_id, state, ctx):\n"
          "        return (\"stopped\",)\n")],
    33: [(FMG, SYNC_THEN_GATE,
          "    if _outcome_integrity_merge_gate(conn, task_id, state, ctx):\n"
          "        return (\"stopped\",)\n"
          "    sync_outcome = _sync_main_or_wait(conn, task_id, t, state, branch, ctx)\n"
          "    if sync_outcome != \"fresh\":\n"
          "        return sync_outcome\n")],
    34: [(OI, "        t = store.get_task(conn, task_id)\n        if t[\"is_canary\"]:\n            return False\n        artifact_branch, _foreign = artifact_source.resolve(conn, task_id)\n        refusal = _gate(",
          "        t = store.get_task(conn, task_id)\n        artifact_branch, _foreign = artifact_source.resolve(conn, task_id)\n        refusal = _gate(")],
    35: [(OI, "    base_sha = gitcmd.diff_base(branch, repo=repo)\n",
          "    base_sha = _head_sha\n")],
    36: [(OI, "    base_sha = gitcmd.diff_base(branch, repo=repo)\n",
          "    res = gitcmd.in_repo(repo, \"rev-parse\", f\"refs/remotes/origin/{config.MAIN_BRANCH}\")\n"
          "    base_sha = res.stdout.strip() if res is not None and res.returncode == 0 else \"\"\n")],
    # Ac8 review lines
    37: [(RV, "    if not outcome_integrity.in_outcome_bounds(profile) and \\",
          "    if True or not outcome_integrity.in_outcome_bounds(profile) and \\")],
    38: [(OI, REVIEW_HEAD, REVIEW_HEAD.replace("fields[0] != head_sha", "fields[1] != head_sha"))],
    39: [(OI, "                *(f\"гейт исходов: {line}\" for line in lines[1:])]\n    return [NOT_RUN_LINE",
          "                *(f\"гейт исходов: {line.partition(COVERED_MARK)[0]}\" for line in lines[1:])]\n    return [NOT_RUN_LINE")],
    # Ac9 not run
    40: [(OI, REVIEW_HEAD, REVIEW_HEAD.replace("fields is None or fields[0] != head_sha", "fields is None"))],
    41: [(OI, "    return [NOT_RUN_LINE.format(head=head_sha[:7] or \"(не прочитана)\")]\n\n\ndef _record_lines",
          "    return []\n\n\ndef _record_lines")],
    42: [(RV, "    return (outcome_integrity.review_lines(conn, task_id, head)\n",
          "    shown = outcome_integrity.review_lines(conn, task_id, head)\n"
          "    if any(\"не исполнялся\" in line for line in shown):\n"
          "        return None\n"
          "    return (outcome_integrity.review_lines(conn, task_id, head)\n")],
    # Ac10 section
    43: [(RV, "    if not lines and not unobserved and outcome_lines is None:",
          "    if not lines and not unobserved:")],
    44: [(RV, "    if not store.task_exists(conn, task_id) \\\n            or store.get_task(conn, task_id)[\"is_canary\"]:",
          "    if not store.task_exists(conn, task_id):")],
    # Ac11, Ac12 two-sided
    45: [(TS, STRICT, STRICT.replace("if strict and", "if False and"))],
    46: [(TS, "            kind = _check_failure_kind(case, profile)",
          "            kind = \"не проверка\"")],
    47: [(TS, STRICT, "        if strict and (case.outcome in (outcome.FAILED, outcome.ERROR)):")],
    # Ac13 retried base rerun
    48: [(OI, "                    green = case is not None and in_pass_to_pass(case)",
          "                    green = case is not None and (\n"
          "                        case.outcome == outcome.PASSED if side == BASE\n"
          "                        else in_pass_to_pass(case))")],
    # Ac14 out of bounds
    49: [(AC, "    return (profile is not None and project_profile.reported(profile)\n"
              "            and bool(getattr(profile, \"from_components\", False)))",
          "    return (profile is not None and project_profile.reported(profile))")],
}

D = {
    50: [(OI, "        else:\n            m = _HUNK_RE.match(line)",
          "        elif line.startswith(\"\\\\\") and path is not None:\n"
          "            added.setdefault(path, []).append((number, line[1:]))\n"
          "        else:\n            m = _HUNK_RE.match(line)")],
    51: [(OI, '            "--src-prefix=a/", "--dst-prefix=b/", "-M", "-U0",',
          '            "-M", "-U0",'),
         (OI, PREFIX_RAISE, "            else:\n                path = None")],
    52: [(OI, PREFIX_RAISE, "            else:\n                path = None")],
    53: [(OI, '            if target == "/dev/null":\n                path = None',
          '            if target == "/dev/null":\n                path = None\n'
          '                added.setdefault(target, [])')],
    54: [(OI, "    origin = {(new or path): status for status, path, new in entries}\n",
          "    origin = {(new or path): status for status, path, new in entries}\n"
          "    old_of = {(new or path): path for status, path, new in entries}\n"),
         (OI, "        if files.is_test(path) or files.is_support(path):\n            continue\n        # Путь головы",
          "        if any(files.is_test(p) or files.is_support(p)\n"
          "               for p in (path, old_of.get(path, path))):\n"
          "            continue\n        # Путь головы")],
    55: [(OI, '        if (not files.profile.tests and status.startswith(("A", "R", "C"))',
          '        if (not files.profile.tests and status.startswith(("A", "C"))')],
}


def build(root: Path, edits: list) -> str:
    texts = {}
    for rel, old, new in edits:
        text = texts.get(rel)
        if text is None:
            text = (root / rel).read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise SystemExit(f"{rel}: фрагмент встречается {text.count(old)} раз:\n{old}")
        texts[rel] = text.replace(old, new)
    out = []
    for rel, new_text in texts.items():
        old_text = (root / rel).read_text(encoding="utf-8")
        diff = difflib.unified_diff(old_text.splitlines(keepends=True),
                                    new_text.splitlines(keepends=True),
                                    f"a/{rel}", f"b/{rel}", n=3)
        out.append(f"diff --git a/{rel} b/{rel}\n" + "".join(diff))
    return "".join(out)


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    docs = Path(__file__).resolve().parent
    for number, edits in sorted({**M, **D}.items()):
        text = build(root, edits)
        path = docs / f"mutation-{number:03d}.diff"
        path.write_text(text, encoding="utf-8")
        res = subprocess.run(["git", "-C", str(root), "apply", "--check", str(path)],
                             capture_output=True, text=True)
        print(number, "ok" if res.returncode == 0 else f"FAIL {res.stderr.strip()}")


if __name__ == "__main__":
    main()
