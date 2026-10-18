---
task: 01M56GWRJ5NVSR39VNT6QQC7NV
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Чекпоинт developer коммитит свои долгоживущие файлы внешнего проекта

## Фаза A: план
- Таблица покрытия полна (требования 1-9 → шаг 1). Один шаг на один модуль —
  размер MR, не микрооперация.
- Подход (источник профиля `project_profile.for_task(...).profile.is_long_lived`,
  тот же, что у гейта зон; флаг `own_long_lived` в `_commit_worktree_change`;
  `--no-renames` в `_stray_staged_paths`) не конфликтует с архитектурой:
  test_author сохраняет свой `own_zones`, `COMMON_ZONES` не тронут.
- «Влияние на систему» = фактический diff: `orchestrator/checkpoint.py` +
  `docs/codebase-map.md` (+ долгоживущий тест test_author). Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `own_long_lived=True` в трёх вызовах developer: `_wip_checkpoint` (checkpoint.py:232), `commit_success_checkpoint` (:902), `commit_pull_checkpoint` (:1539); вычитание своих до мандата (:1811-1813). |
| 2 | OK | `pult_commit_failed_paths` вычитает `_own_long_lived(conn, task_id, outside)` (:1735-1736). |
| 3 | OK | `_role_may_delete` developer: `or (profile is not None and profile.is_long_lived(...))` (:529-532); профиль читается для developer (:562-563). |
| 4 | OK | Фильтр — `is_long_lived` (полный шаблон), не каталог `long_lived_dir`; переименование чужого в своё — источник отдельной строкой (`--no-renames`) остаётся посторонним. AC-2, AC-3, AC-9(а) зелены. |
| 5 | OK | `_stray_staged_paths` с `--no-renames` (:1607): источник `git mv` — удалённый посторонний, `reset -- <src>` возвращает в индекс версию HEAD, последующий `restore_out_of_bounds_deletions` восстанавливает на диске; в подтяжке — отказ целиком, запись называет источник. Изменение общее для `_commit_worktree_change`, т. е. касается и чекпоинта test_author (тот же вызов с `own_zones`) — это усиление того же свойства, в рамках решения О-3 (а). |
| 6 | OK | `git diff d6d4698e...HEAD -- orchestrator/config.py` пуст; планка AC-8 зелёная. |
| 7 | OK | `_own_long_lived`: `profile is None` → `[]` (:1628-1630); `_role_may_delete` — `profile is not None`. AC-6 (skip/refusal) зелёный. |
| 8 | OK | У артели свои долгоживущие (`tests/`) уже в `COMMON_ZONES`; AC-7 зелёный. |
| 9 | OK | Песочница git, `random` с печатаемым зерном, без сети. |

## Замечания
Нет blocker/major/minor.

Сверено дополнительно (без замечаний):
- `_own_long_lived` при пустом `paths` не читает профиль — шаг без посторонних не платит чтением `targets.yaml`; `_commit_worktree_change` без зон даёт `stray=[]` → профиль не читается.
- Удаление своего отслеживаемого долгоживущего файла теперь коммитится пультом (свой путь не посторонний) — согласовано с требованием 3.
- `tests/` diff ветки — только долгоживущий файл test_author; существующие тесты не тронуты, разработчик долгоживущий не дублировал.
- `docs/codebase-map.md` свежа (регенерация даёт расхождение только в `built_at_sha` — нет даже его).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py tests/test_checkpoint_zone_filter.py tests/test_timeout_checkpoint.py tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py tests/test_pull.py tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py` — 105 passed, 54 subtests passed (116 с).
- `artel.py plank-run 01M56GWRJ5NVSR39VNT6QQC7NV` — 1 passed, код выхода 0.
- Временная мутация (возвращена `git checkout -- orchestrator/checkpoint.py`, дерево чисто): снят `own_long_lived=True` в `commit_pull_checkpoint` и профиль для developer в `restore_out_of_bounds_deletions` → `-k "ac3 or ac5"`: 3 failed (2 subtest AC-3 «без записи о посторонних», AC-5) — заявки «Ловит мутацию» подтверждены.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расхождений нет (возвращено).

## Предложения системе
- Песочный Bash шага отклоняет подстановку команд `$(…)` и не находит `ls` — удобно бы указать это в брифе ревьювера, чтобы не тратить попытки.
