---
task: 01M46C776SZEMYPBQGPNJN1TXY
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Полный прогон пульта на дереве ветки с приложениями PLAN

# ТЗ: полный прогон tests/ пульта на дереве «ветка плюс приложения PLAN» — приёмка и suite-run

Порядок: после 01M462QACEH29RPRD2RZHGHQFM

Источник: этап 3 ADR-0021, часть 1 (01M45FJVGQT1K0P8HDEXZX6HS7), 05.10.
Код задачи по SPEC краснеет без приложений PLAN (профиль в targets.yaml,
песочница tests/test_invariants.py). Автогейт приёмки (15:15Z) и approve на
приёмке гоняли полный набор в рабочей копии задачи без приложений — 14
инвариантов красны по построению, остальные 4357 зелёные; приёмку прошли
только через approve --accept-red (решение Оператора). Роль в шаге видела
те же 14 падений и тратила шаги на их «починку». Приложения накладывают
только CI (push и, с 01M466ZERX, pull_request веток задач) и гейт мержа.
Решение Оператора 05.10: задача приоритета 1, после suite-run, до части 2
этапа 3.

Факты (пин 7934bf2a, сверка кода 05.10):
- Полные прогоны tests/ пульта — `orchestrator/acceptance.py::full_suite`
  (~698-720) поверх `::run_full_suite`. Вызовы:
  `orchestrator/fsm_autogate.py` (~284-297, автогейт приёмки, каталог —
  `workspace.path(task_id)` на ветке задачи), `orchestrator/fsm.py::
  _acceptance_full_suite_ok` (~1096-1124, approve в acceptance, тот же
  каталог, флаг `--accept-red`), `orchestrator/fsm_merge_gate.py`
  (~868-881, после наложения приложений на scratch-дерево мержа, только
  если приложения трогают пути `_FULL_SUITE_APPENDIX_PREFIXES` ~737-739),
  `orchestrator/notes.py` (~1010, не прогон задачи).
- Наложение приложений на гейте мержа — `fsm_merge_gate.py::
  _apply_plan_appendices` (~883-), разбор — `scripts/guard.py::
  plan_appendices` (~364), `git apply` — `orchestrator/advance_gates/
  plan_appendix.py::git_apply` (~73). Источник PLAN — ссылка документов
  задачи. Наложение — только для артели (`repo_context.is_artel`).
- Команда `suite-run` (01M462QACEH29RPRD2RZHGHQFM, мерж до этой задачи)
  гоняет полный набор в рабочей копии задачи тем же узлом `full_suite`;
  базу сравнения — по sha базы.
- CI: `scripts/plan_appendix_ci.py` накладывает приложения PLAN на дерево
  чекаута на push и pull_request веток задач.

Требуется:
1. Автогейт приёмки, approve в acceptance и `suite-run` (прогон ветки)
   гоняют полный набор tests/ на временном дереве: состояние рабочей
   копии задачи (для suite-run — с незакоммиченными правками; для
   приёмки — голова ветки) плюс приложения PLAN задачи, наложенные тем же
   разбором и тем же `git apply`, что на гейте мержа, в том же порядке.
   Рабочая копия задачи, её индекс, ветка и ссылки не меняются; временное
   дерево убирается на любом исходе.
2. PLAN без приложений или задача не артели — прогон идёт как сегодня, в
   рабочей копии задачи (решение SPEC: допустимо и общее временное
   дерево, если это проще и не медленнее).
3. Неприменимое приложение — прогон не идёт; отказ (автогейт — не пройден
   с причиной, approve — отказ, suite-run — отказ) называет номер и пути
   приложения. Сбой git — отказ, а не прогон без приложений (fail-closed).
4. Итог прогона (запись журнала, detail, отчёт suite-run) называет, что
   прогон шёл с приложениями PLAN и с какими путями.
5. Прогон базы `suite-run` (дерево базы задачи) приложения задачи не
   накладывает — база сравнения остаётся деревом main.
6. Тесты в `tests/` с заявками «Ловит мутацию»: тест, красный без
   приложения и зелёный с ним, на автогейте приёмки, approve и suite-run
   даёт зелёный прогон; неприменимое приложение — отказ без прогона;
   рабочая копия задачи после прогона не изменена; задача без приложений
   — прогон в прежнем месте. Существующие тесты не ослабляются.

Зоны: orchestrator/ (orchestrator/acceptance.py, orchestrator/fsm_autogate.py,
orchestrator/fsm.py, модуль suite-run, orchestrator/fsm_merge_gate.py —
только вынос общего узла наложения), tests/, docs/codebase-map.md.

Только чтение (не менять): scripts/plan_appendix_ci.py, scripts/guard.py,
conftest.py, tests/test_invariants.py, docs/invariants.md, docs/adr/,
docs/roadmap.md, docs/backlog.md, docs/operator-session.md, templates/,
skills/, CLAUDE.md, models.yaml, roles.yaml, targets.yaml,
.github/workflows/ci.yml.

Не входит: изменение порядка и условий наложения на гейте мержа; прогоны
роли напрямую pytest (вне suite-run); замок одного полного прогона на
машину (отдельная строка копилки); внешние проекты.

Рамка: $100.
