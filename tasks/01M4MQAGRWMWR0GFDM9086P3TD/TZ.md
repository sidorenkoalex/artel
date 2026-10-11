---
task: 01M4MQAGRWMWR0GFDM9086P3TD
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Аудит SPEC: шаг spec_auditor между сдачей SPEC и spec_gate (ADR-0022)

# ТЗ: Аудит SPEC — шаг пульта spec_auditor между сдачей SPEC и spec_gate (ADR-0022 п.2–3)

Источник: ADR-0022 «Аудит на передаче» (`docs/adr/0022-handoff-audit.md`,
принят 11.10.2026, план исполнения п.2); решение Оператора 11.10.2026 —
аудит каждого SPEC, сигналы задают глубину; модель — та же, что у
аналитика, переключение набором моделей по желанию Оператора.

Факты (origin/main de280309, сверка 11.10):
- Переход `spec_writing → spec_gate`: `orchestrator/fsm_advance.py::spec_writing`
  (~86): при `SPEC.md status: ready` и чистом guard — `budget.apply_spec_budget`,
  затем `store.set_state(..., "spec_gate", ...)` (~171). Батч вопросов
  аналитика (QUESTIONS.md) — эскалация раньше статуса.
- Роли агентских состояний: `config.STATE_ROLE` (~792:
  `tests_writing → test_author`, `in_dev → developer`, `review → reviewer`;
  `spec_writing → analyst` — отдельным путём `run`); остановки `auto` —
  `config.AUTO_STOP` (~796), `spec_gate` — «гейт SPEC — решение
  Оператора» (~823).
- Прецедент шага проверки с возвратом: ревью — `REVIEW.md status:
  changes_requested` возвращает задачу разработчику, счётчик итераций,
  `advance_gates/review.py::_review_rework_gate`; бриф продолжения несёт
  замечания (`orchestrator/brief.py`).
- Роли и их скилы: `roles.yaml` (общая зона, `config.COMMON_ZONES`);
  шаблоны `templates/*.md`, скилы `skills/*.md` — защищённые пути,
  правятся только приложением PLAN (`doc-commit` скилы не принимает).
- Сигналы «подозрения на большой объём» SPEC уже считаются:
  `config.SPLIT_SIGNAL_*` (~558–583); мандаты ANSWER — `answer.py`
  («Ослабление тестов разрешено», «Расширение зон разрешено»).
- Канарейка проходит `spec_gate` автоматически (`canary: гейт SPEC
  пройден автоматически`) — новый шаг должен пройти и в её прогоне.

Требуется:
1. Каждая задача после сдачи SPEC аналитиком (`status: ready`, guard
   чист) проходит шаг аудита роли `spec_auditor` до `spec_gate`; без
   исключений по размеру задачи и проекту.
2. Роль `spec_auditor`: агент, ярус strong, модель по умолчанию — та же,
   что у аналитика; провайдер и модель задаются набором моделей, как у
   прочих ролей. Бриф аудитора: ТЗ, SPEC, все ANSWER задачи, карта кодовой
   базы, код (рабочий каталог), скил аудита; без черновиков, логов и
   переписки аналитика.
3. Артефакт `tasks/<id>/SPEC-AUDIT.md` по шаблону `templates/SPEC-AUDIT.md`,
   разделы ADR-0022 п.2: а) ТЗ ↔ SPEC в обе стороны; б) факты SPEC против
   кода; в) проверяемость каждого `AC-n` и ловимая мутация; г) зоны против
   требований (права записи, песочница, защищённые пути); д) матрица
   неослабления (форма `docs/operator-gates.md`); е) пути обхода гейтов;
   ж) вердикт `pass` | `concerns` | `fail` и перечень отклонений со
   ссылками файл:строка. guard проверяет frontmatter и разделы.
4. Глубина по сигналам (ADR-0022 п.3): непустое «Меняемое поведение»;
   мандат в ANSWER; зоны или требования касаются `tests/`, гейтов,
   лимитов, песочницы ролей, защищённых путей или приложений PLAN;
   `budget_usd` ≥ 45; ТЗ ссылается на ADR. Есть сигнал — бриф требует
   полного разбора а–ж; нет — краткого (вердикт и отклонения). Какие
   сигналы сработали — в журнале и в артефакте.
5. `fail` — возврат аналитику с аудитом в брифе продолжения (как
   `changes_requested` ревью); не более двух возвратов, третий `fail` —
   на `spec_gate` с вердиктом аудита. `concerns` и `pass` — на `spec_gate`.
   Повторный аудит после возврата смотрит новый SPEC целиком.
6. На `spec_gate` вердикт аудита виден Оператору (`show`/`status`,
   сводка гейта); `approve` на `spec_gate` при последнем вердикте `fail`
   без нового аудита требует явного флага Оператора (по образцу
   `--no-answer`), иначе отказ.
7. Команда Оператора запускает повторный аудит задачи на `spec_gate`
   (например, после правки SPEC через `reject`).
8. Канарейка проходит шаг аудита тем же кодом; её автоматический
   `spec_gate` срабатывает после аудита.
9. QUESTIONS аналитика по каждому варианту несёт матрицу последствий
   (что ломается, что ослабляется, цена, чьё решение) — шаблон
   `templates/QUESTIONS.md` и `skills/spec-authoring.md`.
10. Защищённые пути — только приложениями PLAN: запись роли в
    `roles.yaml`, `templates/SPEC-AUDIT.md`, `skills/spec-audit.md`,
    правки `templates/QUESTIONS.md` и `skills/spec-authoring.md`.
11. Ослабления нет: существующие гейты и проверки `spec_writing →
    spec_gate` (guard, батч вопросов, бюджет из SPEC) не меняются по
    смыслу; смена поведения существующих тестов — только разделом SPEC
    «Меняемое поведение» (инвариант 38).

Критерии приёмки (направление; планку пишет test_author):
- Песочница: SPEC ready → шаг `spec_auditor` → `spec_gate` при `pass`;
  без аудита задача на `spec_gate` не попадает (мутация «аудит
  пропущен» ловится).
- `fail` дважды → два возврата аналитику; третий `fail` → `spec_gate`
  с вердиктом; бриф возврата несёт отклонения аудита.
- Сигнал «Меняемое поведение» → бриф аудитора требует полного разбора;
  без сигналов — краткого; сработавшие сигналы в журнале.
- `approve` на `spec_gate` при последнем `fail` без флага — отказ, с
  флагом — проход и запись в журнале.
- guard отказывает SPEC-AUDIT.md без раздела или без вердикта.
- Бриф аудитора не содержит логов и черновиков аналитика.
- Канарейка: прогон проходит аудит и автогейт SPEC.

Зоны: orchestrator/fsm_advance.py, orchestrator/config.py, orchestrator/brief.py,
orchestrator/auto.py, orchestrator/catalog.py, orchestrator/fsm.py,
orchestrator/advance_gates/, scripts/guard.py, docs/codebase-map.md, tests/.

Приложением: roles.yaml, templates/SPEC-AUDIT.md, templates/QUESTIONS.md,
skills/spec-audit.md, skills/spec-authoring.md.

Только чтение (не менять): orchestrator/answer.py, orchestrator/runner.py,
orchestrator/providers/, orchestrator/canary.py, orchestrator/canary_drive.py,
orchestrator/store.py, orchestrator/schema.py, orchestrator/budget.py,
orchestrator/acceptance.py, orchestrator/fsm_merge_gate.py,
orchestrator/fsm_postmerge.py, orchestrator/retro.py, orchestrator/snapshot.py,
orchestrator/suite_run.py, orchestrator/suite_lock.py,
.github/workflows/ci.yml, tests/test_invariants.py, docs/invariants.md,
docs/adr/, docs/roadmap.md, docs/backlog.md, docs/operator-session.md,
docs/operator-gates.md, CLAUDE.md, models.yaml, model_sets.yaml,
targets.yaml, .artel/.

Не входит: проверка матрицы в `answer` (строка бэклога 11.10, отдельная
задача); канарейка-ловушка с дефектным SPEC (ADR-0022 п.4 плана, после
этой задачи); выбор другой модели для аудитора; аудит ТЗ и PLAN.

Рамка: $85.

Набор моделей: по умолчанию.
