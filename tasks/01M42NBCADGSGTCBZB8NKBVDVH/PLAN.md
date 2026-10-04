---
task: 01M42NBCADGSGTCBZB8NKBVDVH
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Мелкие дефекты пульта: amend-tests, гонка fetch, observe add, сверка путей SPEC в guard

## Подход
Четыре независимые точечные правки, каждая в своём модуле; поведение вне
названного места не меняется. Долгоживущие тесты задачи
(`tests/test_01m42nbcadgsgtcbzb8nkbvdvh_*.py`, 9 методов) не правились и
зелёные. Бюджет SPEC ($25) не переоценивается: дифф ~120 строк в 6 файлах.

1. **amend-tests** (`orchestrator/amend.py`): новая `_drop_fixed_task_dir`
   зовёт существующий узел `acceptance.drop_from_code_copy(task_id, wt_path)`
   (удаляет только `<wt>/tasks/<id>/`, главную копию пульта не трогает).
   Вызывается последней строкой обоих успешных путей режима рабочей копии —
   `_cmd_amend_tests` и `_amend_with_long_lived`, то есть после
   `store.update_task(tests_locked_sha=…)` и `_record_amend`. Все отказы
   (`sys.exit`) срабатывают раньше, так что правка Оператора на отказе
   остаётся на диске. Режим `--from-branch` не меняется: он выкладывает
   планку через `plank_in_code_copy`, который и так убирает её в `finally`.
2. **fetch базы** (`orchestrator/gitcmd.py`, `orchestrator/workspace.py`):
   у `fetch_ref_sha` новый keyword-only параметр `tracking_refs: bool = True`;
   при `False` перед именем remote ставится `--refmap=`. Так git
   использует только refspec из командной строки и не делает попутного
   обновления `refs/remotes/origin/<ветка>`, поэтому чужой
   `…/main.lock` fetch не блокирует. `workspace.ensure` зовёт
   `fetch_ref_sha("origin", MAIN_BRANCH, tracking_refs=False)` вместо
   `fetch_head_sha`, а текст и форма отказа «база ветки недоступна: fetch
   origin не удался: …» остаются прежними. Остальные вызовы (fsm,
   fsm_merge_gate, canary, github_adapter, doctor, artifact_branch) идут с
   дефолтом и ведут себя как раньше.
3. **observe add/remove** (`orchestrator/artel.py`): новая
   `_refuse_extra_observe_args(action, rest)` перебирает `rest[2:]`,
   пропуская `--tasks <значение>` и флаги. Любой оставшийся
   позиционный аргумент — отказ `observe <action>: лишний аргумент B —
   номера задач перечисляются через запятую одним значением: --tasks A,B`.
   Проверка стоит сразу после проверки действия, до
   `_observation_or_exit` и до любой записи в БД.
4. **guard по файлу** (`scripts/guard.py`): новая `spec_path_errors(path)`.
   Для файла с `type: spec` она зовёт тот же `spec_unclassified_paths(text, meta)`
   (корень по умолчанию — `config.ROOT` рабочей копии, как у `approve`) и
   возвращает `<путь>: unclassified_paths_refusal(...)`. В `main()` она
   подключена только в режиме явных файлов (`args != ["--all"]`), поэтому
   `check()`/`check_content()`/`--all` (CI main) не меняются. Сверка в
   `fsm._approve_spec_gate` не тронута.

## Шаги
1. Правки 1–4 выше и сторож `tests/test_gitcmd_fetch_ref_sha.py::TrackingRefsDefaultTest`
   (два метода: дефолтный вызов по-прежнему двигает ссылку отслеживания;
   `tracking_refs=False` приносит голову и объекты, убирает приватную
   ссылку и не трогает ссылку отслеживания). Регенерирована
   `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (AC-1, AC-2) | 1 — `amend._drop_fixed_task_dir`; тест `test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py` |
| 2 (AC-3, AC-4, AC-5) | 1 — `gitcmd.fetch_ref_sha(tracking_refs=False)` в `workspace.ensure`; тест `…_workspace_fetch.py` + `TrackingRefsDefaultTest` |
| 3 (AC-6, AC-7) | 1 — `artel._refuse_extra_observe_args`; тест `…_observe_extra_args.py` |
| 4 (AC-8, AC-9) | 1 — `guard.spec_path_errors` в `main()` по файлам; тест `…_guard_spec_paths.py` |
| 5 | 1 — долгоживущие тесты задачи и `TrackingRefsDefaultTest` с заявками «Ловит мутацию» |

Прогоны (в переднем плане, `-p no:cacheprovider -p timeout -o timeout=120`):
- долгоживущие тесты задачи: 9 passed (прогнаны дважды, зёрна случайные);
- `test_amend.py test_amend_long_lived.py test_amend_remove.py test_workspace.py
  test_gitcmd_fetch_ref_sha.py test_guard_path_mentions.py
  test_fsm_spec_gate_path_check.py test_observation_edges.py
  test_01m3sx69e8p64d77j1xthmhe40_observation.py
  test_artel_role_restricted_commands.py`: 131 passed, 45 subtests passed;
- `test_guard_task_root_subdirectory.py test_guard_artifact_disk_read.py
  test_guard_extraneous_acceptance_files.py
  test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py test_guard_zones.py
  test_guard_schema.py test_invariants.py test_branch_freshness_gate.py
  test_analyst_role.py`: 216 passed, 273 subtests passed;
- `test_codebase_map.py test_mutation_claim_gate.py` + долгоживущие: 56 passed;
- `artel.py plank-run 01M42NBCADGSGTCBZB8NKBVDVH`: «планки нет» — разовых
  файлов в `acceptance_tests/` нет, планка задачи целиком долгоживущая
  (прогнана выше).
- Мутации сторожа: безусловный `--refmap=` — красный
  `test_default_call_still_updates_the_tracking_ref`; fetch без приватной
  refspec при `tracking_refs=False` — красный
  `test_without_tracking_refs_objects_arrive_and_private_ref_is_removed`;
  код возвращён.

## Влияние на систему
- Гейт зон: после успешного `amend-tests` неотслеживаемого `tasks/<id>/` в
  рабочей копии больше нет, поэтому ложной находки нет. Гейт не меняется.
- `fetch_ref_sha` — общий примитив; дефолт сохраняет прежнюю argv
  (`fetch <remote> <refspec>`). Это держат существующие тесты
  (`test_gitcmd_fetch_ref_sha.py`, `test_branch_freshness_gate.py`) и новый
  сторож. Ссылка отслеживания `origin/main` теперь не обновляется при
  заведении рабочего каталога. Её по-прежнему обновляют прочие fetch пульта
  (`doctor`, `fsm._origin_main_sha` и др.), а ветка задачи берётся от sha
  приватной ссылки, не от ссылки отслеживания.
- Перехватчик сети песочницы (`tests/sandbox.py::_network_git_command_denial`)
  берёт первый аргумент без `-` — это `origin`, флаг `--refmap=` его не
  сбивает.
- guard: новая проверка только ужесточает вызов по файлу; `--all` в CI и
  `check_content` не затронуты (`test_check_content_does_not_call_the_spec_path_check`
  зелёный). `approve` на `spec_gate` не тронут.
- observe: строже только при лишнем позиционном аргументе; корректные
  вызовы не меняются.
- Тесты, гейты, лимиты не ослаблены; существующие тестовые методы не
  менялись (в `test_gitcmd_fetch_ref_sha.py` только добавлен класс).
- Откат — revert merge-коммита задачи; миграций и схемы БД нет.

## Риски
- `--refmap=` требует git ≥ 2.1 (на машине 2.50.1). Старый git отказал бы
  fetch'ем, и `ensure` вернул бы именованный отказ, а не молча завёл ветку
  от неверной базы.
- guard по явному списку файлов теперь может покраснеть на старом SPEC с
  путями вне зон, если кто-то гоняет его руками не на `--all`. Это и есть
  требование 4; CI идёт через `--all`.

## Предложения системе
- Командная оболочка шага роли не даёт `ls` и отклоняет составные команды
  (`for …; do …; done`, присваивание переменной): повторный прогон
  сторожа на нескольких случайных зёрнах пришлось делать отдельными
  вызовами. Класс уже в бэклоге (коммит 151dbf4f) — подтверждаю повтор.
