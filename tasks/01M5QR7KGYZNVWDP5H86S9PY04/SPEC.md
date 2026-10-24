---
task: 01M5QR7KGYZNVWDP5H86S9PY04
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/artifact_branch.py, docs/codebase-map.md, tests/
budget_usd: 30
---

# SPEC: Скорость пульта, git 1 — одна проверка origin при отправке документов и отправка в сверке с origin только при расхождении

## Контекст
Решение Оператора 24.10.2026: задачи по git 1, 5, 2, 3, 4 идут по очереди
между волнами сведения тестов; эта задача — git 1. Повод — исследование
вызовов git 24.10 на 9c0e8b8c: тест `merge_outcome_gate::Ac5` делает 1332
вызова git (`remote` — 84, `push` — 42), один `cmd_approve` — около 166
вызовов git и 4 отправки документов. Каждый вызов git в тестах стоит 9–16 мс,
отправка в локальный bare-репозиторий — 60–190 мс; в работе отправка и
`ls-remote` идут в GitHub.

Сверено аналитиком с деревом ветки (`orchestrator/artifact_branch.py`):
- `_attempt_push(branch, repo)` (:367) проверяет `repo == _NO_REPO or
  gitcmd.has_no_remote(repo)` (:378; `git remote`), затем `git push -q origin
  <ref>:<ref>` (:384) с повтором ответа сервера до
  `PUSH_SERVER_RETRY_ATTEMPTS`.
- `push(task_id)` (:425) зовёт `_attempt_push` без `_origin_configured`.
- `_origin_configured(repo)` (:442) — `git remote get-url origin`.
- `_send(task_id, repo)` (:451): `_origin_configured` (:458), затем
  `_attempt_push` (:461) — два вызова `git remote …` перед каждой отправкой.
  Истинный `_origin_configured` значит, что запись `origin` есть и `git
  remote` не пуст: вторая проверка ответа не меняет.
- `origin_sync_refusal(task_id)` (:477): `_origin_configured` (:489), `local =
  _head(...)` (:491), при непустом `local` — `_send` всегда (:493), даже когда
  отправлять нечего; затем `gitcmd.remote_ref_state` (:494) и сравнение.
  Зовут: `orchestrator/fsm_merge_gate.py:1349` (гейт мержа),
  `orchestrator/cleanup.py:681` (закрытие).

Параллельно идут волны сведения тестов; их ТЗ требуют повторить таблицу
мутаций «до», если подтяжка main изменила `orchestrator/`, — правка этой
задачи это вызовет.

## Требования

1. `_send`: после истинного `_origin_configured` отправка не проверяет наличие
   remote второй раз (`_attempt_push` получает признак уже проверенного
   `origin` либо равный по смыслу приём). У `push(task_id)` и прочих
   вызывающих `_attempt_push` проверка `has_no_remote` остаётся. Исходы, тексты
   журнала и возвращаемые значения `_send`/`push` не меняются, в том числе
   «нет origin», «ошибка git», «ответ сервера» с повторами, non-fast-forward.
2. `origin_sync_refusal`: сначала `gitcmd.remote_ref_state`; если `local` пуст
   или равен состоянию `origin` — отправки нет; если различаются и `local`
   есть — `_send`, затем повторная сверка `gitcmd.remote_ref_state` и прежнее
   сравнение. Отказ «origin не ответил» на первой сверке — прежний текст отказа
   без отправки. Тексты отказов и `None` — прежние для каждого из исходов:
   совпадает; в origin нет ссылки (после досылки — совпадает либо прежний отказ
   «нет в origin»); расходится; origin не ответил. Вызывающие
   (`fsm_merge_gate.py:1349`, `cleanup.py:681`) не меняются.
3. Тесты — новый файл `tests/test_01m5qr7kgyznvwdp5h86s9py04_origin_push_checks.py`
   в стиле pytest (ADR-0027); у каждой функции — «Ловит мутацию:». Покрывают
   случаи AC-1–AC-8. Песочница — настоящий git с локальным bare-origin
   (`tests/sandbox.py`, `tests/fixtures.py`).
4. Число вызовов: в PLAN — счёт вызовов `git remote`, `git push`, `git
   ls-remote` на тесте
   `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac5PassToPassTest`
   (или его наследнике после сведения) до и после правки. Счёт снимается
   шпионом процессов во временной копии; файл тестов при этом не меняется.
5. Существующие тесты не правятся.

## Критерии приёмки

AC-1. `_send` при настроенном `origin` делает ровно один вызов `git remote …`
перед `git push` (шпион на `gitcmd`/`_git`); отправка проходит, `_send`
возвращает `True`.

AC-2. `_send` без `origin` не делает `git push` и возвращает `False`.

AC-3. `push(task_id)` для репозитория без remote даёт исход «нет origin»
(`PUSH_REASON_NO_ORIGIN` в журнале, возврат `False`) без вызова `git push`.

AC-4. `origin_sync_refusal` при совпадении локальной `refs/artifacts/<id>` с
`origin` не делает `git push` и возвращает `None`.

AC-5. `origin_sync_refusal`, когда локальная ссылка впереди `origin`, делает
`git push`, затем повторную сверку `ls-remote` и при успешной досылке
возвращает `None`.

AC-6. `origin_sync_refusal`, когда `origin` не ответил на первую сверку,
возвращает прежний текст отказа «отказ: origin не ответил на сверку <ветка> —
<причина>» без вызова `git push`.

AC-7. `origin_sync_refusal`, когда ссылки нет в `origin` и досылка не удалась,
возвращает прежний отказ «отказ: <ветка> нет в origin (локально <sha>) —
документы задачи не отправлены».

AC-8. `origin_sync_refusal`, когда после досылки ссылки расходятся, возвращает
прежний отказ «отказ: <ветка> расходится с origin — локально <sha>, в origin
<sha>».

AC-9. Раздел PLAN несёт счёт вызовов `git remote`, `git push`, `git ls-remote`
на `Ac5PassToPassTest` (или его наследнике) до и после правки, снятый
шпионом процессов во временной копии.

## Оценка объёма и деление
Сработавший сигнал: `budget_usd` ≥ $30 (бюджет $30 задан ТЗ). Других сигналов
нет: зона — 3 записи, критериев 9, текста-маркера нет.

Обоснование монолита (материал для решения Оператора): правка — две функции
одного модуля (`_send`/`_attempt_push` и `origin_sync_refusal`) плюс новый файл
тестов, оценка диффа — единицы КиБ. Части по зонам (код без тестов, тесты без
кода) самостоятельно не мержимы: тесты AC-1, AC-4–AC-6 красны без правки кода,
а правка кода без них не несёт доказательства требования 3. Деление по
требованиям 1 и 2 возможно, но удваивает число шагов и бюджет ради правки в
десятки строк.

## Не входит
- Прочий код `orchestrator/` вне зон; в `orchestrator/artifact_branch.py` —
  всё, кроме `_send`, `_attempt_push` (признак проверенного origin) и
  `origin_sync_refusal`; в `tests/` — правка существующих файлов (только новые
  файлы).
- Правка вызывающих `fsm_merge_gate.py`, `cleanup.py` и файлов только для
  чтения: `orchestrator/gitcmd.py`, `orchestrator/docs_fetch.py`,
  `orchestrator/doctor/artifact_branches.py`, `orchestrator/store.py`,
  `tests/sandbox.py`, `tests/fixtures.py`, `scripts/guard.py`.
- Одна отправка документов на команду (задача git 2).
- Память чтений и перевод прямых вызовов git (git 3, 4).
- Объединение чтений (git 5).
- Одно получение origin/main на approve (решение Оператора).
- Изменение `doctor`.
- Зелёный полный набор `tests/` (требование 5 ТЗ, часть «остаются зелёными») —
  её держит пульт.

## Материалы
- `tasks/01M5QR7KGYZNVWDP5H86S9PY04/TZ.md`.
- Имя файла требования 3 совпадает с шаблоном долгоживущего теста задачи
  (`tests/test_<id>_<имя>.py`, ADR-0020; `scripts/guard.py::is_long_lived_test_path`).
