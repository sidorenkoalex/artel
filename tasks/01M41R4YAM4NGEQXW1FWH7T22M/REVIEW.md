---
task: 01M41R4YAM4NGEQXW1FWH7T22M
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Штатный локальный прогон планки в шаге роли; шаг роли не удаляет отслеживаемые файлы вне своих путей

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–5 сопоставлены шагам 1–6, AC-1…AC-9 названы с файлами, которые их держат.
- Шаги размером с MR: модуль acceptance, новая команда с диспетчером, чекпоинт, миссия, тесты, приложение к skills. Микроопераций нет.
- Подход не расходится с архитектурой. Выкладка и уборка идут через общий узел `acceptance.plank_in_code_copy`, который получил параметр `files`. Раннер общий: `_pytest_command`/`_pytest_env`. Восстановление удалений встроено в существующие точки чекпоинта. Приложение к защищённым `skills/` оформлено диффом, `git apply --check` подтверждён (см. «Проверено исполнением»).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/plank_run.py::cmd_plank_run`. Выкладка: `acceptance.plank_in_code_copy(..., files=draft)`, уборка `drop_from_code_copy` в `finally`. Прогон: `acceptance.run_plank` (`_pytest_command`, `timeout=config.ACCEPTANCE_TIMEOUT_SEC`). Печатается итог и код выхода pytest. Источник: в `tests_writing` черновик из docs_dir, иначе `ls_tree` ссылки. Аргумент `[файл]` поддерживает префикс и `::узел` |
| 2 | OK | `plank-run` добавлен в `_ROLE_ALLOWED_COMMANDS` (`artel.py:1422`). `config.ROOT` вычисляется от `__file__` (`config.py:9`), поэтому вызов `artel.py` главной копии из worktree не упирается в `_refuse_if_worktree` (`artel.py:1087`). Журнал, БД и ссылки команда не трогает. Если планки нет, отказ с текстом `NO_PLANK` происходит до выкладки |
| 3 | OK | `docs_dir_note` больше не содержит `copytree`, называет `python3 <ROOT>/orchestrator/artel.py plank-run` и запрещает ручное копирование с причиной (03.10). Пункт 5 миссии test_author согласован с этим текстом. Диф к трём файлам skills применяется |
| 4 | OK | `checkpoint.restore_out_of_bounds_deletions` пишет одну запись `RESTORED_DELETIONS_ACTION` с числом и первыми пятью путями. Для developer вызывается после `_commit_worktree_change`, только если `stray` непуст: `stray` возвращается на всех ветках после reset, в том числе «нечего коммитить» (`checkpoint.py:1567`). Для прочих ролей вызов стоит до отката вне мандата, на штатном и WIP-путях. Удаления внутри зон не трогаются (`_role_may_delete`) |
| 5 | OK | Долгоживущие `tests/test_01m41r4yam4ngeqxw1fwh7t22m_{plank_run,restore_deleted}.py` покрывают AC-9 (а)–(д), края — `tests/test_plank_run_edges.py`. Заявки «Ловит мутацию» есть у каждого метода и наблюдаемы |

Системная целостность: существующие тесты не изменены (в diff `tests/` только новый файл `test_plank_run_edges.py`). Гейты и guard не тронуты. Защищённых путей в diff нет. Секция «Влияние на систему» совпадает с diff. Откат описан.

## Замечания

Замечаний уровня blocker/major/minor нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний в этой итерации не заведено, прошлых итераций нет.

## Вердикт
approved.

Мелочи без сценария последствий (замечаниями не заводятся):
- `orchestrator/artel.py:534` — в справке модулей у строки `amend` выравнивание сместилось на один пробел.
- `orchestrator/role_prompt.py:81` — пункт 5 говорит, что `plank-run` «выполнит `python3 -m pytest tasks/<id>/acceptance_tests …`». На деле путь передаётся абсолютным (`plank_run.py`, `str(tests_dir)`), смысл не искажён.

## Проверено исполнением
- Планка из каталога документов скопирована в рабочую копию по инструкции миссии и прогнана вместе с долгоживущими тестами и краевыми тестами: `python3 -m pytest tasks/01M41R4YAM4NGEQXW1FWH7T22M/acceptance_tests tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py tests/test_plank_run_edges.py -p no:cacheprovider -p timeout -o timeout=120` — 16 passed, 34 subtests passed. AC-8 зелёный: PLAN уже в ссылке документов. После прогона удалён только `tasks/01M41R4YAM4NGEQXW1FWH7T22M/`, `git status` чист.
- Тесты затронутых модулей, последовательно, в переднем плане: test_01m3xtf5506gf43hd51ece230t_role_refusal, test_artel_role_restricted_commands, test_role_prompt_test_author_mission, test_acceptance, test_timeout_checkpoint, test_step_autocommit, test_checkpoint_zone_filter, test_checkpoint_external_step_artifacts, test_checkpoint_stray_acceptance_files, test_role_commit_by_pult, test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit, test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir, test_pause_now, test_review_package, test_test_author_long_lived_artifact, test_long_lived_step_end_to_end — 295 passed, 141 subtests passed (150 с). Попытка с `-n 8` упала на запуске воркеров xdist («node down»), тесты при этом не исполнялись; результат выше получен без `-n`.
- Приложение к skills вырезано из PLAN.md, проверено `git apply --check -v`: `Checking patch skills/coding-standards.md... skills/review-checklist.md... skills/test-authoring.md...`, код 0.
- Временные мутации, затем `git checkout --` и проверка чистого дерева:
  - (1) `_role_may_delete`: для test_author `return False` вместо `guard.is_long_lived_test_path`;
  - (2) `plank_run._selected`: префикс `tasks/<id>/acceptance_tests/` не снимается.
  
  `tests/test_plank_run_edges.py` — 2 failed (`test_test_author_own_long_lived_deletion_left_to_its_mandate`, `test_file_arg_accepts_task_prefix_and_node`), 4 passed: заявки этих тестов подтверждены.
- Прочитано точечно: `artel.py:1087-1111` (`_refuse_if_worktree`) и `config.py:9`, чтобы проверить доступность команды из worktree роли; `checkpoint.py:1410-1427, 1540-1575`, чтобы проверить, что `stray` возвращается на всех ветках.

## Предложения системе
- Миссия шага ревью этой задачи всё ещё велит `copytree` планки: до мержа новая команда в главной копии недоступна. Задачи, которые меняют миссию, проходят собственный круг по старой инструкции — стоит учитывать при разборе инцидентов уборки до мержа.
