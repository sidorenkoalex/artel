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
После мержа 01M55VGDHXQ55YR2YXXBPAHTNB гейт зон (`orchestrator/advance_gates/zones.py`, расширение по `project_profile.decide(target)` → `Profile.is_long_lived(task_id, path)`) признаёт зоной новый файл задачи `test_<id>_*.py` в `long_lived_dir` профиля внешнего проекта, добавленный developer. Но чекпоинты developer (`orchestrator/checkpoint.py`) снимают со стейджа пути вне `_zone_paths` (заявленные зоны + `config.COMMON_ZONES` + `tasks/<id>/`); у внешнего проекта `COMMON_ZONES` артели к `backend/tests/test_<id>_x.py` не относятся — пульт такой файл не коммитит, а чекпоинт подтяжки (`commit_pull_checkpoint`, `refuse_on_stray=True`) отказывает подтяжке целиком. Разработчик вынужден коммитить файл сам. Чекпоинт test_author после 01M551W0TFCT2XRQ71XFXJDKB9 уже признаёт свои файлы по профилю (`own_zones`).

Узел, который меняет задача, — зоны чекпоинта developer с профилем. По решению Оператора на гейте SPEC 18.10 (О-1..О-3) в него входят все места `checkpoint.py`, которые считают зоны developer по `_zone_paths`:
- аварийный WIP-чекпоинт (таймаут/авария/`pause --now`, ветка developer `_wip_checkpoint`, вызов `_commit_worktree_change` ~:231);
- чекпоинт штатного завершения шага `commit_success_checkpoint` (~:828-911, вызов `_commit_worktree_change` ~:895; вызывается из `runner.py` ~:1931) — основной путь, которым пульт коммитит за developer;
- чекпоинт подтяжки main `commit_pull_checkpoint` (~:1531);
- `pult_commit_failed_paths` (~:1669-1707) — иначе после отказа git на коммите свой долгоживущий файл выпадает из незакоммиченного результата шага как посторонний;
- `restore_out_of_bounds_deletions` для developer (~:532-590, `_role_may_delete`) — иначе удаление своего долгоживущего файла задачи восстанавливается из HEAD как удаление вне зон.

## Требования
1. У задачи внешнего проекта зоны чекпоинта developer включают собственные долгоживущие файлы задачи — пути, для которых `Profile.is_long_lived(task_id, path)` истинно, — тем же источником профиля, что гейт зон после 01M55VGDHXQ55YR2YXXBPAHTNB. Расширение действует в аварийном WIP-чекпоинте developer, в чекпоинте штатного завершения шага `commit_success_checkpoint` и в чекпоинте подтяжки main `commit_pull_checkpoint`.
2. `pult_commit_failed_paths` для задачи внешнего проекта считает свои долгоживущие файлы задачи по тем же зонам с профилем: после отказа git на коммите пульта незакоммиченный свой долгоживущий файл входит в возвращаемые пути, а не отбрасывается как путь вне зон.
3. `restore_out_of_bounds_deletions` для developer задачи внешнего проекта не восстанавливает удаление своего долгоживущего файла задачи (те же зоны с профилем).
4. Прочие пути `long_lived_dir` профиля (не проходящие `is_long_lived` для этой задачи) в зону чекпоинта не входят — во всех местах требований 1-3, в том числе когда developer переименовал такой файл в имя своего долгоживущего файла задачи: удаление чужого файла в коммит пульта не уходит (решение гейта SPEC 18.10, О-1).
5. `config.COMMON_ZONES` не меняется.
6. Отказ определения профиля (оба исхода `project_profile.decide` без профиля: `skip` — у проекта нет `test_profile`; `refusal` — профиль не прочитан) — зоны не расширяются ни в одном месте требований 1-3, поведение сегодняшнее.
7. У задачи артели исходы мест требований 1-3 не меняются; это фиксируется тестами до правки.
8. Тесты детерминированы, без сети: учебный внешний проект, задача с зонами `backend/src/`.

## Критерии приёмки
AC-1. Внешний проект с профилем, задача с зонами `backend/src/`: незакоммиченный developer-ом новый файл `backend/tests/test_<id>_x.py` (id этой задачи) коммитится и аварийным WIP-чекпоинтом developer, и чекпоинтом штатного завершения шага `commit_success_checkpoint` — в каждом из двух случаев файл присутствует в коммите пульта, рабочее дерево по нему чисто.
AC-2. В той же постановке незакоммиченный `backend/tests/test_other.py` (не долгоживущий файл этой задачи) снимается со стейджа и не попадает в коммит пульта, а запись журнала `STRAY_WORKTREE_FILES_ACTION` называет его; при этом свой `backend/tests/test_<id>_x.py` в том же шаге коммитится. Проверяется для обоих путей AC-1: аварийного WIP-чекпоинта developer и `commit_success_checkpoint`.
AC-3. Чекпоинт подтяжки main внешнего проекта (`commit_pull_checkpoint`) с незакоммиченными `backend/src/…` и `backend/tests/test_<id>_x.py` и без иных путей вне зон коммитит оба и не пишет запись `STRAY_WORKTREE_FILES_ACTION`; с дополнительным `backend/tests/test_other.py` — отказывает целиком, как сегодня.
AC-4. Внешний проект с профилем, задача с зонами `backend/src/`, после записи отказа git на коммите пульта (`PULT_COMMIT_GIT_FAILED_ACTION`) с незакоммиченными `backend/tests/test_<id>_x.py` и `backend/tests/test_other.py`: `pult_commit_failed_paths` возвращает `backend/tests/test_<id>_x.py` и не возвращает `backend/tests/test_other.py`.
AC-5. Внешний проект с профилем, задача с зонами `backend/src/`: отслеживаемый в HEAD `backend/tests/test_<id>_x.py`, удалённый шагом developer, `restore_out_of_bounds_deletions` не восстанавливает; удалённый отслеживаемый `backend/tests/test_other.py` — восстанавливает из HEAD.
AC-6. Внешний проект, задача с зонами `backend/src/`, при каждом из двух исходов `project_profile.decide` без профиля — `skip` (у проекта нет `test_profile`) и `refusal` (профиль не прочитан): незакоммиченный `backend/tests/test_<id>_x.py` снимается со стейджа и не попадает в коммит пульта, а незакоммиченный `tests/test_<id>_x.py` коммитится (через `config.COMMON_ZONES`, как сегодня). Проверяется для обоих путей AC-1: аварийного WIP-чекпоинта developer и `commit_success_checkpoint`.
AC-7. Задача артели: исходы чекпоинта штатного завершения шага developer и чекпоинта подтяжки для пути в `tests/` (из `COMMON_ZONES`) и для пути вне зон те же, что до правки; эти тесты зелёные и на коде до правки, и после.
AC-8. `config.COMMON_ZONES` в ветке задачи не изменён.
AC-9. Внешний проект с профилем, задача с зонами `backend/src/`: отслеживаемый в HEAD `backend/tests/test_other.py`, переименованный шагом developer в `backend/tests/test_<id>_x.py` (`git mv` без иных правок): после чекпоинта `backend/tests/test_other.py` по-прежнему есть в дереве коммита пульта (его удаление в коммит не ушло). Проверяется для обоих путей AC-1: аварийного WIP-чекпоинта developer и `commit_success_checkpoint`.

## Оценка объёма и деление
Сигналов «подозрения на большой объём» нет: зона — 2 пути (`orchestrator/checkpoint.py`, `tests/`), критериев 9 (< 10), `budget_usd` 25 (< 30). Требования 1-3 — один узел (зоны чекпоинта developer с профилем) в одном модуле; деление не требуется.

## Не входит
- Гейт зон (`orchestrator/advance_gates/zones.py`) — сделан 01M55VGDHXQ55YR2YXXBPAHTNB.
- Чекпоинт test_author — сделан 01M551W0TFCT2XRQ71XFXJDKB9.
- Правка `orchestrator/project_profile.py`, `orchestrator/advance_gates/zones.py`, `orchestrator/config.py`, `orchestrator/repo_context.py`, `docs/backlog.md` — только чтение; потребность в правке вне зон — эскалация.
- Вызов чекпоинта из `orchestrator/runner.py` — не меняется (вне зон задачи).

## Материалы
- ТЗ: строка бэклога 18.10 (П3), аудит SPEC 01M55VGDHXQ55YR2YXXBPAHTNB (О-1).
- Решения Оператора по аудиту этого SPEC 18.10 (О-1, О-2, О-3) — причина возврата из spec_gate; уточнение О-2 — ANSWER-1.md (вариант B: `tests/test_<id>_x.py` у внешнего проекта коммитится через `COMMON_ZONES`, `_zone_paths` — `checkpoint.py:1564-1583`, `COMMON_ZONES` — `config.py:803`).
- О-1: `_stray_staged_paths` (`checkpoint.py:1595`) читает `git diff --cached --name-only` без `--no-renames` — переименование даёт только имя назначения; восстановление удалений вызывается только при непустом `stray` (`:233-234`, `:897-898`).
- `orchestrator/checkpoint.py`: ветка developer `_wip_checkpoint` (~:229), `restore_out_of_bounds_deletions`/`_role_may_delete` (~:514-590), `commit_success_checkpoint` (~:828-911), `commit_pull_checkpoint` (~:1491), `_zone_paths` (~:1564), `pult_commit_failed_paths` (~:1669), `_commit_worktree_change` и его параметр `own_zones` (~:1710).
- Образец источника профиля: `orchestrator/advance_gates/zones.py` (~:280-292), `project_profile.decide`/`for_task`.
