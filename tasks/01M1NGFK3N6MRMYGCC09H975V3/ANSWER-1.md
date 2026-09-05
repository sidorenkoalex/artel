---
task: 01M1NGFK3N6MRMYGCC09H975V3
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

---
task: 01M1NGFK3N6MRMYGCC09H975V3
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Общий блокер снят: часть 1 (01M1NEEWH5K1XPFRDGRMPYSBXJ) смержена в main
(коммит слияния a76836aa, RETRO 849bb8ac). Ниже — контракт, которого не
хватало тест-автору. Планку писать по нему; всё, чего в main ещё нет,
делает разработчик этой задачи в её зонах.

1. Журнал прогонов канарейки (AC-1, AC-2, AC-3, AC-4, AC-6). Это таблицы
   БД пульта `canary_runs` и `canary_baseline` в `orchestrator/store.py`
   (создание — в общей инициализации схемы, запись — `store.insert_canary_run`,
   вызов — `orchestrator/canary.py`). Текущие поля `canary_runs`:
   `id, run_stamp, title, task_id, steps, cost_usd, review_iterations,
   escalations, outcome, expected_escalation, actual_escalation,
   marker_mismatch, created_at`. `run_stamp` — метка прогона в UTC вида
   `%Y%m%dT%H%M%SZ`, общая для всех задач одного запуска `canary --k <N>`;
   `outcome` — конечное состояние задачи (после штатного завершения
   канарейки всегда `killed`, поэтому «зелёность» по нему не читается).

2. Что добавляет часть 2 в журнал (решение Оператора, зона задачи —
   `orchestrator/store.py`, `orchestrator/canary.py`): два столбца
   `canary_runs`, миграция идемпотентная (`ALTER TABLE … ADD COLUMN`
   при отсутствии столбца, как у прочих миграций store):
   - `main_sha TEXT` — sha HEAD `config.ROOT` (main пульта) на момент
     старта прогона; заполняет `canary.py` при записи строки;
   - `verdict TEXT` — `green`, если задача-канарейка дошла до
     `merge_gate` или `verifying` и убита там штатно (то есть прошла
     приёмку) и `marker_mismatch = 0`; иначе `red`.
   «Зелёный прогон» = все строки одного `run_stamp` имеют `verdict =
   'green'`. Фикстуры теста строят строки напрямую через
   `store.insert_canary_run` (сигнатура расширяется параметрами
   `main_sha`, `verdict`) — стенд канарейки для этого не нужен.

3. «Не старше N мержей main» (AC-1..AC-4). N — именованная константа
   `CANARY_MAX_MERGES_SINCE_GREEN` в `orchestrator/config.py` (значение
   по умолчанию 10; тесты читают константу по имени, не число). Возраст
   зелёного прогона относительно целевого sha T: `main_sha` прогона S
   обязан быть предком T (`git merge-base --is-ancestor S T`), возраст =
   `git rev-list --count --merges S..T` в `config.ROOT`. Прогон «не
   старше N» ⇔ возраст < N. Если S не предок T — прогон не считается.
   `doctor` (AC-3, AC-4) считает возраст последнего зелёного прогона
   относительно локальной ветки main в `config.ROOT` (без обращения к
   сети — инвариант 35) и поднимает алерт `kind=trigger`, `source=canary`
   при возрасте ≥ N; повторно открытый алерт не дублируется
   (`store.open_alert_exists`). Пустой журнал (ни одного зелёного
   прогона) — тоже алерт `trigger` с текстом «канарейка ни разу не
   прогонялась» и отказ `pin-update` по AC-1.

4. Отказ `pin-update` (AC-1). Именованный отказ начинается словами
   `pin-update: нет зелёного прогона канарейки` и содержит команду
   запуска `python3 orchestrator/artel.py canary --k <N>`; пин (HEAD
   `config.ROOT`) не меняется, `git merge --ff-only` не вызывается.
   Проверка — до fetch/merge, после текущей проверки аргументов. Обхода
   SPEC не предусматривает — порядок ввода в эксплуатацию: сначала
   прогон канарейки на текущем main, затем мерж этой задачи.

5. Контракт `pin --to` (AC-5, AC-6, AC-7). Подкоманда `pin` в
   диспетчере `orchestrator/artel.py`, реализация — `orchestrator/pin.py`,
   функция `cmd_pin_to(sha: str | None)`. Вызовы: `artel.py pin --to <sha>`
   и `artel.py pin --to`. Поведение:
   - `<sha>` задан: sha обязан существовать в `config.ROOT` и быть предком
     текущего HEAD (откат — назад по истории main); рабочее дерево ROOT
     обязано быть чистым. Тогда `git reset --hard <sha>` в `config.ROOT`;
     origin и ветка main на origin не трогаются ни fetch, ни push
     («не изменяя main» = main пульта на origin остаётся прежним).
   - без `<sha>`: цель — `main_sha` самого свежего зелёного прогона по
     `created_at`; если такого нет — именованный отказ `pin --to: в
     журнале нет зелёного прогона канарейки`; если он равен текущему HEAD
     — именованный отказ `pin --to: пин уже на sha последнего зелёного
     прогона`.
   - журнал (AC-7): через `store.journal` с `task_id =
     config.PIN_UPDATE_JOURNAL_TASK_ID`, actor `operator`. Успех — действие
     `pin откатан`, detail `pin откатан: <старый sha> -> <новый sha>;
     причина: <явный sha Оператора | последний зелёный прогон канарейки
     <run_stamp>>`. Любой отказ — действие `pin откат отклонён`, detail с
     причиной; HEAD не меняется. Каждый вызов даёт ровно одну запись.
   - код возврата: успех 0, любой отказ — ненулевой (`sys.exit` с текстом,
     как у `pin-update`).

6. Зелёность существующего набора (AC-8) — по прецеденту остаётся
   `skip`, проверяется CI.

7. Изоляция в тестах: `config.ROOT` и БД подменяются, как в
   `tests/test_pin_update*.py` и песочнице `tests/sandbox.py`; сеть
   тестам запрещена (инвариант 35), поэтому сценарии `doctor` и `pin --to`
   строятся на локальном репозитории-фикстуре с искусственными коммитами
   слияния (`git merge --no-ff`).
