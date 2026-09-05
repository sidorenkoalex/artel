---
task: 01M1P9QCHPHSCEA6TK13PV85SP
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 4
---

# REVIEW: Механика зон, часть 3: сверка диффа с зонами при переходе в ревью

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 / AC-1 | OK | `_zones_gate_refuses` (orchestrator/fsm_advance.py:569-626 примерно) — без изменений с итерации 2, `Ac1OutOfZoneDiffRefusesTest` зелёный. |
| 2 / AC-3 | OK | R2-F1 закрыт: `_answer_commit_is_role_step_autocommit` (fsm_advance.py:517-539) отклоняет мандат из ANSWER-файла, чей последний коммит на артефактной ветке — доказанный автокоммит шага роли (`checkpoint.py::own_commit_marker`); подключено в `_answer_zones_mandate` (fsm_advance.py:557-558) ДО чтения текста файла. `AnswerCommitIsRoleStepAutocommitTest` (4 теста) и `AnswerZonesMandateOriginTest` (2 теста) зелёные — см. «Проверено исполнением». |
| 3 / AC-4 | OK | Без изменений с итерации 2. |
| 4 / AC-7 | OK | `git diff main...HEAD -- tests/` этой итерации: единственная правка — 6 новых тестовых методов в уже добавленном `tests/test_zones_gate.py` (298 строк итогом против 208 на итерации 2), ни один существующий файл `tests/*.py` не тронут. |
| AC-2 | OK | Без изменений с итерации 2. |
| AC-5 | OK | Без изменений с итерации 2. |
| AC-6 | OK | Без изменений с итерации 2. |

Единственный blocker прошлой итерации (R2-F1) закрыт содержательно, а не декларативно: разобрал сам фикс, воспроизвёл сценарий эксплойта и его закрытие юнит-тестами (ниже). Остальные требования не менялись с итерации 2, повторно перепроверены прогоном.

## Замечания

- **minor** (перенесено с итерации 2, не в реестре — не блокирует) — `tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/test_ac3_ac7_markers.py` всё ещё дублирует `test_ac7_existing_suite_marker.py` (оба несут идентичную по смыслу пометку `# AC-7: skip`); разработчик не удалил файл после замечания итерации 2. Не аппрув-блокер, повторяю для полноты — удалить при следующей правке этой зоны.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/ | код-ветка несла устаревший снимок приёмочных тестов | — | закрыто итерацией 2, без изменений |
| R1-F2 | accepted | tests/test_zones_gate.py | докстринги «Ловит мутацию:» | — | закрыто итерацией 2, без изменений |
| R2-F1 | accepted | orchestrator/fsm_advance.py:505-539 (`_answer_commit_is_role_step_autocommit`, `_answer_zones_mandate`) | мандат Оператора на расширение зон принимался по ЛЮБОМУ ANSWER-*.md, без проверки происхождения коммита | AC-3 не гарантировал то, что заявляет | подтверждено: `_answer_commit_is_role_step_autocommit` сверяет последний коммит ANSWER-файла на артефактной ветке с префиксом `own_commit_marker` (`checkpoint.py`, общий для любой роли и обеих формулировок — обычной и с пометкой таймаута) и исключает файл из мандата при совпадении, ДО чтения текста; не отвечает git или сообщение не опознано → файл НЕ считается доказанным автокоммитом (fail-safe в сторону легитимного мандата, симметрично тому, как `checkpoint.py` использует тот же признак только как положительное основание для удаления). Разобрал код построчно, прогнал `AnswerCommitIsRoleStepAutocommitTest` (4/4) и `AnswerZonesMandateOriginTest` (2/2) — оба сценария (поддельный мандат из автокоммита шага developer отклоняется; настоящий `cmd_answer` проходит) явно тестами покрыты. Приёмочная планка AC-3 (`_sandbox.py::write_answer_mandate`) не может проверить это различение (лёгкая песочница не моделирует чей коммит принёс файл — тот же документированный вырожденный случай, что был и на итерации 2), поэтому проверка целиком на юнит-уровне — это ожидаемо и достаточно, происхождение проверяется именно там, где оно доступно |

## Вердикт

approved — единственный blocker (R2-F1) закрыт и подтверждён самостоятельным разбором фикса и прогоном новых тестов; реестр закрыт целиком (все записи `accepted`). Остался один minor вне реестра (дубль файла разметки AC-7) — не блокирует.

## Проверено исполнением

- `python3 -m unittest tests.test_zones_gate -v` — 20 тестов, все зелёные (14 с итерации 2 + 6 новых для R2-F1: `AnswerCommitIsRoleStepAutocommitTest`×4, `AnswerZonesMandateOriginTest`×2).
- `python3 -m unittest discover -s tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests -p "test_*.py" -v` — 11 тестов, все зелёные (запуск из код-ветки).
- `python3 -m unittest tests.test_advance_guard tests.test_advance_refusal_history tests.test_capacity_gate tests.test_store_schema_migration_parity tests.test_store_journal tests.test_invariants -v` — 67 тестов, все зелёные (соседние гейты того же перехода `in_dev -> review`, миграция схемы БД, инварианты — не задеты фиксом R2-F1).
- `python3 scripts/codebase_map.py --check` — без вывода/ошибки, карта актуальна.
- `git diff main...task/01m1p9qchphscea6tk13pv85sp-mekhanika-zon-chast-3-sverka-d --stat` и `-- tests/` — сверено: единственное изменение `tests/` веткой целиком — новый файл `tests/test_zones_gate.py` (298 строк), ни один существующий тест не тронут (AC-7); полный diff кода (`orchestrator/fsm_advance.py` 177 строк, `orchestrator/store.py` 7 строк, `docs/invariants.md` 1 строка — новая строка 34 таблицы инвариантов на переход зон) прочитан целиком.
- `git show 58ef73e1493cc9269557659bc1f1f284718b5bdf` — прочитан целиком: единственный коммит-фикс этой итерации (`orchestrator/fsm_advance.py`, `tests/test_zones_gate.py`, `docs/invariants.md`, `docs/codebase-map.md`); инкрементальный diff пакета (58ef73e1...HEAD) нёс только `docs/roadmap.md` от подтяжки main — сверился вручную по `git log -- tasks/.../REVIEW.md` и содержимому артефактной ветки, что фактический фикс лежит именно в этом коммите (см. «Предложения системе»).
- Прочитаны `orchestrator/gitcmd.py::git` (сигнатура вызова `_answer_commit_is_role_step_autocommit`) и `orchestrator/checkpoint.py:497-499` (`own_commit_marker`) — подтверждено дословное совпадение префикса, который сверяет фикс, с тем, что реально пишет автокоммит шага.
- `docs/invariants.md` — строка 34 добавлена фикс-коммитом, закрывает minor итерации 2 про отсутствие гейта зон в таблице инвариантов.

## Предложения системе

- Инкрементальный diff пакета этой итерации (от sha `58ef73e1...`, помеченного как «sha предыдущего вердикта») нёс только `docs/roadmap.md` — сам коммит с фиксом R2-F1 оказался ИСПОЛЬЗОВАН КАК БАЗА диффа, а не показан в нём (тот же класс, что T082/T087, уже отмеченный в скиле `review-checklist`). Разобрался вручную (`git show <sha>` целиком, сверка с историей REVIEW.md артефактной ветки) — стоит проверить, почему sha фикс-коммита разработчика попадает в поле «предыдущий вердикт» пакета вместо коммита самого REVIEW.md итерации 2.
