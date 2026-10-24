---
task: 01M5QR7KGYZNVWDP5H86S9PY04
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Скорость пульта, git 1: одна проверка origin при отправке документов и отправка в сверке с origin только при расхождении

# Скорость пульта, git 1: одна проверка `origin` при отправке ссылки документов и отправка в сверке с `origin` только при расхождении

## Факты

Решение Оператора 24.10.2026 (дословно): «Заводи рекомендованный набор: быстрая задача по full_suite_lock и doctor_duration сейчас, задачи по git 1, 5, 2, 3, 4 — по очереди между волнами; шаблон песочниц и подделку pytest — отложить.» Повод — исследование вызовов git в командах пульта 24.10 (шпион процессов на 9c0e8b8c): тест `merge_outcome_gate::Ac5` (34 точки входа пульта) делает 1332 вызова git, из них `remote` — 84, `push` — 42, `ls-remote` и `fetch` — десятки; на один `cmd_approve` — около 166 вызовов git и 4 отправки документов. Сверено с origin/main 9c0e8b8c.

- `orchestrator/artifact_branch.py`:
  - `_attempt_push(branch, repo)` (:367): перед отправкой проверяет `repo == _NO_REPO or gitcmd.has_no_remote(repo)` (:378; `gitcmd.has_no_remote` — `git remote`, `orchestrator/gitcmd.py:568`), затем `git push -q origin <ref>:<ref>` с повтором ответа сервера до `PUSH_SERVER_RETRY_ATTEMPTS`.
  - `_origin_configured(repo)` (:442) — `git remote get-url origin`.
  - `_send(task_id, repo)` (:450): `_origin_configured` (:458), затем `_attempt_push` (:461) — то есть два вызова git (`remote get-url` и `remote`) перед каждой отправкой; журнал — при отказе, повторе или досылке после отказа.
  - `push(task_id)` (:428): `_attempt_push` без `_origin_configured`.
  - `origin_sync_refusal(task_id)` (:477): `_origin_configured` (:489), `local = _head(...)`, если `local` есть — `_send` всегда (push даже когда отправлять нечего), затем `gitcmd.remote_ref_state` (`ls-remote`) и сравнение. Зовут: `orchestrator/fsm_merge_gate.py:1349` (гейт мержа), `orchestrator/cleanup.py:681` (закрытие).
- `_origin_configured` истинно ⇒ у репозитория есть запись `origin` ⇒ `git remote` не пуст: вторая проверка в `_attempt_push` после первой ответ не меняет.
- Каждый вызов git в тестах — 9–16 мс, отправка в локальный bare-репозиторий — 60–190 мс; в работе отправка и `ls-remote` — обращения к GitHub.
- Параллельно идут волны сведения тестов (3м-1 и следующие); их ТЗ требуют повторить таблицу мутаций «до», если подтяжка main изменила `orchestrator/` — изменение этой задачи это вызовет.

## Требования

1. `_send`: после истинного `_origin_configured` отправка не проверяет наличие remote второй раз (`_attempt_push` получает признак уже проверенного `origin` либо равный по смыслу приём); у `push(task_id)` и прочих вызывающих `_attempt_push` проверка `has_no_remote` остаётся. Исходы, тексты журнала и возвращаемые значения `_send`/`push` не меняются, в том числе «нет origin», «ошибка git», «ответ сервера» с повторами, non-fast-forward.
2. `origin_sync_refusal`: сначала `gitcmd.remote_ref_state`; если `local` пуст или равен состоянию `origin` — отправки нет; если различаются и `local` есть — `_send`, затем повторная сверка `gitcmd.remote_ref_state` и прежнее сравнение. Отказ «origin не ответил» на первой сверке — прежний текст отказа без отправки. Тексты отказов и `None` — прежние для каждого из исходов: совпадает; в origin нет ссылки (после досылки — совпадает либо прежний отказ «нет в origin»); расходится; origin не ответил. Вызывающие (`fsm_merge_gate.py:1349`, `cleanup.py:681`) не меняются.
3. Тесты (новый файл `tests/test_<id>_origin_push_checks.py` в стиле pytest, ADR-0027; у каждой функции — «Ловит мутацию:»): (а) `_send` при настроенном origin делает ровно один вызов `git remote …` перед `push` (шпион на `gitcmd`/`_git`); (б) `_send` без origin — без `push`, `False`; (в) `push(task_id)` без remote — исход «нет origin» без `push`; (г) `origin_sync_refusal` при совпадении локальной ссылки с origin — без `push`, `None`; (д) локальная впереди origin — `push`, затем повторная сверка, `None` при успешной досылке; (е) origin не ответил на первую сверку — отказ прежним текстом без `push`; (ж) ссылки нет в origin и досылка не удалась — прежний отказ «нет в origin»; (з) расхождение после досылки — прежний отказ «расходится». Песочница — настоящий git с локальным bare-origin (`tests/sandbox.py`, `tests/fixtures.py`).
4. Число вызовов: в PLAN — счёт вызовов `git remote`, `git push`, `git ls-remote` на тесте `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac5PassToPassTest` (или его наследнике после сведения) до и после (шпион процессов во временной копии; файл тестов не меняется).
5. Существующие тесты не правятся и остаются зелёными.

Зоны: orchestrator/artifact_branch.py, docs/codebase-map.md, tests/

Ограничение зон по смыслу: в `orchestrator/artifact_branch.py` — только `_send`, `_attempt_push` (признак проверенного origin) и `origin_sync_refusal`; в `tests/` — только новые файлы.

Только чтение: orchestrator/gitcmd.py, orchestrator/fsm_merge_gate.py, orchestrator/cleanup.py, orchestrator/docs_fetch.py, orchestrator/doctor/artifact_branches.py, orchestrator/store.py, tests/sandbox.py, tests/fixtures.py, scripts/guard.py.

Не входит: прочий код orchestrator/ вне зон; одна отправка документов на команду (задача git 2); память чтений и перевод прямых вызовов git (git 3, 4); объединение чтений (git 5); одно получение origin/main на approve (решение Оператора); изменение `doctor`.

Бюджет: $30.
