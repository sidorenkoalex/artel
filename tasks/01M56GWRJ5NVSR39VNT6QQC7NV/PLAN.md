---
task: 01M56GWRJ5NVSR39VNT6QQC7NV
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Чекпоинт developer коммитит свои долгоживущие файлы внешнего проекта

## Подход
Правка одного модуля `orchestrator/checkpoint.py`, тем же источником профиля,
что гейт зон: `project_profile.for_task(conn, task_id).profile.is_long_lived`.

- Новый помощник `_own_long_lived(conn, task_id, paths)` — подсписок путей вне
  зон, которые профиль признаёт своими долгоживущими файлами задачи; профиля
  нет (`skip`/`refusal`) — пусто (требование 7). Профиль читается только при
  непустом списке путей вне зон: шаг без посторонних не платит чтением
  `targets.yaml`.
- `_commit_worktree_change` получает флаг `own_long_lived` (по умолчанию
  `False`): при `True` свои долгоживущие файлы вычитаются из посторонних до
  мандата. Флаг ставят три вызова developer: ветка developer `_wip_checkpoint`
  (таймаут/авария/`pause --now`), `commit_success_checkpoint`,
  `commit_pull_checkpoint`. test_author сохраняет свой `own_zones` без
  изменений.
- `pult_commit_failed_paths` вычитает свои долгоживущие файлы из путей вне зон
  наряду с мандатом.
- `restore_out_of_bounds_deletions`/`_role_may_delete`: developer получает
  профиль и не восстанавливает удаление своего долгоживущего файла.
- `_stray_staged_paths` читает индекс с `--no-renames` (требование 5): `git mv`
  пути вне зон в путь зоны даёт удаление источника отдельной строкой — он
  посторонний, снимается со стейджа (в индексе возвращается версия HEAD), а
  последующий `restore_out_of_bounds_deletions` восстанавливает его на диске;
  в подтяжке — отказ целиком, запись называет источник. Это закрывает и
  требование 4 для переименования чужого файла в свой.

У артели долгоживущие файлы профиля (`tests/`) уже покрыты `COMMON_ZONES`, так
что расширение исходов артели не меняет (требование 8); `COMMON_ZONES` не
тронут (требование 6).

## Шаги
1. Правка `orchestrator/checkpoint.py` (выше), регенерация
   `docs/codebase-map.md`; проверка — долгоживущий файл задачи
   `tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`, планка AC-8,
   тесты затронутых модулей, полный набор `suite-run`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`own_long_lived=True` в трёх чекпоинтах developer; AC-1, AC-2, AC-3) |
| 2 | 1 (`pult_commit_failed_paths`; AC-4) |
| 3 | 1 (`_role_may_delete` developer с профилем; AC-5) |
| 4 | 1 (`is_long_lived` — полный шаблон, не каталог; `--no-renames`; AC-2, AC-3, AC-9 (а)) |
| 5 | 1 (`--no-renames` в `_stray_staged_paths`; AC-9) |
| 6 | 1 (`config.py` не тронут; AC-8) |
| 7 | 1 (`_own_long_lived` пусто без профиля; AC-6) |
| 8 | 1 (AC-7) |
| 9 | 1 (долгоживущий файл test_author — песочница git, без сети) |

## Влияние на систему
- Затронут общий фильтр посторонних путей WIP-чекпоинтов. Флаг
  `own_long_lived` только расширяет зону developer на файлы, которые гейт зон
  (`advance_gates/zones.py`) уже признаёт зоной, — коммит пульта и гейт зон
  перестают расходиться; фильтр не ослаблен: прочие пути `long_lived_dir`
  остаются посторонними.
- `--no-renames` усиливает свойство восстановления удалений вне зон (SPEC
  01M41R4YAM4NGEQXW1FWH7T22M) для всех проектов — решение Оператора 18.10
  (О-3, вариант (а)).
- Проверено: долгоживущий файл задачи 13/13 зелёный; временная мутация (снят
  `--no-renames`) — AC-9 красны (5 failed), возвращено; тесты
  `test_checkpoint_zone_filter`, `test_timeout_checkpoint`,
  `test_01m551w0…_profile_checkpoint`, `test_01m41r4…_restore_deleted`,
  `test_pull`, `test_01m4pmr5…_pull_main` — 105 passed; планка — 1 passed.
- Откат — revert одного merge-коммита.

## Риски
- Чтение профиля (`project_profile.decide`) теперь происходит в чекпоинте при
  наличии посторонних путей; исключения `targets.TargetsError` им самим
  перехвачены (`repo_context.resolve`/`profile_of`) — деградация в «без
  профиля», без падения чекпоинта.

## Предложения системе
