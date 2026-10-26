---
task: 01M5WDB7F14SQ30QVWJY2XYBG2
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 5
---

# REVIEW: GitLab Б1.1 — поля записи, ветка по шаблону, единая точка отправки с журналом и белым списком

## Фаза A: план
- Таблица покрытия полна. Шаги 9–10 описывают инкрементальный diff: `orchestrator/gitcmd.py` (`_alias_body_words`, вызов в `_push_plan`) и `tests/test_gitcmd_push_point.py` (`test_alias_body_into_whitelisted_clone_from_pult_root_refused`). Сверх плана в diff ничего нет.
- Шаг 10 и «Риски» фиксируют решение ANSWER-3: R3-F1 перенесено в Б2. Разбор тела псевдонима остаётся частичной защитой до Б2, а вычисляемый путь `$(…)` им не ловится — это названо честно.
- «Влияние на систему» соответствует diff. `_alias_body_words` вызывается только в ветке «псевдоним в argv», после `targets.load()`. У артели (`config.DEFAULT_TARGET` пропускается в `_alias_guarded_project`) и у проектов `operator` вызов прежний: `test_git_hooks.py` зелёный.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1. |
| 2 | OK | Без изменений с итерации 1. |
| 3 (а), (б) | OK | Без изменений с итерации 3. |
| 3 (в) | OK | Назначение в теле псевдонима из argv (`push <клон> main`, `!git -C <клон> …`, `!cd <клон>&&…`, через `-c` и `--config-env`) теперь отказывается. Остаток класса («произвольная команда в значении», `$(…)`) по ANSWER-3 перенесён в Б2. |
| 3 (г) | OK | Те же формы при испорченном `targets.yaml` отказываются: тест параметризован слоем `broken`. |

## Замечания

Новых замечаний нет. Наблюдение без severity: регулярное выражение `\.artel/projects/<имя>/` в `orchestrator/gitcmd.py` (`_alias_body_words`) не сверяет путь с `repo_context.projects_root()`. Поэтому псевдоним в argv, тело которого упоминает такой путь вне области проектов, получит отказ как проект с неизвестной записью. Код пульта таких вызовов не делает, а класс целиком закрывает Б2. Это не дефект этой задачи.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R3-F1 | accepted | orchestrator/gitcmd.py:285-306, 587-597 (`_alias_guarded_project`, `_push_plan`) | Для псевдонима в argv назначение в теле псевдонима не проверялось. | Отправка мимо белого списка (3 (в)) и мимо отказа при нечитаемом `targets.yaml` (3 (г)). | Accepted по решению Оператора ANSWER-3 (26.10.2026): класс «произвольная команда внутри значения псевдонима» перенесён в Б2 (хук `pre-push`, `core.hooksPath`, сверка суммы в `doctor`). Частичная защита шага 9 (`_alias_body_words`) проверена: тест красный на мутации, см. «Проверено исполнением». |

R1-F1 закрыта в итерации 2 (`accepted`), здесь не повторяется.

## Вердикт
`approved`. В реестре все записи `accepted`. R3-F1 закрыт по ANSWER-3, изменения итерации сверены и покрыты тестом с исполнимой заявкой.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_gitcmd_push_point.py tests/test_store_project_branch_tasks.py tests/test_01m5wdb7f14sq30qvwjy2xybg2_branch_template.py tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py tests/test_git_hooks.py tests/test_multitarget.py` — 175 passed, 17 subtests passed.
- Временная мутация из заявки теста: в `_alias_body_words` сразу `return words, named` (пустые списки). `pytest tests/test_gitcmd_push_point.py -k alias_body` — 12 failed (все случаи). Код возвращён через `git checkout -- orchestrator/gitcmd.py`, `git status` чист.
- `artel.py plank-run 01M5WDB7F14SQ30QVWJY2XYBG2` — 75 passed, код выхода pytest 0.
- CI коммита 2f279ea1 зелёный (16 проверок, из пакета).

## Предложения системе
- Нет.
