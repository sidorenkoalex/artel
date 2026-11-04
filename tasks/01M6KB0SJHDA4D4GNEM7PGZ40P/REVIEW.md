---
task: 01M6KB0SJHDA4D4GNEM7PGZ40P
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Возврат с гейта SPEC файлом решения

## Фаза A — план
- Таблица покрытия полна: требования 1–12 привязаны к шагам 1–4.
- Шаги размером с MR: модуль разбора, ветка fsm/artel/auto, документация, приложения.
- Подход совпадает с SPEC и с архитектурой: чистый модуль без чтения файлов, `brief` импортируется по месту (через `fsm.spec_gate_prior_decisions`), один `lease.run_task_command`.
- «Влияние на систему» сходится с diff: 8 файлов из зон SPEC; `templates/`, `skills/` в diff нет — они идут только приложениями PLAN. Существующие тесты не правились: `tests/` получил только новый `tests/test_spec_gate_decision.py`.
- Приложения: шаблон с «шестью полями», закрывающие ``` стоят с новой строки. `git apply --check` заявлен на HEAD 724f04683, его применимость проверяет гейт приложений.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `fsm.py` `cmd_reject(..., *, decision_file=None)` — ровно один `run_task_command`, ветвление тернарником внутри лямбды. При `None` тело зовётся `_cmd_reject(conn, tid, reason)` без kwargs. Ключ разбирается явно в `artel._cmd_reject`. Планка AC-10 и оба AST-линтера зелёные |
| 2 | OK | `spec_gate_decision.parse/_fields/_form_problem`: заголовок, раздел, номера подряд с 1 (сверяется и запись номера), метка поля только в начале строки, повтор поля, пустое поле, заглушка раньше формы. `файл:строка` отбрасывает «AC-3:1», «нет:2», «04.11:» и «v1.2:3» (последнее проверено пробой) |
| 3 | OK | `STUBS` зашиты дословно из ТЗ; вложенные «<строка мандата>» и `<id>` заглушкой не считаются (AC-5) |
| 4 | OK | Модуль ничего не читает и не содержит «templates» — AST-тест AC-11 зелёный |
| 5 | OK | `spec_gate_prior_decisions`: номера k.n только у записи, которая проходит `numbered` (заголовок + разбор формы), остальные — k и первые 120 знаков, переносы свёрнуты. Перечень печатают отказ по содержанию и `auto` на `spec_gate` (`auto.py:602`). Отказы чтения и разбора аргументов перечня не печатают. `AUTO_STOP["spec_gate"]` называет `--decision` и сохраняет `approve {id}{sha}` |
| 6 | OK | `prior_refusal`: несуществующий номер, пропущенный номер, «первое решение» при прежних возвратах, нет «противоречий нет»; «№01» ни с чем не совпадает |
| 7 | OK | `mandate_lines` берёт остаток физической строки целиком. `line_elements` вызывается по маркерам мандата тестов на обеих сторонах, мандат не тестов — `ONLY_TESTS`. ANSWER-n читаются лениво с артефактной ветки (`artifact_source.resolve` всегда даёт foreign) |
| 8 | OK | Тот же `store.set_state` с префиксом; бриф не менялся (AC-1) |
| 9 | OK | `_spec_gate_reject_text`: предупреждение у прежней формы; причина с заголовком — отказ до журнала |
| 10 | OK | `artel._cmd_reject`: отказы «без значения» и «с позиционной причиной» — до lease. Отказ «не на spec_gate» стоит до проверки `awaiting_human`. Нечитаемый файл и каталог — `OSError` → отказ |
| 11 | OK | Документы обновлены, справка `artel.py:190`, карта содержит новый модуль (15 вхождений) |
| 12 | OK | Три приложения в PLAN по форме |

## Замечания
Blocker/major нет. Ниже наблюдения уровня ниже minor. Код ведёт себя по SPEC, мержу они не мешают, поэтому в реестр не внесены:
- `orchestrator/spec_gate_decision.py:181` (`int(number)` после `isdigit()`): номер «### Решение ²» даёт `ValueError` с трейсбеком, а не именованный отказ. `"²".isdigit()` истинно, `int("²")` бросает исключение — проверено пробой. Состояние не меняется: исключение возникает до `set_state`. Можно заменить проверку на `number.isascii() and number.isdigit()` или на `re.fullmatch(r"\d+", number, re.ASCII)`.
- `tests/test_spec_gate_decision.py::ParseEdgesTest::test_numbered_returns_none_for_text_reason` во второй и третьей проверке частично повторяет долгоживущий `test_ac8_prior_decisions_listed`: запись с заголовком не по форме получает номер «k», запись по форме — «k.n». Новое в нём только то, что функция возвращает `None` на простой текст. Докстринг модуля обещает края, «не покрытые сквозными тестами». Повод сузить тест при следующей правке, сейчас он ничего не ломает.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Реестр пуст: замечаний blocker/major/minor нет, наблюдения выше в реестр не внесены.

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M6KB0SJHDA4D4GNEM7PGZ40P` — 2 passed (`test_ac10_reject_signature.py`), код выхода 0.
- `python3 -m pytest -p no:cacheprovider -p no:xdist -q` по файлам: `tests/test_01m6kb0sjhda4d4gnem7pgz40p_decision_reject.py`, `tests/test_spec_gate_decision.py`, `tests/test_lease_run_task_command.py`, `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`, `tests/test_fsm_spec_gate_reject.py`, `tests/test_spec_audit_gate.py` — 70 passed, 45 subtests passed (441 с).
- `pytest tests/test_auto_cycle.py tests/test_invariants.py -k "spec_gate or reject"` — 6 passed, 111 subtests.
- Проба разбора в `python3 -c`:
  - `parse("### Решение ²")` → `ValueError` (наблюдение выше);
  - `prior_refusal("№1: противоречий нет; первое решение по теме", ["1"])` → отказ;
  - `_has_file_line("см. docs/x.md:12")` → True, `_has_file_line("v1.2:3")` → False.
- Запуск под `-n 6` (xdist) упал на старте воркеров («node down») — к коду задачи это не относится, повторил последовательно.

## Предложения системе
- Запуск `pytest -n` в шаге ревью роняет воркеры xdist на старте («node down: Not properly terminated», 30 воркеров), и последовательный прогон шести файлов стоит 7 минут. Стоит назвать в `review-checklist` рабочую форму параллели или потолок числа файлов.
