# Записка developer (итерация 2)

## Выяснено
- R1-F1: `role_git._alias_refusal` теперь разбирает тело псевдонима `parse()`; `-c`/`--config-env` тела (`option_config`) проверяются — pager/fsmonitor с git, `core.worktree` → отказ, `alias.*` тела участвуют в раскрытии. На настоящем git через обёртку в дублёре `-c 'alias.cl=-c a.b=c clean -fX' cl` — отказ.
- R1-F3: `task_files.cmd_task_rm` не планирует повтор пути.
- R1-F2: сквозные тесты в `tests/test_role_git.py` (WrapperMainTest, DispatcherPathTest, TaskRmCommandTest, MissionTaskRmTest, DoctorBoundaryTest) над временным дублёром ROOT; все 7 мутаций ревью красят файл.
- Мутация «`sub == "clean"` выключен» в одиночку эквивалентна: `clean` отклоняет и `_alias_refusal`; выключение обоих мест — 4 красных.
- Статус записи реестра REVIEW.md — голое слово (`fixed`), описание — в колонке «решение», иначе guard отказывает.
- Механизм: `orchestrator/role_bin/git` (sh) → `python3 -I -S orchestrator/role_git.py`; только stdlib.

## Не сработало
- `task-rm` из главной копии пульта ещё недоступен (задача не смержена); временный файл каталога документов убран `python3 -c os.unlink`. `rm`, `cat` в Bash роли нет.

## Где остановился
- Итерация 2 сдана: планка 119 passed; test_role_git + долгоживущий + test_multitarget + test_codebase_map — 110 passed; карта регенерирована; PLAN.md status: ready, реестр R1-F1..F3 — fixed.
- `artel.py guard <id>` по-прежнему красит SPEC.md (`.artel/notes-pending/` не классифицирован) — артефакт аналитика.

## Чего не хватило
- Формы статуса записи реестра (только слово) — узнал по отказу guard.
