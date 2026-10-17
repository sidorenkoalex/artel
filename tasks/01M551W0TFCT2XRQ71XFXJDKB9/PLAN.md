---
task: 01M551W0TFCT2XRQ71XFXJDKB9
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Долгоживущие тесты по профилю проекта: задание автора тестов и чекпоинт

## Подход
Один источник — профиль проекта задачи (`project_profile.decide` по
`store.task_target`, то же, что `project_profile.for_task` гейта выхода из
`tests_writing`) — подставляется в три места пути шага test_author вместо
умолчаний артели (`guard.long_lived_path_prefix(task_id)`, буквальный
`tests`):

- `orchestrator/role_prompt.py` — `_long_lived_paths` даёт (каталог,
  префикс) или `None`; пункты 2а и 5 test_author и фраза пункта 3
  developer собираются помощниками `_long_lived_author_note`,
  `_long_lived_run_note`, `_long_lived_developer_note`. Текст артели
  побайтно прежний (подставляется `tests` и тот же префикс). Без профиля
  (refusal/skip) абзацы опускаются.
- `orchestrator/checkpoint.py` — `_test_author_checkpoint` берёт решение
  профиля: refusal — запись `TEST_AUTHOR_NOT_COMMITTED_ACTION` с причиной,
  worktree не тронут (как при молчании git); иначе профиль передаётся в
  `_test_author_own_paths` (отбор по `profile.is_long_lived`, дерево базы
  под `profile.long_lived_dir`; профиля нет — отбор пуст), текст записи о
  неотобранных называет `<long_lived_dir>/`. `_role_may_delete` получает
  профиль от `restore_out_of_bounds_deletions`. Зонный фильтр:
  `_commit_worktree_change(..., own_zones=)` — свои отобранные файлы
  добавляются к `_zone_paths` (только когда зоны заявлены);
  `config.COMMON_ZONES` не меняется.
- `orchestrator/runner.py` — только `_missing_required_artifact` (новый
  необязательный `conn`, вызов из `run_agent_once` передаёт его) и
  `_has_own_long_lived_test(cwd, task_id, profile)`: `git diff`/`ls-files`
  под `profile.long_lived_dir`, признак `profile.is_long_lived`, текст
  отказа с `profile.long_lived_prefix`. Без профиля файл не засчитывается,
  текст отказа без упоминания долгоживущего файла; при refusal — запись
  `LONG_LIVED_NOT_COUNTED_ACTION` с причиной.

`conn=None` в `role_prompt._long_lived_paths` и
`runner._missing_required_artifact` трактуется как проект артели — так их
зовут существующие тесты (`tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`
передаёт `None`, `tests/test_test_author_long_lived_artifact.py` — три
позиционных аргумента), и это тот же ответ, что `store.task_target` даёт
задаче без строки.

Бюджет SPEC ($25) не пересматривается.

## Шаги
1. Подстановка профиля в задание ролей, чекпоинт test_author и проверку
   обязательного артефакта (`role_prompt.py`, `checkpoint.py`,
   `runner.py`), регенерация `docs/codebase-map.md`. Проверка —
   долгоживущие файлы задачи
   `tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_{mission,checkpoint,required_artifact}.py`
   (18 тестов, зелёные) и тесты затронутых модулей (175 зелёных, список
   ниже), полный набор — `suite-run` №1: зелёный, 5617 прошло, 0 упало,
   2 пропущено; планка (`plank-run`) — 1 passed.

Тесты затронутых модулей, прогнанные в шаге:
`test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions`, `…_pult_commit`,
`test_01m3y8570h9y57ytp3m7e1amhg_required_artifact`,
`test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted`,
`test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit`,
`test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals`,
`test_01m4rzbdfshnessbqreh5mky9b_role_templates`,
`test_01m4rzbpg6exm74mtbptegw2d4_note_mission`,
`test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_hint`,
`test_01m484rnv3qbdy3b0m16j916zp_external_flow`,
`test_checkpoint_zone_filter`, `test_long_lived_step_end_to_end`,
`test_long_lived_transitions`, `test_role_commit_by_pult`,
`test_role_prompt_test_author_mission`, `test_timeout_checkpoint`,
`test_step_project`, `test_docs_dir_layout`,
`test_test_author_long_lived_artifact`.

Новых своих тестов в `tests/` нет: каждое требование покрывают
долгоживущие файлы задачи (AC-1..AC-7), неизменность артели — их AC-1/AC-5
и существующие тесты выше.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`role_prompt._long_lived_paths` и помощники) |
| 2 | 1 (`checkpoint._test_author_own_paths`, `_role_may_delete`, запись о неотобранных) |
| 3 | 1 (`checkpoint._commit_worktree_change(own_zones=)`) |
| 4 | 1 (`runner._missing_required_artifact`, `_has_own_long_lived_test`) |
| 5 | 1 (ветки refusal/skip во всех трёх местах) |
| 6 | 1 (текст и поведение артели прежние; AC-1/AC-5 долгоживущих файлов) |
| 7 | 1 (долгоживущие файлы задачи, учебный проект `backend/tests`) |
| 8 | — (готовый текст правки `skills/test-authoring.md` в SPEC, вносит Оператор `doc-commit`) |

## Влияние на систему
- Гейт выхода из `tests_writing`, гейт зон, гейт неослабления,
  `config.COMMON_ZONES`, `guard.py`, `project_profile.py` не меняются.
- Артель: профиль в `targets.yaml` совпадает с умолчаниями — тексты,
  отбор и коммит прежние; дополнительная зона `own_zones` у артели уже
  покрыта `tests/` из `COMMON_ZONES`.
- Новое fail-closed поведение: при отказе профиля (артель без
  `test_profile`, нечитаемый `targets.yaml`) чекпоинт test_author не
  коммитит долгоживущие файлы, а проверка артефакта их не засчитывает —
  с записью причины в журнал; раньше шли умолчания артели. Это требование
  5 SPEC; гейт выхода из `tests_writing` в этом случае и так отказывает.
- `role_prompt`/`runner`/`checkpoint` читают `targets.yaml` на каждом
  задании/чекпоинте test_author/developer — один разбор маленького файла.
- Откат — revert коммита задачи.

## Риски
- Внешний проект с `long_lived_dir` вне `zones:` получит коммит своих
  файлов чекпоинтом, но гейт зон на выходе из `in_dev` их отклонит —
  по правилу зон SPEC (требование 3) такая задача включает каталог в
  `zones:`; гейт зон — вне задачи (Ф-3 (а)).

## Предложения системе
- Шаг роли: `ls`, запись во `/tmp` heredoc'ом и составные команды Bash
  требуют подтверждения, которого в headless-шаге нет — правки пришлось
  делать только инструментом Edit (курируемый `settings.json` роли).
