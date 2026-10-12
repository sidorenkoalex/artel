---
task: 01M4RRW7FT1EE77EY9Y462AZKC
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Проект задачи — флаг new --target, однозначный выбор проекта и клон в target-init

# ТЗ-2: Проект задачи — флаг `new --target`, однозначный выбор проекта и клон в `target-init`

Источник: роадмап §4, главная линия, ТЗ-2 (пересчёт 10.10: «флаг
`new --target`; клон внешнего проекта командой `target-init`»); решение
Оператора 12.10.2026: минимальный путь к первой задаче на sled, ТЗ-2 —
заводить сейчас.

Факты (origin/main 8543e24e):
- `orchestrator/catalog.py::cmd_new` (~455) принимает keyword `target`,
  `None` → `config.DEFAULT_TARGET` (артель, `config.py` ~58); клон проекта
  заводит `workspace.ensure_clone(target)` (~543).
- `orchestrator/artel.py`: `_NEW_USAGE` (~1368) = `new "<название>" [--tz
  <файл>] [--set <набор>]`; `_parse_new_args` (~1371) и `_cmd_new` (~1530)
  флага проекта не знают и `target` в `cmd_new` не передают. У всех 425
  задач в БД `tasks.target = artel`.
- `orchestrator/targets.py`: `target(name)` (~83) отдаёт запись
  `targets.yaml` либо `TargetsError`; `load()` (~59) — все записи.
- `orchestrator/projects.py::cmd_target_init` (~40) создаёт только каталоги
  проекта (`init_project`), клон не заводит; клон заводят `new`,
  `docs_fetch` и `doctor --fix` (`workspace.ensure_clone`, `workspace.py`
  ~94, идемпотентно).
- Строку «Проект:» в ТЗ пульт сегодня не разбирает.

Требуется:
1. `new "<название>" [--tz <файл>] [--set <набор>] [--target <имя>]`:
   значение флага передаётся в `catalog.cmd_new(target=...)`. Справка
   `_NEW_USAGE` и текст справки команды обновлены.
2. Имя проекта сверяется с `targets.yaml` в `catalog.cmd_new` в самом
   начале — до чтения ТЗ, до `workspace.ensure_clone` и до расхода id,
   ветки и строки БД: неизвестное имя — именованный отказ с перечнем объявленных
   проектов; флаг без значения — отказ, как у `--tz`.
3. Если в `targets.yaml` больше одной записи, `new` без `--target`
   отказывает именованно («укажи проект: --target <одно из …>»). Пока
   запись одна (сегодня — только artel), без флага задача уходит в неё,
   как сейчас. Правило обязательности проекта действует только в
   командной строке (`_cmd_new` / `_parse_new_args`, через
   вспомогательную функцию в `catalog.py`); `catalog.cmd_new(target=None)`
   по-прежнему означает артель и не отказывает, чтобы
   `orchestrator/canary_drive.py` (вызывает `cmd_new` без target) и
   существующие вызыватели и тесты не менялись.
4. Если в ТЗ есть строка `Проект: <имя>` (одна, в начале строки), она
   обязана совпасть с проектом задачи (из флага или из правила п. 3);
   несовпадение — отказ до создания задачи. Строки нет — проверка не
   делается. Две и более строки — отказ. Для канарейки (`canary=True`)
   строка «Проект:» не разбирается, как и «Порядок:». Порядок: проект
   из флага или правила п. 3 → сверка с `targets.yaml` → сверка со
   строкой «Проект:» → только затем `ensure_clone`; все отказы пп. 2–4
   происходят до `ensure_clone`, клон на диске после отказа не
   появляется.
5. Проект задачи печатается в выводе `new` и пишется в журнал записи о
   заведении задачи.
6. `target-init <имя>` после каталогов заводит клон проекта тем же
   `workspace.ensure_clone` (идемпотентно); неудача клона — именованный
   отказ с причиной, каталоги остаются. Имя сверяется с `targets.yaml`
   до создания каталогов. Существующие тесты, вызывающие `target-init`
   для проекта без заранее заведённого клона (`tests/test_doctor.py`,
   `tests/test_git_fixation.py`), переставляются: клон проекта
   (`make_project_repo`) создаётся до `target-init`; проверки не
   меняются, устаревший комментарий о том, что `target-init` клон не
   заводит, правится. Раздел SPEC «Меняемое поведение» это перечисляет.
7. Тесты в `tests/` с заявками «Ловит мутацию»: флаг не передан в
   `cmd_new`; неизвестный проект создал задачу (или потратил id/ветку);
   при двух записях `new` без флага ушёл в artel; строка «Проект:» не
   сверена или сверена после создания задачи (или после клона);
   `target-init` не завёл клон; правило п. 3 перенесено в `cmd_new` и
   сломало вызов без target (канарейка); `target-init` создал каталоги
   проекта до сверки имени с `targets.yaml`.
   Для двух записей — временный `targets.yaml` в песочнице тестов
   (настоящий `targets.yaml` не меняется). Существующие тесты не
   ослабляются; смена текста справки `_NEW_USAGE` (её проверяют
   `tests/test_new_argv_parsing.py`, `tests/test_task_model_set_units.py`)
   — разделом SPEC «Меняемое поведение».
8. `docs/codebase-map.md` обновляется в той же задаче: флаг `--target`,
   клон в `target-init`.

Матрица неослабления: задача на неизвестный или неуказанный (при
нескольких) проект не заводится вовсе — строже сегодняшнего; поведение
для единственной записи artel не меняется; клон в `target-init` — тот же
узел, что у `new`.

Зоны: orchestrator/artel.py, orchestrator/catalog.py,
orchestrator/projects.py, tests/, docs/codebase-map.md.

Только чтение (не менять): targets.yaml, orchestrator/targets.py,
orchestrator/workspace.py, orchestrator/repo_context.py, orchestrator/config.py,
orchestrator/canary_drive.py,
orchestrator/fsm.py, orchestrator/brief.py, tests/test_invariants.py,
docs/invariants.md, docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, skills/, templates/, CLAUDE.md, roles.yaml,
.github/.

Не входит: запись sled в `targets.yaml` (Оператор, doc-commit); бриф роли
для внешнего проекта и `CLAUDE.md` целевого (ТЗ-4 этап 2); профиль тестов
не на pytest пульта и песочница (ADR и B3); токен проекта (ТЗ-4 этап 1);
`doctor` для внешнего проекта (ТЗ-5); разбор слов Оператора в чате (их
переводит в `--target` ассистентская сессия).

Рамка: $40.

Набор моделей: по умолчанию.
