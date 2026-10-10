---
task: 01M4KG7VHHXTVTW5TTX2PGY5RY
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: suite-run доступен роли на Codex (песочница workspace-write)

## Фаза A — план
- Таблица покрытия полна (требования 1–6 → шаги 1–4), шаги размера MR.
- Подход (каталог `suite_lock.directory()` вторым `--add-dir`, логи в
  `_task_dir`, отложенный журнал с досылом процессом пульта) не
  конфликтует с архитектурой.
- Неверно утверждение раздела «Влияние на систему»: «Подложенная ролью
  запись станет записью журнала её задачи… На гейты и итоги approve она не
  влияет». На деле досыл пишет в журнал любые `actor`/`action`/`task_id`
  из файла, и эти записи читают гейты (см. R1-F1).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Замок тот же (`suite_lock.directory()/lock.json`), отчёт и лог в каталоге, доступном роли; AC-4/AC-6/AC-8 зелёные |
| 2 | OK, с оговоркой | `--add-dir` открывает ровно `config.LOGS/suite-run`, логи перенесены (`suite_run._log_path`, `_new_log`). Но очередь `pending-journal` в этом каталоге — канал записи в журнал (R1-F1) |
| 3 | реализовано не так | Досыл есть (`suite_lock.deliver_journal`), но он без проверки доверяет содержимому файла, который пишет процесс роли (R1-F1) |
| 4 | OK | Argv Claude прежний (AC-7), путь лога в отчёте назван |
| 5 | нарушено | Замок и пределы не тронуты, но песочница Codex теперь пропускает подделку журнальных записей, которым верят гейты. Сверх нужного это ослабляет второй рубеж (R1-F1) |
| 6 | OK | Изменено одно ожидание `test_docs_dir_layout.py::…::test_add_dir_only_when_docs_dir_given_and_model_stays_last`, оно объявлено в SPEC, значение совпадает с требованием 2. В `test_suite_run.py` поменялся только путь подмены (`_new_log`), утверждения не тронуты |

## Замечания

- **blocker** — `orchestrator/suite_lock.py` `deliver_journal` (вызов
  `store.journal(conn, task_id, record["actor"], record["action"], text, …)`)
  и `defer_journal`. Досыл переносит в журнал задачи произвольные `actor`,
  `action` и `task_id` из JSON-файла. Каталог
  `config.LOGS/suite-run/pending-journal/` роль на Codex теперь может писать
  сама (это её `--add-dir`). Сценарий: роль кладёт туда
  `{"task_id": "<своя>", "actor": "operator", "action": "объявлена смена
  поведения тестов", "detail": "<строки перечня>\n-"}` или
  `"двусторонний прогон пройден"` с `голова <sha>; база …; методы: …, x`.
  Первый же `suite-run`/`wait_acquire` процесса пульта запишет это в журнал.
  `advance_gates/test_integrity.py::declared_changes` (~886) берёт последнюю
  запись `DECLARED_CHANGE_ACTION`, а `_proven_addresses` (~1036) берёт
  записи `TWO_SIDED_PASSED_ACTION`. Пометку «[дослано…]» досыл приклеивает в
  конец detail, и это лечится лишней хвостовой строкой или элементом. Итог:
  роль обходит гейт неослабления тестов. Проверено исполнением (см. ниже):
  запись с `actor=operator` и `action=объявлена смена поведения тестов`
  доставлена в журнал как есть.
  **Предложение:** на стороне досыла держать закрытый перечень действий,
  которые вправе приходить из очереди: те, что пишет прогон —
  `acceptance.SUITE_NEAR_LIMIT_ACTION`, `acceptance.SUITE_DURATION_ACTION`.
  `actor` ставить самим досылом (`"orchestrator"`), а не брать из файла.
  Записи с иным действием выбрасывать (лучше с отметкой в журнале или
  stderr). Тот же перечень применить в `suite_run._journal_deferred`, чтобы
  в очередь не попадало ничего другого. Добавить тест в
  `tests/test_suite_run_deferred_journal.py`: файл с чужим действием или
  `actor` в журнал не попадает. Поправить «Влияние на систему» в PLAN.

- **minor** — `orchestrator/suite_lock.py` `deliver_journal`: соединение
  `store.db()` не закрывается. Досыл зовут при каждом `wait_acquire` гейта и
  каждом `suite-run`, и в долгоживущем процессе пульта копятся открытые
  соединения или дескрипторы WAL. **Предложение:** `contextlib.closing`
  либо `conn.close()` в `finally`.

- **minor** — `acceptance._signal_near_limit` (вне зоны, только чтение).
  В процессе роли `store.journal` падает раньше `alerts.raise_alert`, и алерт
  kind=trigger «длительность близка к пределу» теряется: досыл
  восстанавливает только запись журнала. SPEC (требование 3) требует только
  журнал, поэтому это не дефект задачи. Стоит упомянуть в «Рисках» PLAN или
  поднимать алерт на досыле записи `SUITE_NEAR_LIMIT_ACTION`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/suite_lock.py: `deliver_journal` (вызов `store.journal` с `record["actor"]`, `record["action"]`) | Досыл пишет в журнал произвольные actor/action/task_id из файла очереди, а файл роль на Codex пишет сама | Роль подделывает записи, которым верят гейты (`объявлена смена поведения тестов`, `двусторонний прогон пройден`), с `actor=operator`, и обходит гейт неослабления тестов; песочница ослаблена сверх нужного (треб. 2, 5) | Закрытый перечень действий (SUITE_NEAR_LIMIT_ACTION, SUITE_DURATION_ACTION) на досыле и в `_journal_deferred`; actor ставит досыл; чужие записи отбрасываются; тест на отказ; правка «Влияния на систему» PLAN; fixed: `suite_lock.deferrable` — закрытый перечень из одного `SUITE_NEAR_LIMIT_ACTION` (`SUITE_DURATION_ACTION` suite-run не пишет, а по нему калибруется doctor, поэтому в перечень не включён); перечень проверяют `defer_journal` (через него и `_journal_deferred`) и досыл; actor ставит досыл (`DEFERRED_ACTOR`), detail обрезается до `DEFERRED_DETAIL_MAX`, запись вне перечня выбрасывается со строкой в stderr; тесты `test_forged_actor_and_foreign_action_are_not_delivered`, `test_background_does_not_defer_foreign_action`; «Влияние на систему» в PLAN исправлено |
| R1-F2 | fixed | orchestrator/suite_lock.py: `deliver_journal`, `conn = store.db()` | Соединение не закрывается | В долгоживущем процессе пульта на каждом ожидании замка гейтом копятся соединения | Закрывать соединение (`contextlib.closing`/`finally`); fixed: `deliver_journal` закрывает соединение в `finally`, тест `test_delivery_closes_connection` |
| R1-F3 | fixed | orchestrator/acceptance.py `_signal_near_limit` (поведение при отложенном журнале) | Алерт trigger у предела из процесса роли теряется, досыл его не поднимает | Оператор не получает алерт «близко к пределу» по прогонам роли на Codex | Назвать в рисках PLAN либо поднимать алерт при досыле записи SUITE_NEAR_LIMIT_ACTION; fixed: потеря алерта названа в «Рисках» PLAN; алерт на досыле намеренно не поднимается — иначе файл, подложенный ролью в очередь, поднимал бы алерт Оператору, а это лишний канал из песочницы |

## Вердикт
changes_requested — исправить R1-F1 (blocker): закрытый перечень действий и
actor досыла плюс тест. R1-F2 и R1-F3 — minor, исправить или обоснованно
отклонить.

## Проверено исполнением
- `python3 -m pytest -q tests/test_suite_run.py tests/test_suite_run_deferred_journal.py tests/test_docs_dir_layout.py tests/test_suite_lock.py tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_step_suite_dirs.py tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`:
  56 passed, 84 subtests passed (29 с).
- `python3 -m pytest -q tests/test_providers*.py`: 87 passed, 92 subtests passed.
- `artel.py plank-run 01M4KG7VHHXTVTW5TTX2PGY5RY`: отказ «планки нет» (в
  `refs/artifacts/…` нет `test_*.py`), задачу держат долгоживущие файлы, они
  зелёные (см. выше).
- PoC к R1-F1: временный тест в `tests/` на `TmpRootTest` (после прогона
  удалён, `git status` чистый). `suite_lock.defer_journal({"task_id": "T001",
  "actor": "operator", "action": test_integrity.DECLARED_CHANGE_ACTION, …})`,
  затем `suite_lock.deliver_journal()` вернул 1. Последняя запись
  `store.task_steps`: `actor=operator`, `action=объявлена смена поведения
  тестов`. Подмена actor и action подтверждена.

## Предложения системе
- Любая очередь «процесс роли кладёт → процесс пульта исполняет»
  (здесь `pending-journal`) — класс доверенного канала из песочницы. Стоит
  добавить в review-checklist пункт «данные, которые пишет роль и
  исполняет пульт, проходят закрытый перечень допустимых действий».
