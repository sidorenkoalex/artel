"""Прогон выбранных тестов `tests/` в ОТДЕЛЬНОМ интерпретаторе с заданным
состоянием кэша `agent_log.environment_fingerprint` и (по желанию) с
мутацией `orchestrator/acceptance.py::run`.

Вызов: `python3 _runner.py <кэш> <мутация> <аргументы pytest…>`, где
<кэш> — `empty` (кэш пуст, как у одиночного запуска) или `prefilled`
(кэш уже заполнен, как после соседнего теста в полном `tests/`);
<мутация> — `none`, `no_timeout` (из вызова pytest в `acceptance.run`
убран `timeout=`) или `no_word` (текст отказа по таймауту в
`acceptance.run` больше не содержит «превысил»).

Мутация применяется в памяти: исходник модуля правится текстом только
внутри функции `run` и исполняется заново в пространстве имён уже
импортированного модуля — файл на диске не трогается. Код возврата —
код `pytest.main`; `MUTATION_NOT_APPLIED` — мутацию применить не
удалось (форма вызова в `acceptance.run` не узнана), чтобы проверка
мутации не прошла вхолостую.
"""
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

MUTATION_NOT_APPLIED = 97

PREFILLED = ("python=0.0.0 (/nonexistent/python), git=prefilled, "
             "claude=prefilled, заранее заполненный кэш планки")

_MUTATIONS = {
    "no_timeout": (re.compile(r",\s*timeout=config\.ACCEPTANCE_TIMEOUT_SEC\s*\)"),
                   ")"),
    "no_word": (re.compile(r"прогон превысил "), "прогон вышел за предел "),
}


def _mutate_acceptance_run(kind: str) -> bool:
    from orchestrator import acceptance
    path = Path(acceptance.__file__)
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    run_def = next((n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "run"),
                   None)
    if run_def is None:
        return False
    lines = src.splitlines(keepends=True)
    start = sum(len(l) for l in lines[:run_def.lineno - 1])
    end = sum(len(l) for l in lines[:run_def.end_lineno])
    pattern, repl = _MUTATIONS[kind]
    body, count = pattern.subn(repl, src[start:end])
    if count != 1:
        return False
    exec(compile(src[:start] + body + src[end:], str(path), "exec"),
         acceptance.__dict__)
    return True


def main(argv: list[str]) -> int:
    cache, mutation, pytest_args = argv[0], argv[1], argv[2:]
    from orchestrator import agent_log
    agent_log._environment_fingerprint_cache = (
        None if cache == "empty" else PREFILLED)
    if mutation != "none" and not _mutate_acceptance_run(mutation):
        print(f"мутация {mutation} не применилась к acceptance.run")
        return MUTATION_NOT_APPLIED
    import pytest
    # Корневой conftest.py (сторож роли) читает пути из sys.argv — под ним
    # должны стоять аргументы pytest, а не аргументы этого прогонщика.
    sys.argv = ["pytest", *pytest_args]
    return int(pytest.main(["-p", "no:cacheprovider", "-q", *pytest_args]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
