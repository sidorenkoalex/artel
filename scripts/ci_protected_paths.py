#!/usr/bin/env python3
"""Сверка изменённых PR файлов со списком защищённых путей БАЗЫ сравнения —
логика джоба `protected-paths` `.github/workflows/ci.yml`, вынесенная
отдельным модулем (SPEC 01M31DRD81092HB69J0MAKZMGH, требования 1-4) тем же
приёмом, каким вынесен классификатор пуша `scripts/ci_push_class.py`
(ADR-0016): stdlib, без сторонних пакетов.

Почему модуль, а не однострочник в yaml: правка `.github/` идёт приложением
к PLAN и применяется пультом на мерже, то есть текста нового джоба в ветке
задачи нет ни в один момент её жизни — логика, оставленная в yaml,
недоступна тестам ветки в принципе (SPEC, требование 2).

Почему список берётся из БАЗЫ, а не импортом `orchestrator.config` текущего
чекаута: однострочник `from orchestrator import config` читал список из кода
ВЕТКИ, и ветка, которая создаёт файл и тем же изменением вносит его в
`PROTECTED_PATHS`, красила собственный PR — путь было не провести ни веткой,
ни приложением к PLAN (гейт приложений сверяется со списком главной копии,
где пути ещё нет). Список базы этой подмене не подвержен: что защищено —
решает то состояние, ОТ которого ветка ушла.

Запускается БЕЗ аргументов командной строки в каталоге чекаута PR (тот же
контракт вызова, что у `scripts/ci_push_class.py`); база приходит переменной
окружения `BASE_SHA` — тем же именем, каким её несёт `.github/workflows/
ci.yml` сегодня. Код возврата: 0 — нарушений нет; 1 — PR трогает путь,
защищённый в базе; 2 — список базы не прочитан.

Список базы не прочитан (файла в базе нет, git не ответил, значение не
разбирается) — это код возврата 2 с названной причиной, а не пустой список
и молчаливо зелёный джоб: неизвестный статус — это «нельзя» (fail-closed,
ADR-0002).
"""
import ast
import os
import subprocess

CONFIG_REL = "orchestrator/config.py"

LIST_NAME = "PROTECTED_PATHS"

BASE_ENV = "BASE_SHA"


def is_violation(path: str, protected: list) -> bool:
    """Тот же префиксный смысл сверки, что нёс `grep -E "^($PROTECTED)"` в
    bash джоба: элемент списка — начало пути, поэтому каталог `skills/`
    ловит любой файл внутри него, а `gates.yaml` — сам файл."""
    return any(path.startswith(prefix) for prefix in protected)


def protected_paths_from_source(source: str) -> tuple:
    """(список путей | None, причина) — значение `PROTECTED_PATHS` из ТЕКСТА
    `orchestrator/config.py`.

    Разбирается модульным AST, а не импортом и не регуляркой: импорт
    исполнил бы код базы (и всё равно дал бы список текущего чекаута через
    `sys.path`), а регулярка не пережила бы перенос кортежа на вторую
    строку, в котором список записан сегодня.

    Присваивание берётся только на верхнем уровне модуля: одноимённая
    локальная переменная внутри функции списком защищённых путей не
    является. Пустое значение — причина, а не «нарушений нет»: пустой
    список означал бы снятую защиту, и принимать его молча значит зеленить
    джоб, ничего не проверив (fail-closed).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return None, f"{CONFIG_REL} базы не разбирается как Python: {exc}"
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if not any(isinstance(t, ast.Name) and t.id == LIST_NAME
                   for t in targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, SyntaxError) as exc:
            return None, (f"значение {LIST_NAME} в {CONFIG_REL} базы не "
                          f"разбирается: {exc}")
        if not isinstance(value, (tuple, list)):
            return None, (f"значение {LIST_NAME} в {CONFIG_REL} базы не "
                          f"список путей, а {type(value).__name__}")
        paths = [p for p in value if isinstance(p, str) and p]
        if len(paths) != len(value) or not paths:
            return None, (f"значение {LIST_NAME} в {CONFIG_REL} базы пусто "
                          f"либо содержит не-строки — защита снята, сверять "
                          f"нечем")
        return paths, ""
    return None, f"в {CONFIG_REL} базы нет присваивания {LIST_NAME}"


def _git(*args) -> tuple:
    """(stdout | None, причина) вызова git в ТЕКУЩЕМ каталоге — чекауте PR.

    Рабочий каталог не переопределяется (тот же приём, что в
    `scripts/ci_push_class.py`): в CI это чекаут `actions/checkout`, в
    тестах — временный репозиторий.
    """
    try:
        res = subprocess.run(["git", *args], capture_output=True, text=True,
                             timeout=120)
    except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError) as exc:
        return None, str(exc)
    if res.returncode != 0:
        detail = (res.stderr or res.stdout).strip()[:200]
        return None, detail or f"git завершился кодом {res.returncode}"
    return res.stdout, ""


def base_protected_paths(base_sha: str) -> tuple:
    """(список защищённых путей базы | None, причина) — `git show
    <base>:orchestrator/config.py` плюс разбор значения."""
    if not base_sha:
        return None, f"переменная окружения {BASE_ENV} пуста — базы нет"
    source, reason = _git("show", f"{base_sha}:{CONFIG_REL}")
    if source is None:
        return None, (f"git не отдал {CONFIG_REL} из базы {base_sha} "
                      f"({BASE_ENV}): {reason}")
    return protected_paths_from_source(source)


def changed_files(base_sha: str) -> tuple:
    """(пути диффа `<base>...HEAD` | None, причина) — тот же диапазон с
    тремя точками, каким мерил дифф bash джоба."""
    out, reason = _git("diff", "--name-only", f"{base_sha}...HEAD")
    if out is None:
        return None, (f"git не ответил на дифф {base_sha}...HEAD "
                      f"({BASE_ENV}): {reason}")
    return [line for line in out.splitlines() if line], ""


def main() -> int:
    base_sha = os.environ.get(BASE_ENV, "").strip()
    protected, reason = base_protected_paths(base_sha)
    if protected is None:
        print(f"::error::список защищённых путей базы сравнения не прочитан "
              f"— джоб красный (fail-closed, ADR-0002): {reason}")
        return 2
    changed, reason = changed_files(base_sha)
    if changed is None:
        print(f"::error::список изменённых PR файлов не собран — джоб "
              f"красный (fail-closed, ADR-0002): {reason}")
        return 2
    violations = [path for path in changed if is_violation(path, protected)]
    if not violations:
        return 0
    print(f"::error::PR меняет защищённые пути ({LIST_NAME} базы сравнения "
          f"{base_sha}) — их правит только Оператор коммитом в main:")
    for path in violations:
        print(path)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
