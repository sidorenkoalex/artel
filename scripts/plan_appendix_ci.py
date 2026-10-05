#!/usr/bin/env python3
"""Приложения PLAN задачи на рабочем дереве раннера CI ветки задачи (SPEC
01M443HV9SJYVYQTHJSQ87QV68, требования 1-4).

`verifying` ждёт зелёного CI головы ветки задачи, а приложения PLAN к
защищённым путям накладывают только ворота мержа. Код задачи, которому
нужна совместимая правка защищённого теста, без этого сценария красил CI
ветки по построению (прецедент 04.10, 01M42PENCS26D0656X8FR7DFA7). Шаг CI
перед тестами jobs `python` и `python-min` зовёт сценарий, и тесты идут на
дереве «код ветки плюс приложения её PLAN».

Запуск — без аргументов, тем же контрактом, что соседний
`scripts/ci_push_class.py`: входы — переменные окружения Actions
(`GITHUB_EVENT_NAME`, `GITHUB_REF`; на pull_request — `GITHUB_HEAD_REF`,
`GITHUB_REPOSITORY` и файл события `GITHUB_EVENT_PATH`), git зовётся из
PATH в текущем каталоге (чекаут `actions/checkout`).

- Не пуш ветки `task/**` и не pull_request из ветки `task/**` того же
  репозитория — ничего не делается, git не зовётся, код 0 (требование 2;
  SPEC 01M466ZERXQKXTR5RQCDYVDZJQ, требования 2-3). Ветка форка с именем
  `task/**` — тоже не ветка задачи.
- pull_request ветки задачи (SPEC 01M466ZERXQKXTR5RQCDYVDZJQ, требование
  1): ветка — из `GITHUB_HEAD_REF`, приложения накладываются на дерево
  чекаута как есть — merge-коммит PR с базой, то дерево, на котором их
  накладывают ворота мержа; голова ветки не перевыкладывается.
- PLAN читается из ссылки документов задачи `refs/artifacts/<id>` в
  `origin` (ADR-0021: в кодовой ветке PLAN.md нет). Ссылки нет, PLAN.md в
  ней нет, приложений в PLAN нет — код 0, дерево не тронуто.
- Приложения (`guard.plan_appendices`) накладываются `git apply` подряд, в
  порядке PLAN — тем же порядком, что ворота мержа. Неприменимое
  приложение — код 1 и его номер и пути в выводе (требование 3).
- Сценарий ничего не коммитит и не пушит, и не заводит ссылок: ссылка
  документов подтягивается в объектную базу без имени назначения, правка
  остаётся только в рабочем дереве раннера (требование 4).

Сбой git на чтении `origin` — код 1, а не «приложений нет»: молча зелёный
CI при недоступном PLAN пропустил бы ровно тот случай, ради которого
сценарий написан (fail-closed, ADR-0002).

Режим `--check-workflow [путь]` — сторож самого шага (требование 7): в
jobs `python` и `python-min` файла `.github/workflows/ci.yml` шаг
сценария стоит перед прогоном pytest, и его условие `if:` не допускает
одно событие push (SPEC 01M466ZERXQKXTR5RQCDYVDZJQ, требование 5). Его
зовёт job `guard` того же файла.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Файл живёт двумя жизнями — скрипт и модуль (`from scripts import
# plan_appendix_ci` в тестах), тем же приёмом, что `scripts/guard.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import guard  # noqa: E402

TASK_BRANCH_PREFIX = "refs/heads/task/"
PROCESSED_EVENTS = ("push", "pull_request")
# Пространство ссылок документов задачи — `artifact_branch.branch_name`;
# модуль пульта сюда не тянется: сценарию нужен только префикс.
DOCS_REF_PREFIX = "refs/artifacts/"
WORKFLOW_REL = ".github/workflows/ci.yml"
SCRIPT_REL = "scripts/plan_appendix_ci.py"
WORKFLOW_JOBS = ("python", "python-min")


class CiError(Exception):
    """Сбой, после которого судить о приложениях нельзя: код 1."""


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def _git_or_fail(what: str, *args: str) -> str:
    res = _git(*args)
    if res.returncode != 0:
        answer = (res.stderr or res.stdout).strip()[:300]
        raise CiError(f"{what}: git {' '.join(args)} — "
                      f"{answer or f'код {res.returncode}'}")
    return res.stdout


def task_branch(event_name: str, ref: str) -> str | None:
    """Имя ветки задачи без `task/` для прогона ветки `task/**`; иначе None
    — прогоны `main`, прочих веток и прочих событий сценарий не трогает.

    `ref` — ссылка проверяемой ветки: на push это `GITHUB_REF`, на
    pull_request — `refs/heads/<GITHUB_HEAD_REF>` головы PR того же
    репозитория (`tested_ref`); сам `GITHUB_REF` pull_request
    (`refs/pull/<N>/merge`) ветки не называет."""
    if event_name not in PROCESSED_EVENTS:
        return None
    if not ref.startswith(TASK_BRANCH_PREFIX) or ref == TASK_BRANCH_PREFIX:
        return None
    return ref[len(TASK_BRANCH_PREFIX):]


def _head_repo(event_path: str) -> str:
    """`pull_request.head.repo.full_name` файла события Actions."""
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        name = event["pull_request"]["head"]["repo"]["full_name"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CiError(f"репозиторий головы PR не прочитан из файла события "
                      f"{event_path or '(GITHUB_EVENT_PATH пуст)'}: "
                      f"{exc!r}") from exc
    if not isinstance(name, str) or not name:
        raise CiError(f"в файле события {event_path} нет "
                      f"pull_request.head.repo.full_name")
    return name


def tested_ref(env) -> str:
    """Ссылка проверяемой ветки для `task_branch`; пустая строка — ветки
    задачи того же репозитория у прогона нет.

    pull_request: голова — `GITHUB_HEAD_REF`; ветка форка (репозиторий
    головы в файле события не `GITHUB_REPOSITORY`) — не ветка задачи, даже
    с именем `task/**`: её PLAN не наш. Файл события читается только для
    головы `task/**` — прочие ветки решаются без него. Не прочитан —
    код 1 (`CiError`): гадать «форк или нет» значило бы молча пропустить
    приложения либо наложить чужие. Git здесь не зовётся."""
    event_name = env.get("GITHUB_EVENT_NAME", "")
    if event_name != "pull_request":
        return env.get("GITHUB_REF", "")
    head = env.get("GITHUB_HEAD_REF", "")
    if task_branch(event_name, f"refs/heads/{head}") is None:
        return ""
    if _head_repo(env.get("GITHUB_EVENT_PATH", "")) != env.get(
            "GITHUB_REPOSITORY", ""):
        print(f"pull_request из форка (ветка {head}) — приложения PLAN не "
              f"накладываются")
        return ""
    return f"refs/heads/{head}"


def docs_ref_for_branch(branch_rest: str,
                        refs: dict[str, str]) -> tuple[str, str] | None:
    """(id задачи, sha) ссылки документов, которой принадлежит ветка
    `task/<branch_rest>`; None — такой ссылки нет.

    Имя ветки несёт id в нижнем регистре и слаг через дефис, ссылка — id в
    исходном регистре. Формат id здесь не разбирается (линт
    `id-format-greplint`, SPEC T094): ветке принадлежит ссылка, чей id в
    нижнем регистре — ровно начало имени ветки до дефиса слага. Из
    нескольких подходящих — самый длинный id."""
    owned = [(task_id, sha) for task_id, sha in refs.items()
             if branch_rest == task_id.lower()
             or branch_rest.startswith(task_id.lower() + "-")]
    if not owned:
        return None
    return max(owned, key=lambda pair: len(pair[0]))


def remote_docs_refs() -> dict[str, str]:
    """{id задачи: sha} ссылок документов в `origin`."""
    out = _git_or_fail("ссылки документов в origin не прочитаны",
                       "ls-remote", "--refs", "origin",
                       f"{DOCS_REF_PREFIX}*")
    refs = {}
    for line in out.splitlines():
        sha, _, name = line.partition("\t")
        if name.startswith(DOCS_REF_PREFIX):
            refs[name[len(DOCS_REF_PREFIX):]] = sha
    return refs


def plan_text(task_id: str, sha: str) -> str | None:
    """PLAN.md из ссылки документов; None — PLAN.md в ней нет.

    Fetch — без имени назначения: ссылка уходит только в объектную базу
    (и FETCH_HEAD), ни одна ссылка раннера не заводится и не двигается."""
    _git_or_fail("ссылка документов задачи не подтянута", "fetch", "-q",
                 "--no-tags", "--depth=1", "origin",
                 f"{DOCS_REF_PREFIX}{task_id}")
    rel = f"tasks/{task_id}/PLAN.md"
    if _git("cat-file", "-e", f"{sha}:{rel}").returncode != 0:
        return None
    return _git_or_fail("PLAN.md не прочитан", "show", f"{sha}:{rel}")


def apply_appendix(appendix: guard.PlanAppendix) -> str:
    """`git apply` приложения в текущем дереве: пустая строка — наложено,
    иначе ответ git. Дифф — файлом, тем же способом, что
    `advance_gates.plan_appendix.git_apply` у гейта и ворот мержа."""
    with tempfile.TemporaryDirectory(prefix="artel-plan-appendix-ci-") as tmp:
        patch = Path(tmp) / "appendix.diff"
        patch.write_text(appendix.diff, encoding="utf-8")
        res = _git("apply", str(patch))
    if res.returncode == 0:
        return ""
    return ((res.stderr or res.stdout).strip()
            or f"git apply вернул {res.returncode}")[:300]


def run(event_name: str, ref: str) -> int:
    branch_rest = task_branch(event_name, ref)
    if branch_rest is None:
        print(f"не прогон ветки task/** того же репозитория ({event_name} "
              f"{ref or '-'}) — приложения PLAN не накладываются")
        return 0
    owned = docs_ref_for_branch(branch_rest, remote_docs_refs())
    if owned is None:
        print(f"ссылки документов задачи ветки task/{branch_rest} в origin "
              f"нет — приложений нет")
        return 0
    task_id, sha = owned
    text = plan_text(task_id, sha)
    if text is None:
        print(f"[{task_id}] PLAN.md в ссылке документов нет — приложений нет")
        return 0
    appendices, errors = guard.plan_appendices(text)
    if errors:
        print(f"[{task_id}] приложения PLAN не разобраны: {'; '.join(errors)}",
              file=sys.stderr)
        return 1
    if not appendices:
        print(f"[{task_id}] в PLAN нет приложений — дерево ветки как есть")
        return 0
    for number, appendix in enumerate(appendices, 1):
        paths = ", ".join(appendix.paths)
        answer = apply_appendix(appendix)
        if answer:
            print(f"[{task_id}] приложение {number} ({paths}) не "
                  f"накладывается на дерево чекаута: {answer}",
                  file=sys.stderr)
            return 1
        print(f"[{task_id}] приложение {number} наложено: {paths}")
    print(f"[{task_id}] приложений наложено: {len(appendices)} — только в "
          f"рабочем дереве раннера, без коммита")
    return 0


def _job_block(text: str, job: str) -> list[str]:
    """Строки job `job` под `jobs:` — разбор по отступам (полного YAML в
    пульте нет), тем же приёмом, что сторож CI в `tests/test_invariants.py`:
    job — ключ с отступом 2, его поля глубже."""
    out, in_jobs, inside = [], False, False
    for ln in text.splitlines():
        if ln and not ln[0].isspace():
            in_jobs = ln.split(":")[0] == "jobs"
            inside = False
            continue
        if not in_jobs:
            continue
        if ln.startswith("  ") and len(ln) > 2 and not ln[2].isspace():
            inside = ln.strip().split(":")[0] == job
            continue
        if inside:
            out.append(ln)
    return out


_PUSH_COMPARISON = re.compile(
    r"""github\.event_name\s*==\s*['"]push['"]""")


def _step_condition(block: list[str], at: int) -> str | None:
    """Значение `if:` шага, которому принадлежит строка `block[at]`; None
    — условия у шага нет. Шаг — элемент списка `- ` от его строки с
    дефисом до следующего элемента того же отступа (разбор по отступам,
    как `_job_block`); значение с продолжением на более глубоких строках
    склеивается."""
    start = next((i for i in range(at, -1, -1)
                  if block[i].lstrip().startswith("- ")), None)
    if start is None:
        return None
    dash = len(block[start]) - len(block[start].lstrip())
    end = next((i for i in range(start + 1, len(block))
                if block[i].strip()
                and len(block[i]) - len(block[i].lstrip()) <= dash),
               len(block))
    lines = block[start:end]
    for i, ln in enumerate(lines):
        body = ln.strip()
        if i == 0:
            body = body[2:].lstrip()
        if not body.startswith("if:"):
            continue
        key_col = dash + 2 if i == 0 else len(ln) - len(ln.lstrip())
        parts = [body[len("if:"):].strip()]
        for cont in lines[i + 1:]:
            if not cont.strip():
                continue
            if len(cont) - len(cont.lstrip()) <= key_col:
                break
            parts.append(cont.strip())
        return " ".join(p for p in parts if p)
    return None


def condition_push_only(condition: str) -> bool:
    """Условие шага допускает только событие push: сравнивает
    `github.event_name` с `'push'` и не упоминает `pull_request`
    (требование 5). Условие, не сравнивающее событие, — не push-only."""
    return (_PUSH_COMPARISON.search(condition) is not None
            and "pull_request" not in condition)


def workflow_errors(text: str) -> list[str]:
    """Нарушения в тексте workflow: в каждом из `WORKFLOW_JOBS` строка
    запуска сценария есть, стоит раньше первого вызова pytest, и условие
    её шага не ограничено одним push — прогоны pull_request веток
    `task/**` тоже идут с приложениями (SPEC 01M466ZERXQKXTR5RQCDYVDZJQ,
    требование 5). Пустой список — шаг на месте."""
    errors = []
    for job in WORKFLOW_JOBS:
        block = _job_block(text, job)
        if not block:
            errors.append(f"job {job} не найден")
            continue
        script = next((i for i, ln in enumerate(block)
                       if "run:" in ln and SCRIPT_REL in ln), None)
        pytest_at = next((i for i, ln in enumerate(block)
                          if "pytest" in ln and not ln.strip().startswith("#")),
                         None)
        if script is None:
            errors.append(f"job {job}: нет шага `python3 {SCRIPT_REL}`")
        elif pytest_at is not None and pytest_at < script:
            errors.append(f"job {job}: шаг {SCRIPT_REL} стоит после pytest")
        if script is not None:
            condition = _step_condition(block, script)
            if condition is not None and condition_push_only(condition):
                errors.append(f"job {job}: условие шага {SCRIPT_REL} "
                              f"пропускает только push ({condition}) — "
                              f"pull_request веток task/** идут без "
                              f"приложений PLAN")
    return errors


def check_workflow(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"{path} не прочитан: {exc}", file=sys.stderr)
        return 1
    errors = workflow_errors(text)
    for error in errors:
        print(f"::error::{path}: {error}", file=sys.stderr)
    if not errors:
        print(f"{path}: шаг приложений PLAN есть в jobs "
              f"{', '.join(WORKFLOW_JOBS)}")
    return 1 if errors else 0


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--check-workflow":
        return check_workflow(Path(argv[1] if len(argv) > 1 else WORKFLOW_REL))
    try:
        return run(os.environ.get("GITHUB_EVENT_NAME", ""),
                   tested_ref(os.environ))
    except CiError as exc:
        print(f"приложения PLAN не наложены: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
