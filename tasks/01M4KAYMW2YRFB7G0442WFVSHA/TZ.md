---
task: 01M4KAYMW2YRFB7G0442WFVSHA
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: ANSWER Оператора в in_dev — основание шага роли, не переход по готовым артефактам

# ТЗ: ANSWER Оператора в in_dev — основание шага роли, а не переход по готовым артефактам

Источник: строка копилки 10.10 «answer в in_dev не вызывает шаг роли»
(приоритет 2); очередь критичных 10.10, пункт 5; решение Оператора
10.10.2026 — заводить.

Случай 10.10 (01M4G8KPP8DVNBCPGCAPSVMAKZ): эскалация снята (`approve` →
in_dev 05:20:35Z), в 05:20:55Z журнал «ANSWER создан: указание Оператора»
(ANSWER-1 с причинами красного CI); `auto` в 05:26:08Z выполнил
in_dev → verifying с записью «шаг developer не нужен: переход выполнен по
готовым артефактам» — тот же код ушёл в CI, заведомо красный;
разработчик увидел бы ANSWER только после второго красного CI.

Факты (main c7cc23db, сверка 10.10):
- Указание Оператора в in_dev уже есть: `answer` в in_dev/review
  (01M443BPQE, 05.10) пишет журнал `answer.INSTRUCTION_ACTION` =
  «ANSWER создан: указание Оператора» (`orchestrator/answer.py` ~137, ~223);
  ответ с мандатами — «ANSWER создан (…)» (~320–333).
- `auto._pre_advance_step` (`orchestrator/auto.py` ~773) до шага роли
  пробует `fsm.cmd_advance` по готовым артефактам; переход состоялся —
  «шаг … не нужен» (~830), роль не запускается.
- Рубеж in_dev → verifying — `orchestrator/fsm_advance.py::in_dev` (~593),
  цепочка гейтов `_…_refuses`. Прецедент нужного гейта:
  `orchestrator/advance_gates/review.py::_review_rework_gate` (~294,
  «замечания ревью не отработаны»): нет шага developer после вердикта —
  отказ класса «чинит роль», `auto` запускает роль; критерий «шаг роли
  после входа в состояние» — общая функция
  `auto._role_step_since_state_entry`. Классы отказов —
  `orchestrator/advance_gates/refusal_classes.py`.
- Мелкие хвосты прежних строк закрыты: `answer` отказывает на ключ
  вместо файла (`artel.py::_answer_args`), `approve` из escalated без
  нового ANSWER требует `--no-answer` (01M44ENW1B).

Требуется:
1. Рубеж in_dev → verifying: ANSWER Оператора (любой: указание, мандат,
   ответ на эскалацию), записанный в журнал после последнего завершённого
   шага developer, — отказ перехода класса «чинит роль» с именем файла
   ANSWER; `auto` запускает шаг developer, бриф которого несёт этот ANSWER.
   Ручной `advance` Оператора держится тем же гейтом.
2. После шага developer, начатого позже ANSWER, гейт не мешает: переход
   идёт по обычным условиям (даже если роль кода не меняла).
3. Повторный тот же отказ после шага developer в этом визите — остановка
   `auto` по общему правилу класса, не цикл шагов.
4. ANSWER, отработанный ролью до входа в in_dev этого визита, и задачи
   без ANSWER — поведение прежнее.
5. Смена поведения существующих тестов — только разделом SPEC
   «Меняемое поведение» (инвариант 38).

Критерии приёмки (направление; планку пишет test_author):
- Случай 10.10 в песочнице: approve → in_dev, затем `answer` с указанием,
  артефакты готовы к переходу — `auto` запускает шаг developer, записи
  «шаг developer не нужен» нет; мутация «гейт не смотрит журнал ANSWER»
  ловится.
- Шаг developer начат после ANSWER — переход in_dev → verifying проходит.
- Задача без ANSWER и задача с ANSWER, отработанным до текущего входа в
  in_dev, — переход как сегодня.
- Ручной `advance` при неотработанном ANSWER — отказ с именем файла.

Зоны: orchestrator/fsm_advance.py, orchestrator/advance_gates/review.py,
orchestrator/advance_gates/refusal_classes.py, docs/codebase-map.md, tests/.

Только чтение (не менять): orchestrator/auto.py, orchestrator/answer.py,
orchestrator/brief.py, orchestrator/fsm.py, orchestrator/store.py,
orchestrator/config.py, orchestrator/runner.py, orchestrator/amend.py,
orchestrator/acceptance.py, orchestrator/notes.py, orchestrator/suite_lock.py,
orchestrator/advance_gates/tests_writing.py, scripts/,
.github/workflows/ci.yml, tests/test_invariants.py, docs/invariants.md,
docs/triggers.md, docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, templates/, skills/, CLAUDE.md, models.yaml,
roles.yaml, targets.yaml, .artel/.

Не входит: ANSWER в review (ревьювер); снятие эскалации из verifying с
известным красным CI; правка брифа (ANSWER в бриф уже попадает);
amend-tests (01M4JD36367E5CG3GXDV429XTE слита); полный прогон
(01M4K2767FXKZ8EW7AME81SZ9N).

Рамка: $30.

Набор моделей: по умолчанию.
