---
task: 01M3NMHHAMTFN2BNKBN209E15M
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Трассируемость AC видит долгоживущие файлы test_author в tests/ кодовой ветки (исправление 01M3N3Z1)

## Фаза A — план

- Покрытие: таблица PLAN закрывает требования 1–4. Требование 1 закрыто так:
  анализ показал, что связка «чекпоинт → чтение кодовой ветки» на a4cf36bb
  исправна, это доказывает новый сквозной тест. Канарейка упала, потому что
  исполняла код пина 171ab4c6 при скилах целевого sha. Разработчик честно
  называет сдвиг пина действием Оператора вне роли. Проверил по git:
  `git merge-base --is-ancestor ef9149b7 171ab4c6` → exit 1 (мержа
  01M3N3Z1 в 171ab4c6 нет). `git grep` на 171ab4c6: `checkpoint.py:488
  if role != "developer":` (дефект А) и `fsm_advance.py:329
  fsm._tests_writing_ac_state(conn, task_id, branch, tdir)` без
  `long_lived_sources` (дефект Б). Места совпадают с PLAN.
  Что именно 171ab4c6 — пин боевого пульта, из рабочего каталога шага
  проверить нельзя. Этот факт взят из PLAN/диагностики.
- Шаги имеют размер MR и проверяемы. Подход не противоречит конвенциям: в
  код связки ничего не добавлено ради «лечения» уже рабочего пути.
  Добавлена только видимость тихих выходов.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | На HEAD оба варианта (а)/(б) проходят в `in_dev` без отказа трассируемости (сквозной тест зелёный). Дефекты А/Б воспроизводятся мутациями, повторяющими код пина: см. «Проверено исполнением». Исправление для боевого пульта — сдвиг пина, вне роли; в PLAN это названо в «Рисках». Тихие выходы `_test_author_checkpoint` теперь пишут `TEST_AUTHOR_NOT_COMMITTED_ACTION` (`orchestrator/checkpoint.py:292-299`, `:309-315`) |
| 2 | OK | Перечень пишется в том же `advance`: тест сверяет строку `<sha256 байтов головы>␣␣<путь>` в ветке документов и запись «перечень долгоживущих тестов записан». Гейты не тронуты: в диффе нет правки `fsm_advance.py`/`advance_gates/`, а `test_long_lived_manifest.py`/`test_long_lived_transitions.py` зелёные |
| 3 | OK | `tests/test_long_lived_step_end_to_end.py` — на `tests/sandbox.py` (`FakeProc`, `is_claude_call`), подменён только `runner.spawn_agent`. Оба варианта AC-1 и сценарий без префикса есть |
| 4 | OK | SPEC «Контекст» описывает оба дефекта, PLAN «Причина отказа…» называет место каждого и подтверждает его мутацией |
| AC-1..AC-5 | OK | Планка 13/13 зелёная. Заявка AC-4 в докстринге дословная |
| AC-6 | OK | Оба места названы. Подтверждение мутациями повторил сам (см. ниже) |

Тесты: у всех четырёх новых методов есть «Ловит мутацию: …» с наблюдаемым
расхождением (состояние, отказ в журнале, запись в журнале), и каждую
заявку я проверил временной мутацией. Дифф `tests/` только добавляет новый
файл, существующие ассерты не тронуты. Группы планки: все три файла
помечены «разовый». Для `test_ac1_ac3_*` это обосновано в докстринге:
опора на приватные гейты и `RealPultGitTest`, а долгоживущий сторож
свойства — новый файл в `tests/`. Пометок `manual`/`skip` нет. Защищённые
пути (`skills/`, `templates/`, `.github/`, `gates.yaml`, `roles.yaml`) не
тронуты. Раздел «Влияние на систему» совпадает с диффом (2 файла). Откат
делается revert.

## Замечания

Блокирующих и major-замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest -q tests/test_long_lived_step_end_to_end.py tasks/01M3NMHHAMTFN2BNKBN209E15M/acceptance_tests`: 13 passed, 14 subtests passed (78 с).
- `python3 -m pytest -q tests/test_long_lived_manifest.py tests/test_long_lived_transitions.py tests/test_timeout_checkpoint.py tests/test_step_autocommit.py tests/test_checkpoint_zone_filter.py`: 79 passed, 20 subtests passed.
- Временные мутации (через `mock.patch` в `python3 -c`, файлы кода не правились):
  - дефект Б: `fsm._tests_writing_ac_state` с `long_lived_sources=[]` →
    `test_prefixed_file_counts_after_checkpoint_and_advance` 2 failures
    (оба варианта (а) и (б)).
  - дефект А: `checkpoint._test_author_checkpoint` → `''` (поведение пина
    «только developer») → тот же тест, 1 failure (вариант (а)).
  - правило имени без префикса: `scripts.guard.is_long_lived_test_path`
    принимает любой `tests/test_*.py` → `test_unprefixed_file_keeps_tests_writing`
    2 failures.
  - тихие выходы: `store.journal` пропускает `TEST_AUTHOR_NOT_COMMITTED_ACTION` →
    `TestAuthorCheckpointNotCommittedJournalTest` 2/2 failures.
- `python3 scripts/codebase_map.py`: дифф карты только в `built_at_sha`, по
  содержимому карта свежая. Регенерированный файл возвращён
  `git checkout -- docs/codebase-map.md`.
- Pin-анализ: `git merge-base --is-ancestor ef9149b7 171ab4c6` → exit 1;
  `git grep` на 171ab4c6 по местам дефектов А/Б — совпадают с PLAN.

Наблюдение не для реестра, к мержу не блокирует. Текст второй записи
журнала (`orchestrator/checkpoint.py:313-314`, «git не принял коммит»)
пишется на любой `committed=False` из `_commit_worktree_change`. Среди
таких случаев — «нечего коммитить» и снятие путей фильтром зон. Для путей
`tests/` из `own` (`tests/` входит в `config.COMMON_ZONES`, `own` непуст)
оба случая практически недостижимы, поэтому формулировка точна на реальных
входах.

## Предложения системе

- Скил review-checklist (раздел «Реестр замечаний») и гейт `review ->
  verifying`: любое заведённое minor-замечание блокирует `approved` до
  следующей итерации. На практике это толкает ревьювера либо не заносить
  minor в реестр, либо тратить итерацию на вкусовщину. Стоит разрешить
  minor в статусе `open` при `approved` либо ввести статус `advisory`.
- `orchestrator/canary.py` / `orchestrator/brief.py`: поддерживаю
  предложение PLAN — канарейка на `target_sha` исполняет код пина со
  скилами клона. Задача целиком оплачена этой несогласованностью.
