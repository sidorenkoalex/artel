---
task: 01M551W0TFCT2XRQ71XFXJDKB9
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Долгоживущие тесты по профилю проекта: задание автора тестов и чекпоинт

## Фаза A — план
- Таблица покрытия полна: требования 1–7 → шаг 1, требование 8 — текст в SPEC (doc-commit Оператора). Один шаг оправдан монолитом SPEC (одна подстановка в три места одного пути).
- Подход не трогает `COMMON_ZONES`, гейт зон, `guard.py`, `project_profile.py` — в diff ровно `checkpoint.py`, `role_prompt.py`, `runner.py` (+ карта), что совпадает с «Влиянием на систему».
- Fail-closed при refusal описан в PLAN явно как следствие требования 5.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `role_prompt._long_lived_paths` → `project_profile.decide(store.task_target(...))` — тот же источник, что `for_task`; пункты 2а/5 test_author и 3 developer собираются помощниками, каталог и префикс — из профиля. |
| 2 | OK | `_test_author_own_paths(…, profile)`: отбор `profile.is_long_lived`, база `ls_tree_files(base, profile.long_lived_dir)`; `_role_may_delete(…, profile)`; текст записи `{long_lived_dir}/`. |
| 3 | OK | `_commit_worktree_change(own_zones=sorted(own))`: только отобранные свои файлы (с префиксом, не в базе), добавляются лишь при непустых зонах; `_zone_paths` возвращает свежий список — `zones +=` не мутирует общее состояние; `COMMON_ZONES` не тронут. |
| 4 | OK | `_missing_required_artifact(conn=)`, `_has_own_long_lived_test(cwd, task_id, profile)` — `git diff`/`ls-files -- <long_lived_dir>`, текст отказа `profile.long_lived_prefix`. Остальной `runner.py` — только передача `conn=conn` в вызове и импорт (ANSWER-1). |
| 5 | OK | refusal: чекпоинт — запись `TEST_AUTHOR_NOT_COMMITTED_ACTION` с причиной, worktree не тронут; runner — `LONG_LIVED_NOT_COUNTED_ACTION` с причиной, файл не засчитан; задание без абзацев. skip: отбор пуст, файл не засчитан, абзацев нет. |
| 6 | OK | Тексты артели сверены по diff посимвольно (2а, хвост п.5 «; долгоживущие файлы tests/ — …», п.3 developer « Долгоживущие файлы задачи в tests/ (…*.py) …», отказ runner) — совпадают; держат AC-1/AC-5 долгоживущих файлов. |
| 7 | OK | Долгоживущие файлы — учебный проект `backend/tests`, без сети, случайные входы с печатаемым зерном. |
| 8 | OK | Готовый текст правки в SPEC; планка AC-8 зелёная. |

Тесты: новых/изменённых методов в `tests/` вне долгоживущих файлов задачи нет (diff `tests/` пуст), ослабления набора нет. Заявки «Ловит мутацию» долгоживущих файлов называют наблюдаемое расхождение (HEAD, диск, журнал, текст задания); заявку AC-4 проверил временной мутацией (ниже). Ветвлений под литералы фикстур нет — правило общее (`profile.*`).

Наблюдения без замечания (вкус, не дефект): разрешение проекта `conn is None → DEFAULT_TARGET` продублировано в `role_prompt._long_lived_paths` и `runner._missing_required_artifact`; запись refusal на чекпоинте пишется на каждом шаге test_author, даже без работы роли — у артели с профилем в `targets.yaml` не возникает.

## Замечания
Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 …/artel.py plank-run 01M551W0TFCT2XRQ71XFXJDKB9` — 1 passed, код выхода 0.
- `python3 -m pytest -q -p no:cacheprovider` по трём долгоживущим файлам задачи + `test_test_author_long_lived_artifact`, `test_checkpoint_zone_filter`, `test_role_prompt_test_author_mission`, `test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions`, `test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted`, `test_01m3y8570h9y57ytp3m7e1amhg_required_artifact`, `test_long_lived_step_end_to_end`, `test_role_commit_by_pult` — 52 passed, 58 subtests passed.
- Временная мутация: в `checkpoint._commit_worktree_change` строка `zones += list(own_zones)` заменена на `pass` → `profile_checkpoint.py -k ac4` красный (2 subtest failed); код возвращён `git checkout -- orchestrator/checkpoint.py`, `git status` чист.
- CI коммита b8e9fb12 зелёный (16 проверок, из пакета).

## Предложения системе
