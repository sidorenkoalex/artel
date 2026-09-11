#!/usr/bin/env python3
"""Классификатор класса пуша CI (ADR-0016) — вынесен из bash-логики job
`changes` в `.github/workflows/ci.yml` (01M28NWK5X10J139Z8TD69HFAC,
требование 1): та же классификация, но как отдельный вызываемый и
тестируемый скрипт на stdlib, без сторонних пакетов.

Запускается БЕЗ аргументов командной строки (tasks/01M28NWK5X10J139Z8TD69HFAC/
acceptance_tests/test_ci_push_class.py — залоченный контракт вызова) — все
входы приходят через переменные окружения: `GITHUB_EVENT_NAME`, `GITHUB_REF`,
`GITHUB_SHA` (HEAD), `BEFORE` (родитель, тем же именем, что нёс bash в
ci.yml), плюс `GITHUB_TOKEN`/`GITHUB_REPOSITORY` для запроса `gh api` —
последние двумя нигде явно не читаются: `gh` находит их в собственном
окружении процесса сам. Список изменённых файлов скрипт считает сам через
`git diff --name-only $BEFORE $GITHUB_SHA` в ТЕКУЩЕМ каталоге (requirement 1,
"либо сам скрипт вызывает git diff --name-only") — ни один вызов `git`/`gh`
здесь не переопределяет `cwd`: рабочий каталог наследуется от процесса,
которым скрипт запущен (в CI — чекаут `actions/checkout`, в приёмочных
тестах — временный git-репозиторий).

Печатает на stdout ровно две строки: `code=true`/`code=false` (идёт ли
job `python`) и строку причины. `.github/workflows/ci.yml` забирает
первую строку в `$GITHUB_OUTPUT`, вторую — в лог задания.

Копилка 11.09 («Main красный, а CI main зелёный»): документный пуш в
main маскировал красный CI родительского коммита, потому что job
`changes` присваивал `code=false` безусловно для любого документного
диффа. Эта задача добавляет наследование итога родителя (требования
3–5): документный пуш в main получает `code=false` только если
последний завершённый прогон workflow `ci` для коммита `before` на
ветке main зелёный (`gh api .../actions/runs?head_sha=...&branch=main`).
Любое сомнение — прогона нет, заключение не `success`, ошибка запроса —
`code=true` (fail-closed, требование 4).
"""
import json
import os
import re
import subprocess
import sys

# Дословно та же классификация документного пути, что была в bash job
# `changes`: `docs/**`, `tasks/**` или `*.md` в корне (требование 2).
_DOC_PATTERN = re.compile(r"^(docs/|tasks/|[^/]+\.md$)")

_NULL_SHA = "0" * 40

_WORKFLOW_NAME = "ci"


def _is_doc_path(path: str) -> bool:
    return bool(_DOC_PATTERN.match(path))


def _diff_names(before: str, head: str) -> list | None:
    """`git diff --name-only <before> <head>` в текущем каталоге; `None` —
    дифф недоступен (нет базы, принудительный пуш, ошибка git) — тот же
    случай, что бортует классификацию в fail-closed `code=true`
    (требование 2)."""
    if not before or before == _NULL_SHA or not head:
        return None
    check = subprocess.run(["git", "cat-file", "-e", before],
                            capture_output=True)
    if check.returncode != 0:
        return None
    res = subprocess.run(["git", "diff", "--name-only", before, head],
                          capture_output=True, text=True)
    if res.returncode != 0:
        return None
    return [line for line in res.stdout.splitlines() if line]


def _parent_run_conclusion(before: str) -> tuple:
    """(conclusion строкой | None, причина) последнего завершённого прогона
    workflow `ci` для коммита `before` на ветке main (требование 3):
    `gh api repos/{owner}/{repo}/actions/runs?head_sha=<before>&branch=main`.
    `None` — прогона нет либо запрос завершился ошибкой (требование 4)."""
    try:
        res = subprocess.run(
            ["gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs"
                          f"?head_sha={before}&branch=main"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if res.returncode != 0:
        detail = (res.stderr or res.stdout).strip()[:200]
        return None, detail or f"gh завершился кодом {res.returncode}"
    try:
        payload = json.loads(res.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, f"ответ gh не разобран: {exc}"
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        return None, "в ответе gh нет списка workflow_runs"
    completed = [r for r in runs if isinstance(r, dict)
                and r.get("name") == _WORKFLOW_NAME
                and r.get("status") == "completed"]
    if not completed:
        return None, f"для родителя {before} нет завершённого прогона ci"
    return completed[0].get("conclusion"), ""


def classify(event_name: str, ref: str, before: str, head: str,
            changed_files: list | None = None) -> tuple:
    """(code: bool, reason: str) — идёт ли job `python` для этого пуша.

    `changed_files` — список путей диффа `before..head`; `None` (по
    умолчанию, вызов из CI) — скрипт сам считает дифф через `_diff_names`.
    Явный список — вход тестов (требование 1: "либо сам скрипт вызывает
    git diff --name-only").
    """
    branch = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref

    if event_name != "push":
        return True, f"событие {event_name} — тесты идут"

    if branch.startswith("artifact/"):
        return False, "артефактная ветка — код равен родителю, тесты пропущены"

    if branch != "main":
        return True, f"ветка {branch} — тесты идут"

    files = changed_files if changed_files is not None else _diff_names(before, head)
    if not files or not all(_is_doc_path(f) for f in files):
        return True, "main: код менялся — тесты идут"

    conclusion, why = _parent_run_conclusion(before)
    if conclusion == "success":
        return False, f"документный пуш, родитель {before} зелёный — тесты пропущены"
    if conclusion is not None:
        return True, f"родитель {before} красный — тесты идут"
    return True, "нет данных о родителе — тесты идут"


def main() -> int:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    ref = os.environ.get("GITHUB_REF", "")
    head = os.environ.get("GITHUB_SHA", "")
    before = os.environ.get("BEFORE", "")
    code, reason = classify(event_name, ref, before, head)
    print(f"code={'true' if code else 'false'}")
    print(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
