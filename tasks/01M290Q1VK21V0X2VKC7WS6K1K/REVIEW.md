---
task: 01M290Q1VK21V0X2VKC7WS6K1K
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: note --drop, --set-state, --set-priority — снятие и правка строк копилки/бэклога тем же циклом fetch/правка/push

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`--drop <ключ>`) | OK | `_apply_drop` (orchestrator/notes.py:175-180) снимает ровно одну строку через общий `_find_unique_row` (orchestrator/notes.py:157-163) — ноль/множество совпадений дают `sys.exit` до какой-либо записи в `lines`. Сообщение коммита `_commit_message` (orchestrator/notes.py:228-237, ветка `kind == "drop"`) — «оператор: <раздел> — снята: <первые 80 симв. наблюдения>». Путь `_attempt`/`_hold_pending`/повтор non-fast-forward (orchestrator/notes.py:271-307) не изменён — новый вид проходит тем же циклом. AC-1..AC-4 проверены прогоном `acceptance_tests/test_ac1..ac4` (см. «Проверено исполнением»), все зелёные. |
| 2 (`--set-state`) | OK | `_apply_set_state` (orchestrator/notes.py:183-189) заменяет последнюю колонку целиком (`cells[-1] = text`), не дописывает; `_apply_append` (orchestrator/notes.py:166-172) по-прежнему дописывает (`f"{cells[-1]} {text}".strip()`) — раздельное поведение подтверждено тестами `ApplySetStateTest`/`ApplyAppendTest` (tests/test_notes.py) и `acceptance_tests/test_ac5_set_state_replaces_column.py` (оба класса, включая `AppendStillAppendsSameColumnTest`). Сообщение коммита (orchestrator/notes.py:233-234) соответствует AC-6, подтверждено `test_ac6_set_state_commit_message.py`. |
| 3 (`--set-priority`) | OK | `_apply_set_priority` (orchestrator/notes.py:192-204) валидирует диапазон 1..4 (`int(text)`, `1 <= value <= 4`) ДО чтения/правки строк — отказ вне диапазона (включая нечисловой текст) не меняет `lines` и, соответственно, файл. Колонка «П» — первая ячейка во всех трёх таблицах `docs/backlog.md` (проверено: `| П | Дата | ... |` в разделе «Копилка», `| П | Кандидат | ... |` в «Бэклоге», `| П | Действие | ... |` в «Очереди Оператора» — grep подтверждён), `cells[0] = text` (orchestrator/notes.py:202) — верная колонка. AC-7 подтверждён `test_ac7_set_priority_range.py` (3 теста: replace, above-range, below-range) плюс юнит-тест на нечисловое значение. |
| 4 (общий формат pending, `doctor` без правки) | OK | `_hold_pending`/`pending_notes`/`_pending_paths` (orchestrator/notes.py:65-88) не входят в diff — работают с произвольным `dict`, новые `kind` проходят тем же путём. `orchestrator/doctor/misc_checks.py:35-40` (`check_pending_notes`) читает `doctor.notes.pending_notes()` целиком по длине списка, без ветвления по `kind` — правок `orchestrator/doctor/` в diff нет (`git diff --stat` подтверждён). AC-8 (`test_ac8_pending_all_kinds_ordered_flush.py`) — все пять видов (`insert`/`append`/`drop`/`set-state`/`set-priority`) удерживаются и допушиваются `--flush` в порядке создания — зелёный. |
| 5 (тестовый слой) | OK | `tests/test_notes.py`: новые классы `ApplyDropTest` (изоляция соседних строк — мутация «удаление по индексу без проверки ключа» ловится: тест проверяет, что строки с `ПОВТОРКЛЮЧ` остаются байт-в-байт и другой раздел не задет; отказ при 0 и 2 совпадениях без изменения текста), `ApplySetStateTest` (замена vs дописывание — прямое сравнение с `_apply_append`), `ApplySetPriorityTest` (диапазон 1..4, включая нечисловое значение), 2 новых метода `CmdNoteArgumentValidationTest` (`--set-state`/`--set-priority` без `--text`). Diff `tests/test_notes.py` — только добавления (проверено построчно по diff пакета): ни одна существующая строка/ассерт не удалены и не смягчены — AC-9 выполнено. Полный сценарий git для трёх новых видов закрыт залоченными `acceptance_tests/test_ac1..ac8` (не дублируется юнит-тестами, PLAN это явно оговаривает) — все 17 приёмочных тестов зелёные. `test_ac9_existing_tests_not_weakened.py` — легитимная пометка `manual`: утверждение о диффе будущей правки, которое прогон текущего среза кода в принципе не может проверить (обоснование в докстринге отвечает на «почему тест невозможен», не «сложно/долго»). |

## Замечания

(пусто — 0 blocker/major/minor)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

(пусто — замечаний в этой итерации не заведено)

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_notes -v` — 27 тестов, все `ok` (в т.ч. новые `ApplyDropTest`, `ApplySetStateTest`, `ApplySetPriorityTest`, `CmdNoteArgumentValidationTest.test_set_state_without_text_refuses`/`test_set_priority_without_text_refuses`).
- `python3 -m unittest tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac1_drop_removes_matched_row_only.py tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac2_drop_match_count_refuses.py tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac3_drop_commit_message.py -v` — 6 тестов, ok.
- `python3 -m unittest tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac4_drop_hold_and_flush.py tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac5_set_state_replaces_column.py tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac6_set_state_commit_message.py -v` — 7 тестов, ok.
- `python3 -m unittest tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac7_set_priority_range.py tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/test_ac8_pending_all_kinds_ordered_flush.py -v` — 4 теста, ok. Итого AC-1..AC-8 (17 тестов) зелёные; AC-9 — `manual`, файл без тестовых методов, обоснование в докстринге проверено.
- `grep -n "^| П " docs/backlog.md` — подтверждён порядок колонок всех трёх таблиц («Копилка», «Бэклог», «Очередь Оператора»): «П» — первая колонка везде, «Состояние» — последняя в «Копилке»; соответствует `_apply_set_priority`/`_apply_set_state`.
- `grep -n "pending_notes\|kind" orchestrator/doctor/misc_checks.py` — `check_pending_notes` считает `pending_notes()` по длине списка, без ветвления по `kind`.
- `git diff --stat 2fac2761...task/01m290q1vk21v0x2vkc7ws6k1k-note-drop-set-state-set-priori -- . ':!tasks'` — diff ветки ограничен `docs/codebase-map.md`, `orchestrator/notes.py`, `tests/test_notes.py`; совпадает с описью пакета, посторонних файлов нет.
- Проверка разрешения подтяжки main по ANSWER-1: `git diff 2fac2761:docs/backlog.md a6c38592:docs/backlog.md` — пусто (merge-коммит `a6c38592` взял `docs/backlog.md` из main-стороны `2fac2761` целиком, как предписано). `git diff 2fac2761 a6c38592 -- docs/codebase-map.md` — отличается только строка `built_at_sha` (карта корректно перегенерирована на слитом дереве, публичная поверхность модуля не изменилась). Текущий `origin/main` разошёлся с `a6c38592` дальше (`git merge-base a6c38592 origin/main` = `2fac2761`, 4 новых копилочных коммита после точки слияния) — это последующее движение main уже после подтяжки задачи, не дефект её работы.
- CI коммита `a6c38592` — зелёный, 14 проверок (полный `tests/` в шаге ревью не прогонялся согласно правилу «CI гоняет полный набор»; профильный модуль `tests/test_notes.py` и вся зона задачи прогнаны выше).

## Предложения системе

(пусто)
