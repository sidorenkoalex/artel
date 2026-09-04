---
task: 01M1P9RJVYHTAC087J4B2CAR44
type: plan
author_role: developer
status: ready
schema_version: 3
---

# PLAN: Инкрементальный дифф ревью после A7: база из кодовой ветки (регрессия №10)

## Подход
Регрессия — в двух местах: (1) `record_fixation` для `config.DEFAULT_TARGET`
не пишет поле `код=` в запись «sha зафиксирован» (для НЕ-default target оно
уже есть); (2) `review.previous_verdict_sha` разбирает `detail` регулярным
выражением `sha=([0-9a-f]{4,40})`, которое ловит ПЕРВОЕ вхождение литерала
`sha=` в строке — это поле `sha=` (фиксационный/артефактный sha target'а),
а не `код=` (sha кодовой ветки) дальше по той же строке.

Правки:
1. `orchestrator/fixation.py` — новая функция `default_code_sha(conn,
   task_id)`: sha головы кодовой ветки задачи в `config.ROOT` (репозиторий
   пульта, где для self/артели реально живёт код — `runner.role_cwd`), не
   в артефактном/фиксационном репо `config.PROJECTS/<target>`. Читает
   `gitcmd.branch_head_sha(store.task_branch(conn, task_id))` — sha ветки
   независимо от текущего чекаута, тем же приёмом, что уже применяет
   `external_artifact_sha` к артефактной ветке пульта.
2. `orchestrator/store.py::record_fixation` — для `target == DEFAULT_TARGET`
   добавляет в `detail` поле `код={default_code_sha(...) or '—'}` — та же
   форма, что уже несёт ветка НЕ-default target (`код=`/`external_code_sha`).
   Поле `sha=` (фиксационный sha репо `config.PROJECTS/artel`) остаётся без
   изменений — требование 4 SPEC явно запрещает удалять его, только
   запрещает использовать его как базу diff.
3. `orchestrator/review.py::previous_verdict_sha` — регулярное выражение
   меняется на `код=([0-9a-f]{4,40})`: та же позиция в журнале
   (предпоследняя запись «sha зафиксирован»), то же вырожденное поведение
   (не распознан/меньше двух записей — пустая строка).
4. `orchestrator/review.py::review_package` — требование 2/AC-5: когда
   `iteration > 1`, но `prev_sha` пуст (база не определена — итерация 1 не
   подпадает под эту ветку, `incremental` для неё и так `False` по
   `iteration > 1`), в `parts` добавляется отдельная строка с причиной
   (диф всё равно полный, к `config.MAIN_BRANCH`, без изменений остального
   потока).
5. `orchestrator/alerts.py` — новый `kind="warning"` в `KINDS` + две тонкие
   обёртки: `raise_diff_not_collected_alert(conn, task_id, reason)`
   (дедуп через существующий `raise_alert`) и
   `close_diff_not_collected_alerts(conn, task_id)` (авто-ack, тот же
   приём, что `close_attention_alerts`, но без привязки к переходу FSM —
   закрывается на следующем УСПЕШНОМ сборе пакета той же задачи).
6. `orchestrator/runner.py::cmd_run` — после журналирования «ревью-пакет
   собран»: `package["iteration"] > 1` и `package["not_collected"]` —
   заводит warning; `package["iteration"] > 1` и diff собран — закрывает
   ранее открытые warning-алерты этой задачи. Итерация 1 алерт не трогает
   (там `not_collected` штатно пуст).
7. Правка существующих фикстур `tests/test_review_package.py::
   PreviousVerdictShaTest` — журнальные записи без поля `код=` (регресс,
   который эта задача чинит, AC-7 явно называет это зоной разработчика) —
   добавляется `код=` рядом с `sha=`, ожидаемые значения меняются на
   значения `код=`.
8. Юнит-тесты новых функций: `fixation.default_code_sha`,
   `store.record_fixation` (поле `код=` для default target),
   `alerts.raise_diff_not_collected_alert`/`close_diff_not_collected_alerts`.

## Шаги
1. `fixation.default_code_sha` + `store.record_fixation` (поле `код=` для
   default target) + юнит-тесты.
2. `review.previous_verdict_sha` — regex на `код=` + правка существующих
   фикстур `tests/test_review_package.py::PreviousVerdictShaTest`.
3. `review.review_package` — текст с причиной отсутствия базы при
   `iteration > 1` без `prev_sha` (требование 2/AC-5).
4. `alerts.py` (`kind=warning` + две функции) + `runner.cmd_run` (заводит/
   закрывает алерт по `not_collected`/`iteration`) + юнит-тесты.
5. Регенерация `docs/codebase-map.md` (правка `*.py` в orchestrator/).
6. Полный прогон `tests/` + `guard.py` на артефактах, коммит.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 3 |
| 3 | 4 |
| 4 | 1, 2 |

## Влияние на систему
- `record_fixation` для default target получает новое поле `detail` —
  аддитивная правка формата строки журнала (существующие потребители читают
  `sha=`/`чисто=` по месту, `код=` никто, кроме этой задачи, сегодня не
  парсит для default target — проверено `grep -rn "код="`). Поле `sha=`
  не убирается — фиксационный sha остаётся в журнале, просто перестаёт
  быть базой diff (AC-4).
- `previous_verdict_sha` — смена извлекаемого поля влияет ТОЛЬКО на журналы,
  где уже есть обе записи «sha зафиксирован» с полем `код=` (после этой
  задачи — всегда). Журналы прошлых задач без `код=` (default target,
  созданные до этой правки) деградируют туда же, куда и раньше вело
  отсутствие поля — пустая строка, полный diff к `main`, ничего не падает.
- Новый `kind="warning"` в `alerts.KINDS` — расширение множества, не
  изменение существующих (`incident`/`threshold`/`trigger`/`attention`)
  инвариантов их обработки.
- `runner.cmd_run` — новый импорт `alerts` (уже используется в других
  модулях оркестратора тем же приёмом, побочных эффектов на существующий
  путь `package is None` (роли без ревью-пакета) нет.
- `docs/codebase-map.md` регенерируется тем же коммитом (conventions-core):
  `runner.py` меняет набор импортов.
- Тесты не ослабляются: `tests/test_review_package.py::
  PreviousVerdictShaTest` меняет ФИКСТУРЫ (добавляет поле `код=`), не
  ассерты и не количество тестов — это тот же класс правки, что AC-7
  прямо называет обязанностью разработчика (регресс, который чинит эта
  задача).

## Риски
- `default_code_sha` читает `store.task_branch` — для задач self/артели,
  заведённых до T045 (собственный worktree), либо в песочницах без
  реального git, `gitcmd.branch_head_sha` штатно вернёт пустую строку
  (ветки нет физически) — тот же вырожденный откат, что уже существует
  у `external_code_sha`/`external_artifact_sha`.

## Предложения системе
(пусто)
