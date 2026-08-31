---
task: T079
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: B1b: GitHub-адаптер, Draft-MR и состояние verifying

## Подход

Реализация ложится тремя независимыми, но последовательно зависящими
друг от друга пластами:

1. **GitHub-адаптер** (`orchestrator/github_adapter.py`, новый модуль):
   `ensure_draft_mr`/`undraft_mr` — побочные эффекты входа в `in_dev`
   и `merge_gate` (требования 1-2), не условия перехода. Идемпотентность
   Draft MR несёт колонка `tasks.draft_mr_created` (не повторный запрос
   к GitHub на каждый вход в `in_dev`), канареечные задачи и не-github
   таргеты пропускаются. Любой сбой адаптера — инцидент (`journal` +
   `alerts.raise_alert`), не отказ перехода FSM: тем же приёмом, что
   `fsm.py::_regenerate_and_commit_map`/`_generate_and_commit_retro`
   (T042/T043) уже используют для «побочных, не блокирующих» действий.
   Операция merge (требование 3) отдельного вызова не несёт: ANSWER-1
   (вопрос 1) прямо допускает автоопределение GitHub по коммиту в
   истории `main` как валидный способ — `git merge --no-ff` (fsm.py,
   не тронут) делает голову ветки задачи предком `main`, и GitHub сам
   закрывает Draft MR смерженным после push. Второй вызов адаптера
   здесь добавлял бы точку отказа там, где результат уже наблюдаем
   бесплатно.

2. **Статус CI в `verifying`** (`orchestrator/ci.py::verifying_status`,
   `run_list`): четыре исхода требования 5 (AC-5..AC-8) — зелёный,
   «проверок нет вовсе», «проверки идут» (check-runs коммита ИЛИ
   `gh run list` по ветке — второй источник против задержки события
   GitHub, роадмап P3/T040), красный. Только читает, ничего не
   «будит» (требование 5, AC-12).

3. **Состояние `verifying`** (`orchestrator/fsm.py`): вставлено между
   `review` и `acceptance` (требование 4). `_cmd_advance` из `review`
   при свежем `approved` + зелёных `acceptance_tests` теперь ведёт в
   `verifying`, не в `acceptance` — автогейт `acceptance`
   (`_maybe_autogate_acceptance`) переехал на вход `verifying ->
   acceptance`, сама логика автогейта не тронута. Потолок ожидания —
   `config.LIMIT_VERIFYING_ATTEMPTS`, счётчик попыток (не время: SPEC
   требование 9 явно не специфицирует механизм периодического вызова
   `advance`, часы мерить нечем), сбрасывается на каждом входе в
   `verifying`. `reject` расширен на `verifying` тем же приёмом, каким
   T052 расширила его на `merge_gate` (требование 8). `canary`
   (`orchestrator/canary.py`) `verifying` не дожидается — убивает
   задачу тем же приёмом, что и на `merge_gate` (канареечные задачи не
   заводят Draft MR и не имеют настоящего CI ветки).

Существенная часть этого плана (модули `github_adapter.py`, `ci.py`,
вставка `verifying` в `fsm.py`, `canary.py`, схема БД) была написана
предыдущим шагом developer этой же задачи, прерванным таймаутом
(коммит `ddddf6c`, «WIP-чекпоинт после таймаута шага developer»); эта
итерация приняла её как основу (код и тесты сверены построчно с SPEC/
ANSWER-1 и всеми AC), нашла и закрыла единственный содержательный
пробел (юнит-тесты модулей — см. «Шаги», п.2) и довела задачу до
`status: ready`, включая находку и оформление эскалации ниже.

Итерация 2 (после REVIEW.md, `changes_requested`, замечание 1, major):
`_maybe_ensure_draft_mr` действительно звалась не на всех входах в
`in_dev` — двух из восьми не хватало. Замечание — класса «побочный
эффект входа в состояние X реализован не на ВСЕХ фактических путях
входа в X» (то же REVIEW, «Предложения системе»): закрыт приёмом
«найди все аналогичные места», не точечно — `grep -n 'set_state(conn,
task_id, "in_dev"' orchestrator/fsm.py` подтвердил ровно 7 буквальных
мест плюс один динамический (`back = t["escalated_from"] or "in_dev"`,
куда `in_dev` приходит не литералом), все восемь теперь вызывают узел.
Закрыто:
- `orchestrator/fsm.py:1329-1334` (`_cmd_approve`, ветка `escalated` —
  возврат `back = t["escalated_from"] or "in_dev"`): `_maybe_ensure_
  draft_mr` зовётся после `set_state`, но ТОЛЬКО когда `back ==
  "in_dev"` — возврат из эскалации в другое состояние (`spec_writing`,
  `tests_writing`, если шаг там же и упал) Draft MR заводить не должен,
  это не вход в `in_dev`.
- `orchestrator/fsm.py:1379-1386` (`_cmd_reject` из `acceptance`,
  унаследованный путь T052, ветка «лимит не исчерпан»): добавлен вызов
  сразу за `set_state(..., "in_dev", ...)`, тем же приёмом, что уже
  стоял в ветках `merge_gate`/`verifying` этой же функции. Ветка
  «лимит исчерпан» (`accept_rejects > LIMIT_ACCEPT_REJECTS`) ведёт в
  `escalated`, не в `in_dev`, — там узел не нужен и не добавлен.

Регресс на оба случая — новый файл `tests/test_fsm_draft_mr_reentry.py`
(«Шаги», п.2а): белым ящиком, `github_adapter.ensure_draft_mr`
подменена моком, проверяется факт вызова/невызова на каждой из веток
`_cmd_approve`(escalated)/`_cmd_reject`(acceptance), включая
отрицательные случаи (возврат не в `in_dev`, эскалация по лимиту).
`python3 -m unittest discover -s tests` — 1068 тестов (было 1063 в
итерации 1: +5 новых юнит-тестов), 3 красных — тот же названный список
(«Эскалация» ниже, не новые); `tasks/T079/acceptance_tests/` — 19/19.

## Шаги

1. GitHub-адаптер, `verifying` в FSM, статус CI, `reject`-расширение,
   canary — `orchestrator/{github_adapter,ci,fsm,config,store,canary}.py`
   + правка существующих тестов под новую точку остановки `review ->
   verifying` (`tests/test_acceptance_tests_flow.py`,
   `tests/test_advance_guard.py`, `tests/test_auto_cycle.py`,
   `tests/test_review_freshness.py` — только замена ожидаемого
   состояния `acceptance` → `verifying` и текста подсказки, поведение
   тестов не ослаблено). Локед `tasks/T079/acceptance_tests/` (19
   тестов, AC-1..AC-14) — зелёные без единой правки.
2. Юнит-тесты новых модулей в изоляции (пробел предыдущей итерации):
   `tests/test_ci_status.py` — `RunListTest`, `VerifyingStatusTest`
   (разбор ответа `gh run list`, сведение к одному из четырёх исходов,
   AC-12 — `run_list` не зовётся, если check-runs уже ответили);
   `tests/test_github_adapter.py` (новый) — идемпотентность
   `ensure_draft_mr`/`undraft_mr`, пропуск канареечных/не-github
   задач, сбой адаптера = инцидент, а не исключение.
   2а. (итерация 2, замечание 1 REVIEW.md) `orchestrator/fsm.py` —
   `_maybe_ensure_draft_mr` добавлена в двух пропущенных точках входа
   в `in_dev` (возврат из `escalated`, `reject` из `acceptance`);
   `tests/test_fsm_draft_mr_reentry.py` (новый) — регресс на обе точки
   и на их отрицательные соседние ветки.
3. `docs/codebase-map.md` — регенерация (`scripts/codebase_map.py`)
   тем же коммитом (conventions-core): подхватывает
   `orchestrator/github_adapter.py`, новые функции `ci.py` и новый
   тестовый модуль п.2а.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (Draft MR на первый вход в in_dev, один на цикл) | 1 |
| 2 (undraft на входе в merge_gate) | 1 |
| 3 (merge — побочный эффект локального push, не API-вызов) | 1 |
| 4 (verifying между review и acceptance) | 1 (см. «Эскалация» — единственный незакрытый остаток) |
| 5 (четыре исхода статуса CI в verifying) | 1, 2 |
| 6 (потолок ожидания → escalated) | 1 |
| 7 (красный CI не выталкивает автоматически) | 1 |
| 8 (reject расширен на verifying) | 1 |
| 9 (механизм периодического вызова advance вне объёма — контракт разового вызова) | 1 |

## Влияние на систему

Diff — только `orchestrator/` (новые/изменённые модули, схема БД:
две новые колонки `verifying_attempts`, `draft_mr_created` с
дефолтами через `store.add_column`, обратно совместимо с
существующими БД), `tests/` и `docs/codebase-map.md` — ни один путь
из `no_paths` target `artel` не тронут (AC-14; проверено `git diff
main --stat`, ниже).

Механика T052 (три исхода провала merge из `merge_gate`) и T053
(мьютекс merge-окна) не изменена ни строкой — `_cmd_approve_merge_gate`
не тронута этой задачей, тесты `tests/test_merge_lock.py`,
`tests/test_advance_guard.py` (переходы merge_gate) зелёные (AC-13).

Единственный след системного трения — **три теста
`tests/test_invariants.py`** (список и разбор — «Эскалация» ниже)
красные не по вине реализации, а потому что кодируют СТАРЫЙ инвариант
(`review` ведёт в `acceptance` за один `advance`), который требование 4
этой же задачи целенаправленно отменяет как раз для того, чтобы
завести ожидание CI. Файл в `no_paths` (AC-14) — право менять его есть
только у Оператора через ADR (ADR-0002, принцип целостности), поэтому
не правлю. Полный прогон `python3 -m unittest discover -s tests` —
1068 тестов, 3 красных (список ниже), без ошибок; локед
`tasks/T079/acceptance_tests/` — 19/19 зелёные.

Откат — `git revert` коммитов этой ветки; новые колонки БД не имеют
обратной миграции (SQLite `ADD COLUMN` необратим без пересоздания
таблицы), но существующий код не читает их при отсутствии — потерь
данных откат не создаёт.

## Риски

- `config.LIMIT_VERIFYING_ATTEMPTS = 20` — начальное значение (SPEC:
  «именованная константа», значение не специфицировано), не
  калибровано на реальном темпе появления check-runs после push;
  правка — одна константа в `config.py`.
- `github_adapter.ensure_draft_mr` делает `git push -u origin <branch>`
  безусловно при первом входе в `in_dev` — до этой задачи ветка
  задачи локальная до самого merge; теперь она видна на GitHub с
  первого коммита PLAN.md. Это прямое следствие требования 1 (Draft
  MR не завести без публикации ветки), не самостоятельное решение.

## Предложения системе

- Класс «SPEC вставляет промежуточное состояние между двумя уже
  существующими» напрямую бьёт по любому неослабляемому regression-
  тесту, который свипует «одна команда — один переход» (здесь —
  `tests/test_invariants.py::FreshVerdictGuardsAcceptanceTest`/
  `CountersNeverResetTest`, T051 раньше поймал тот же класс на
  `MergeOnlyFromMergeGateTest`). Стоит проговорить в скиле analyst
  (`spec-writing` или аналог): проектируя переход, добавляющий новое
  промежуточное состояние в существующий маршрут FSM, явно сверяться
  с `tests/test_invariants.py` на предмет тестов, зависящих от числа
  шагов между двумя уже существующими состояниями, и либо закладывать
  ADR заранее, либо явно фиксировать ожидаемую красноту в самом SPEC
  («Не входит»/«Критерии приёмки»), а не оставлять находку developer'у.

## Эскалация

### Вопросы

1. **[Блокирует зелёный `tests/test_invariants.py` на этой ветке; не
   блокирует ни один AC этой задачи — весь диапазон `tasks/T079/
   acceptance_tests/` (19/19, включая AC-4) зелёный без единой
   правки.]** Требование 4 («прямого перехода `review -> acceptance`
   для этого исхода больше нет», AC-4) и локед
   `tasks/T079/acceptance_tests/test_ac4_review_to_verifying.py`
   требуют, чтобы ОДИН вызов `advance` из `review` с approved-
   вердиктом останавливался в `verifying`, даже если CI уже зелёный
   (тест использует ту же песочницу `FsmTest` с CI, зелёным по
   умолчанию, — `self.set_ci(GREEN_CI)` в `setUp`, — и явно
   утверждает `state() == "verifying"`, не `"acceptance"`, после
   этого единственного вызова). Три теста в неослабляемом
   `tests/test_invariants.py` (ADR-0002, докстринг файла: «ослабить,
   отключить... может только Оператор отдельным ADR») используют ТУ
   ЖЕ песочницу с тем же зелёным CI по умолчанию и после ОДНОГО
   вызова `advance` из `review` утверждают обратное —
   `state() == "acceptance"`:
   - `FreshVerdictGuardsAcceptanceTest.
     test_every_return_to_dev_requires_a_new_verdict`
     (tests/test_invariants.py:673, 685)
   - `FreshVerdictGuardsAcceptanceTest.
     test_escalation_and_return_do_not_make_the_verdict_fresh`
     (tests/test_invariants.py:715)
   - `CountersNeverResetTest.
     test_no_transition_of_the_full_cycle_resets_a_counter`
     (tests/test_invariants.py:934)

   Оба утверждения — с идентичными входными условиями (тот же
   `FsmTest`, тот же зелёный CI по умолчанию, тот же единственный
   `advance`) — не могут быть верны одновременно ни при каком выборе
   кода: любая реализация, доводящая `review` до `acceptance` в один
   вызов при уже-зелёном CI («протащить» проверку внутри того же
   `advance`), нарушает сам AC-4 (который и написан для того, чтобы
   не пропустить такое «протаскивание» — докстринг теста: «review ->
   acceptance по свежему approved+зелёным acceptance_tests больше не
   существует напрямую»). Правка `tests/test_invariants.py` —
   `no_paths` (AC-14) и вне полномочий роли разработчика (ADR-0002).
   - **(default, если Оператор промолчит — принято в этой итерации)**
     реализация следует SPEC/AC-4 буквально (`review` всегда
     останавливается в `verifying`, вторым `advance` уходит дальше);
     три названных теста остаются красными до отдельного ADR-правки
     `tests/test_invariants.py`. Готовый минимальный патч (Оператору
     достаточно применить и закоммитить самому — правка не входит в
     эту ветку): в каждом из трёх мест после `self.write_review
     ("approved", N); self.capture(fsm.cmd_advance, self.TASK)`
     вставить `self.assertEqual(self.state(), "verifying")` и ещё
     один `self.capture(fsm.cmd_advance, self.TASK)` перед
     существующим `self.assertEqual(self.state(), "acceptance")` —
     семантика инварианта (свежий вердикт → в итоге приёмка, счётчики
     не сбрасываются) сохраняется буква в букву, меняется только
     число шагов.
   - **(б)** Оператор считает конфликт поводом пересмотреть
     требование 4 (например: `verifying` пропускается синхронно,
     если CI уже зелёный на момент входа) — тогда AC-4 и
     `test_ac4_review_to_verifying.py` тоже требуют правки аналиста
     (тот же локед-статус, что и `tests/test_invariants.py`, только
     артефакт другой роли) — не рекомендую: это возвращает поведение
     «review иногда ведёт прямо в acceptance», которое требование 4
     явно и осознанно убирает.

### Контекст

- Реализация (шаги 1-3 «Шаги», включая п.2а итерации 2) завершена и
  прогнана: `python3 -m unittest discover -s tests` — 1068 тестов,
  3 красных (см. вопрос 1), 0 ошибок; `tasks/T079/acceptance_tests/`
  — 19/19 (включая AC-4); `tests/test_merge_lock.py`, переходы
  `merge_gate` в `tests/test_advance_guard.py` — зелёные (AC-13,
  T052/T053 не задеты).
- `docs/codebase-map.md` регенерирован тем же коммитом.
- Diff ограничен `orchestrator/`, `tests/`, `docs/codebase-map.md`
  (AC-14) — `git diff main --stat` не показывает ни одного пути из
  `no_paths` target `artel`.

### Блокирует

Полностью зелёный `python3 -m unittest discover -s tests` на этой
ветке — блокирован тремя тестами `tests/test_invariants.py`,
правка которых вне полномочий роли разработчика. Саму задачу
(AC-1..AC-14, критерии приёмки SPEC) это не блокирует — весь локед
`tasks/T079/acceptance_tests/` зелёный.
