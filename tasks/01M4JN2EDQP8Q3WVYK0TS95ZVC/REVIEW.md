---
task: 01M4JN2EDQP8Q3WVYK0TS95ZVC
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Сетевые адреса в tests/ — пульт ловит до CI

## Фаза A: план
- Покрытие требований полное (1 → шаги 1, 4; 2 → 1; 3 → 2, 3; 4 → 1).
- Шаги проверяемые, размер нормальный. Приложение к защищённому
  `tests/test_invariants.py` применяется: `git apply --check` проходит на
  чистом дереве, проверено мной.
- Подход в целом архитектуре соответствует. Одно расхождение: пункт
  «Влияние на систему» — «Канарейка и внешние проекты не затронуты» —
  верен только для рубежа `in_dev`. Для выхода из `tests_writing` и для
  `amend-tests` он неверен, см. R1-F1.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Правило перенесено в `scripts/guard.py:2798-2861` дословно. Приложение убирает копию из инварианта и не меняет утверждения: `assertEqual({}, offenders)` и `assertEqual([url], hits)` остались прежними. Я накладывал приложение временно — инвариант и долгоживущий файл зелёные. |
| 2 | Реализовано шире заказанного | Признак добавлен в `long_lived_errors_from_files` (`guard.py:2787`), отказ — `TEST_GROUPS_ACTION`/`LONG_LIVED_ACTION`, в тексте есть файл:строка. Но правило не ограничено артелью — см. R1-F1. |
| 3 | OK | `_network_address_gate` (`tests_writing.py:66-111`) берёт файлы `tests/**/*.py` только из диффа против `diff_base`. Удаления пропускаются, при переименовании читается новый путь, сбой git — отказ (fail-closed). Вызов стоит в `in_dev` до `_origin_push_gate` (`fsm_advance.py:658-662`). |
| 4 | OK | Четыре пары перенесены побайтно, хост сравнивается точно. Подтверждено AC-5/AC-6 долгоживущего файла и планки. |

## Замечания
- major — `scripts/guard.py:2787` (через `long_lived_errors_from_files`;
  потребители — `orchestrator/advance_gates/tests_writing.py:334`,
  `:450` и `orchestrator/amend.py:500`). Правило инварианта 35 —
  правило дерева `tests/` самого пульта: так прямо пишет докстринг
  `_network_address_gate` (`tests_writing.py:76-77`, «в чужом репозитории
  `tests/` значит другое»), и рубеж `in_dev` поэтому чужие проекты
  пропускает. Но тот же признак, добавленный в
  `long_lived_errors_from_files`, действует для любого проекта с профилем
  тестов: `_tests_writing_test_groups_gate`/`_tests_writing_long_lived_gate`
  работают для «любого проекта с профилем» (`tests_writing.py:316`,
  `fsm_advance.py:465-468`), то же касается `amend-tests`.
  Сценарий: внешний проект, долгоживущий тест мокает HTTP-клиент со
  строкой `https://api.stripe.com/v1`. Выход из `tests_writing` отказывает
  с текстом «в tests/ адреса только на localhost/127.0.0.1
  (инвариант 35)», хотя инвариант 35 к этому проекту не относится. Выхода
  у роли нет: именованные исключения ключуются именами файлов пульта.
  Воспроизведено:
  `guard.long_lived_errors_from_files([('spec/test_01abc_client.py', …)], '01ABC')`
  возвращает эту ошибку. Получается, что одно правило на двух рубежах
  ведёт себя по-разному, а «Влияние на систему» в PLAN описывает это
  неверно.
  Предложение: ограничить признак адресов на выходе из `tests_writing`
  артелью (`repo_context.is_artel(target)`), тем же условием, что у
  рубежа `in_dev`. Например, именованным параметром
  `long_lived_errors_from_files(..., network_addresses=True)`: так
  зафиксированный долгоживущий файл, который зовёт функцию без
  параметра, остаётся зелёным, а `tests_writing` передаёт признак
  артели. Остаток в `amend.py` (файл только для чтения) назвать в PLAN.
  Если же правило для чужих проектов задумано, это расширение SPEC:
  эскалируй вопросом Оператору и исправь «Влияние на систему».
- minor — `orchestrator/advance_gates/tests_writing.py:60`. Действие
  отказа `NETWORK_ADDRESS_ACTION = "переход отклонён"` общее, без
  суффикса: в журнале этот отказ отличает только `detail`. Это осознанный
  компромисс (PLAN, «Риски»; `refusal_classes.py` вне зон), предложение
  записано в «Предложения системе». Сейчас не исправлять.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | scripts/guard.py:2787 (потребители tests_writing.py:334, :450; amend.py:500) | Признак адресов инварианта 35 в `long_lived_errors_from_files` действует для любого проекта с профилем, а рубеж `in_dev` — только для артели | Выход из `tests_writing` (и `amend-tests`) внешнего проекта отказывает долгоживущему тесту с мокнутым DNS-адресом со ссылкой на неприменимый инвариант 35, обхода у роли нет; «Влияние на систему» в PLAN неверно | Ограничить признак артелью на выходе из `tests_writing` (параметр с умолчанием True, `tests_writing` передаёт `is_artel(target)`), остаток в amend.py описать в PLAN; либо эскалировать, если правило для чужих проектов задумано |
| R1-F2 | open | orchestrator/advance_gates/tests_writing.py:60 | Отказ рубежа адресов — общее «переход отклонён» без суффикса | В журнале отказ отличает только `detail` (minor, компромисс из-за зон) | Оставить как есть, отметить `rejected` со ссылкой на «Риски» PLAN; своё действие — отдельной задачей через `refusal_classes.py` |

## Вердикт
changes_requested — исправить R1-F1: ограничить признак адресов на
выходе из `tests_writing` артелью или эскалировать вопрос о чужих
проектах, и привести «Влияние на систему» в PLAN в соответствие с
кодом. R1-F2 — minor, разметить на усмотрение разработчика.

## Проверено исполнением
- `python3 -m pytest -q tests/test_network_address_gate.py tests/test_01m4jn2edqp8q3wvyk0ts95zvc_network_address.py tests/test_fsm_advance_gate_smoke.py tests/test_long_lived_transitions.py tests/test_refusal_classes.py tests/test_amend.py`
  — 61 passed, 60 subtests passed.
- `artel.py plank-run 01M4JN2EDQP8Q3WVYK0TS95ZVC` — 5 passed, код выхода
  pytest 0.
- Приложение 1 из PLAN извлечено и наложено временно: `git apply` проходит.
  `pytest tests/test_invariants.py tests/test_01m4jn2edqp8q3wvyk0ts95zvc_network_address.py -k "NoNetworkAddresses or NetworkAddressRule"`
  — 7 passed, 33 subtests passed. После этого `git checkout --
  tests/test_invariants.py`, дерево чистое.
- Временная мутация: в `_network_address_gate` при `text is None` —
  `continue` вместо отказа. Красный
  `test_git_not_answering_diff_or_show_refuses`, заявка подтверждена.
  Код возвращён `git checkout`.
- Воспроизведение R1-F1: `guard.long_lived_errors_from_files` с меткой
  `spec/test_01abc_client.py` и адресом `https://api.stripe.com/v1`
  возвращает ошибку «… (инвариант 35)».
- `python3 scripts/codebase_map.py`: карта отличается только строкой
  `built_at_sha` — свежая. Изменение откатил.

## Предложения системе
- Класс «правило, привязанное к пульту, положено в общий узел
  `guard.long_lived_errors_from_files`, которым пользуются все проекты с
  профилем». Перед добавлением признака в этот узел стоит проверять,
  относится ли он ко всем проектам. Адрес: `scripts/guard.py`,
  `skills/review-checklist.md` (фаза B, пункт «Системная целостность»).
