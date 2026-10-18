---
task: 01M56GWRJ5NVSR39VNT6QQC7NV
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/checkpoint.py, tests/
budget_usd: 25
---

# SPEC: Чекпоинт developer коммитит свои долгоживущие файлы внешнего проекта

## Контекст
После мержа 01M55VGDHXQ55YR2YXXBPAHTNB гейт зон (`orchestrator/advance_gates/zones.py`, расширение по `project_profile.decide(target)` → `Profile.is_long_lived(task_id, path)`) признаёт зоной новый файл задачи `test_<id>_*.py` в `long_lived_dir` профиля внешнего проекта, добавленный developer. Но WIP-чекпоинт developer (`orchestrator/checkpoint.py`, ветка `role == "developer"` → `_commit_worktree_change`) снимает со стейджа пути вне `_zone_paths` (заявленные зоны + `config.COMMON_ZONES` + `tasks/<id>/`); у внешнего проекта `COMMON_ZONES` артели к `backend/tests/test_<id>_x.py` не относятся — пульт такой файл не коммитит, а чекпоинт подтяжки (`commit_pull_checkpoint`, тот же узел `_commit_worktree_change` с `refuse_on_stray=True`) отказывает подтяжке целиком. Разработчик вынужден коммитить файл сам. Чекпоинт test_author после 01M551W0TFCT2XRQ71XFXJDKB9 уже признаёт свои файлы по профилю (`own_zones`).

## Требования
1. У задачи внешнего проекта зоны WIP-чекпоинта developer включают собственные долгоживущие файлы задачи — пути, для которых `Profile.is_long_lived(task_id, path)` истинно, — тем же источником профиля, что гейт зон после 01M55VGDHXQ55YR2YXXBPAHTNB. Чекпоинт подтяжки main (`commit_pull_checkpoint`) идёт тем же узлом `_commit_worktree_change` и получает то же расширение.
2. Прочие пути `long_lived_dir` профиля (не проходящие `is_long_lived` для этой задачи) в зону чекпоинта не входят.
3. `config.COMMON_ZONES` не меняется.
4. Отказ определения профиля (профиля нет / профиль не определён) — зоны чекпоинта не расширяются, поведение сегодняшнее.
5. У задачи артели исходы чекпоинта developer и чекпоинта подтяжки не меняются; это фиксируется тестами до правки.
6. Тесты детерминированы, без сети: учебный внешний проект, задача с зонами `backend/src/`.

## Критерии приёмки
AC-1. Внешний проект с профилем, задача с зонами `backend/src/`: незакоммиченный developer-ом новый файл `backend/tests/test_<id>_x.py` (id этой задачи) коммитится WIP-чекпоинтом developer — файл присутствует в коммите пульта, рабочее дерево по нему чисто.
AC-2. В той же постановке незакоммиченный `backend/tests/test_other.py` (не долгоживущий файл этой задачи) снимается со стейджа и не попадает в коммит пульта, а запись журнала `STRAY_WORKTREE_FILES_ACTION` называет его; при этом свой `backend/tests/test_<id>_x.py` в том же шаге коммитится.
AC-3. Чекпоинт подтяжки main внешнего проекта (`commit_pull_checkpoint`) с незакоммиченными `backend/src/…` и `backend/tests/test_<id>_x.py` и без иных путей вне зон коммитит оба и не пишет запись `STRAY_WORKTREE_FILES_ACTION`; с дополнительным `backend/tests/test_other.py` — отказывает целиком, как сегодня.
AC-4. Внешний проект, у которого определение профиля отказывает (профиль не определён): незакоммиченный `backend/tests/test_<id>_x.py` снимается со стейджа WIP-чекпоинтом developer, как сегодня.
AC-5. Задача артели: исходы WIP-чекпоинта developer и чекпоинта подтяжки для пути в `tests/` (из `COMMON_ZONES`) и для пути вне зон те же, что до правки; эти тесты зелёные и на коде до правки, и после.
AC-6. `config.COMMON_ZONES` в ветке задачи не изменён.

## Не входит
- Гейт зон (`orchestrator/advance_gates/zones.py`) — сделан 01M55VGDHXQ55YR2YXXBPAHTNB.
- Чекпоинт test_author — сделан 01M551W0TFCT2XRQ71XFXJDKB9.
- Правка `orchestrator/project_profile.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/config.py`, `orchestrator/repo_context.py`, `docs/backlog.md` — только чтение; потребность в правке вне зон — эскалация.
- Восстановление удалений вне зон (`restore_out_of_bounds_deletions`/`_role_may_delete` для developer) — ТЗ его не называет.

## Материалы
- ТЗ: строка бэклога 18.10 (П3), аудит SPEC 01M55VGDHXQ55YR2YXXBPAHTNB (О-1).
- `orchestrator/checkpoint.py`: ветка developer общего чекпоинта (~:229), `commit_pull_checkpoint` (~:1491), `_zone_paths` (~:1564), `_commit_worktree_change` и его параметр `own_zones` (~:1710).
- Образец источника профиля: `orchestrator/advance_gates/zones.py` (~:280-292), `project_profile.decide`/`for_task`.
