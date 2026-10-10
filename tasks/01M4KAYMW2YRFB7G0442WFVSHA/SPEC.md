---
task: 01M4KAYMW2YRFB7G0442WFVSHA
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/fsm_advance.py, orchestrator/advance_gates/review.py, orchestrator/advance_gates/refusal_classes.py, docs/codebase-map.md, tests/
budget_usd: 30
---

# SPEC: ANSWER Оператора в in_dev — основание шага developer, а не переход по готовым артефактам

## Контекст
Случай 10.10 (01M4G8KPP8DVNBCPGCAPSVMAKZ): эскалация снята `approve` →
`in_dev` (05:20:35Z), в 05:20:55Z журнал «ANSWER создан: указание
Оператора» (ANSWER-1 с причинами красного CI), а `auto` в 05:26:08Z
выполнил `in_dev → verifying` с записью «шаг developer не нужен: переход
выполнен по готовым артефактам» — заведомо красный код ушёл в CI,
разработчик увидел бы ANSWER только после второго красного CI.

Причина: `auto._pre_advance_step` (`orchestrator/auto.py` ~773) до шага
роли пробует `fsm.cmd_advance` по готовым артефактам, а рубеж
`in_dev → verifying` (`orchestrator/fsm_advance.py::in_dev`) не смотрит,
есть ли в журнале ANSWER Оператора, ещё не отработанный developer.
Записи журнала ANSWER: `answer.INSTRUCTION_ACTION` = «ANSWER создан:
указание Оператора» (`orchestrator/answer.py:137`, `:223`), ответ с
мандатами/на эскалацию — «ANSWER создан …» (`orchestrator/answer.py`
~320–333, ~385). Прецедент нужного гейта —
`orchestrator/advance_gates/review.py::_review_rework_gate` (отказ класса
«чинит роль», после которого `auto` запускает роль; критерий «шаг роли
после входа в состояние» — `auto._role_step_since_state_entry`). Классы
отказов — `orchestrator/advance_gates/refusal_classes.py`.

## Требования

1. Рубеж `in_dev → verifying`: если в журнале задачи есть запись ANSWER
   Оператора (любого вида: указание, мандат, ответ на эскалацию),
   сделанная после последнего завершённого шага developer, переход
   отклоняется отказом класса «чинит роль»; текст отказа называет имя
   файла этого ANSWER (`ANSWER-n.md`).
2. На отказ из требования 1 `auto` запускает шаг developer (а не пишет
   «шаг developer не нужен: переход выполнен по готовым артефактам»);
   бриф этого шага несёт этот ANSWER.
3. Ручной `advance` Оператора в `in_dev` держится тем же гейтом
   требования 1.
4. После шага developer, начатого позже ANSWER, гейт требования 1 не
   мешает: переход `in_dev → verifying` идёт по обычным условиям, в том
   числе если шаг developer не менял код.
5. Повтор того же отказа требования 1 после шага developer в этом визите
   `in_dev` — остановка `auto` по общему правилу класса «чинит роль»
   (тот же отказ после шага роли — стоп), а не цикл шагов developer.
6. Задача без ANSWER и задача, чей ANSWER отработан шагом developer до
   входа в `in_dev` текущего визита, проходят `in_dev → verifying` как
   сегодня.
7. Смена ожидания существующих тестовых методов `tests/` — только через
   раздел SPEC «Меняемое поведение» (инвариант 38); на момент написания
   SPEC такие методы не выявлены, раздел отсутствует.

## Критерии приёмки

AC-1. Случай 10.10 в песочнице: задача `approve` → `in_dev`, затем
`answer` с файлом указания, артефакты готовы к переходу в `verifying` —
`auto` запускает шаг developer, записи «шаг developer не нужен» в
журнале нет, задача не уходит в `verifying` до шага developer; мутация
«гейт не смотрит журнал ANSWER» ловится.

AC-2. Отказ из требования 1 относится к классу «чинит роль»
(`refusal_classes.refusal_class` действия отказа возвращает «чинит
роль»), бриф запущенного на него шага developer несёт этот ANSWER.

AC-3. Шаг developer начат после ANSWER (в том числе без изменения кода)
— переход `in_dev → verifying` проходит по обычным условиям.

AC-4. Тот же отказ требования 1 повторился после шага developer в этом
визите `in_dev` — `auto` останавливается, второго шага developer подряд
по этому отказу нет.

AC-5. Задача без ANSWER и задача с ANSWER, отработанным шагом developer
до текущего входа в `in_dev`, — переход `in_dev → verifying` выполняется
как сегодня (без отказа требования 1).

AC-6. Ручной `advance` Оператора в `in_dev` при неотработанном ANSWER —
отказ, текст которого содержит имя файла `ANSWER-n.md`; состояние
остаётся `in_dev`.

## Оценка объёма и деление

Прогноз диффа: 24 КиБ (гейт в `fsm_advance.py`/`advance_gates/review.py`,
строка класса в `refusal_classes.py`, регенерация карты, тесты) — меньше
половины потолка гейта ёмкости (256 КиБ).

Сработавший сигнал: число файлов/путей зоны ≥ 5 (5 записей поля
`zones`, из них `docs/codebase-map.md` и `tests/` — общие зоны,
собственно кода — 3 файла).

**Обоснование монолита.** Резать нечего: гейт рубежа `in_dev →
verifying` (`fsm_advance.py`/`advance_gates/review.py`) и класс его
отказа (`refusal_classes.py`) — одна атомарная смена механики. Гейт без
записи класса попадает в «чинит Оператор» по умолчанию
(`refusal_class`), и `auto` вместо шага developer останавливается —
промежуточное состояние ломает требование 2; запись класса без гейта —
мёртвая строка. Карта и тесты — сопровождение той же правки, а не
самостоятельные части.

## Не входит

- ANSWER в `review` (ревьювер) — вне задачи по ТЗ.
- Снятие эскалации из `verifying` с известным красным CI.
- Правка брифа: ANSWER в бриф уже попадает (`orchestrator/brief.py` —
  только чтение).
- `amend-tests` (01M4JD36367E5CG3GXDV429XTE слита).
- Полный прогон `tests/` (01M4K2767FXKZ8EW7AME81SZ9N) — её держит пульт.
- Правка файлов «только чтение» из ТЗ: `orchestrator/auto.py`,
  `orchestrator/answer.py`, `orchestrator/brief.py`, `orchestrator/fsm.py`,
  `orchestrator/store.py`, `orchestrator/config.py`, `orchestrator/runner.py`,
  `orchestrator/amend.py`, `orchestrator/acceptance.py`,
  `orchestrator/notes.py`, `orchestrator/suite_lock.py`,
  `orchestrator/advance_gates/tests_writing.py`, `scripts/`,
  `.github/workflows/ci.yml`, `tests/test_invariants.py`,
  `docs/invariants.md`, `docs/triggers.md`, `docs/adr/`, `docs/roadmap.md`,
  `docs/backlog.md`, `docs/operator-session.md`, `templates/`, `skills/`,
  `CLAUDE.md`, `models.yaml`, `roles.yaml`, `targets.yaml`, `.artel/`.

## Материалы

- `tasks/01M4KAYMW2YRFB7G0442WFVSHA/TZ.md`.
- Случай 01M4G8KPP8DVNBCPGCAPSVMAKZ, журнал 10.10 05:20:35Z–05:26:08Z.
- `orchestrator/advance_gates/review.py::_review_rework_gate` — прецедент
  гейта «шаг роли после события».
- `orchestrator/advance_gates/refusal_classes.py` — перечень классов;
  подкласс `ROLE_NOT_FINISHED_REFUSAL_ACTIONS` освобождён от
  повтор-остановки, что противоречит требованию 5 для нового отказа.
