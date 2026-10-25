# Записка developer

## Выяснено
- Список обвязки: `repo_context.wrapper_paths(ctx)` + `config.is_protected_path(path, list)`; поле записи `agent_wrapper` плоское (`targets.WRAPPER_FIELD`). Элемент `knowledge` внутри обвязки (кроме корневых CLAUDE.md/AGENTS.md) запись не загружает вовсе (`targets._check_knowledge_outside_wrapper`) — фильтр брифа на элементах реально видит только корневые два.
- Отметка без сети: `reference_cache.branch_commit(clone, base)`; «не репозиторий» — `rev-parse --show-toplevel` ≠ путь клона (песочница сама git-репозиторий).
- doctor: подмодули читают коллаборантов через фасад `doctor.<имя>`; `conventions` добавлен в импорт `doctor/__init__.py`.
- Готово: `orchestrator/conventions.py`, `brief._pult_conventions_part` + фильтр обвязки, `doctor/project_conventions.py`, команда в `artel.py`, миссии, `docs/target-onboarding.md`, правка трёх старых файлов тестов по мандату, свой `tests/test_conventions.py`, карта регенерирована. Всё зелёное; PLAN — status: ready.
- Два расхождения с буквой мандата (вид утверждения в `RepeatsAndMarksTest::test_ac6_shown_…` и `…size_skip…`) описаны в PLAN, раздел «Затрагиваемые существующие тесты — отчёт».
- pytest здесь — `-p no:xdist` (с `-n` узлы падают).

## Не сработало
- `ls`/`cat` нет; длинный heredoc в Bash — «Parser aborted»: правки больших тестов — через Edit.

## Где остановился
- Шаг завершён, сдано на ревью.

## Чего не хватило
- Что запись с `knowledge` в обвязку отказывает при загрузке (`targets.py:644`) — нашёл по падению своего теста.
