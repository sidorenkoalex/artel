---
task: 01M42PENCS26D0656X8FR7DFA7
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: ADR-0021, этап 2 — клон и рабочие копии задач в области проекта; главная копия пульта перестаёт меняться

## Фаза A: план
- Таблица покрытия полна: требования 1–10 привязаны к шагам. В PLAN добавлен раздел «Возврат из ревью, итерация 1» с ответом на каждую запись реестра.
- Новый раздел «Вызовы с явным `repo=config.ROOT`» перечисляет все 7 явных обращений к главной копии и обосновывает каждое. Каждое — чтение версии пульта, легаси `tasks/`, линия после fetch пульта или историческая ссылка. Поиск `grep -rn 'repo=config.ROOT\|repo=doctor.config.ROOT' orchestrator` дал 7 строк, все есть в таблице.
- «Влияние на систему» теперь называет перевод `pin-update`/`doctor main-ci` на главную копию и новые отказы гейтов приёмки и `tests_writing`. Это совпадает с инкрементальным diff: 6 модулей `orchestrator/` и 3 файла `tests/`.
- Приложения 1 и 2 применяются: `git apply --check` на текущем дереве — код 0 у обоих. С ce5e28ea файлы `docs/invariants.md` и `tests/test_invariants.py` не менялись.
- В «Рисках» осталась устаревшая фраза о прогоне «когда приложений было три». Её смысл раскрыт тут же, поэтому это не замечание.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1. Отказ `ensure` для внешнего проекта больше не глотается, отката на каталог без кода нет (R1-F3) |
| 2 | OK | AC-4 зелёный (долгоживущий `test_…_project_area.py`) |
| 3 | OK | AC-5 зелёный |
| 4 | OK | Детектор AC-8 зелёный. Явные обращения к главной копии перечислены и обоснованы в PLAN (R1-F2) |
| 5 | OK | AC-9 и AC-10 зелёные |
| 6 | OK | AC-11 зелёный |
| 7 | OK | `canary._build_artel_project_area` |
| 8 | OK | AC-13 зелёный |
| 9 | OK | Приложения применяются (`git apply --check` — код 0) |
| 10 | OK | Новые тесты несут заявки. Каждая заявка проверена временной мутацией, все тесты красные на ней (см. ниже). Изменённый `test_docs_dir_layout.py` подменяет `ensure` под новое поведение, утверждения те же |
| Побочный эффект R1-F1 | OK | `pin.py` и `doctor/main_ci.py` читают линию в `config.ROOT`, куда сделан fetch |

## Замечания

Новых замечаний нет. Блокеров и major нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/ci.py:650; orchestrator/pin.py:81; orchestrator/doctor/main_ci.py:30 | Линия `main` читалась в клоне артели, а fetch был в главную копию | Ложный исход `pin-update`/`doctor main-ci` | Исправлено: `repo=config.ROOT` в `pin._refuse_unless_main_ci_green` и `doctor.check_main_ci`. Сторож `tests/test_main_ci_fetched_repo.py` держит главную копию и клон раздельно. Временная мутация (снят `repo=` в обоих местах) красит оба метода, код возвращён |
| R1-F2 | accepted | orchestrator/brief.py:260,295,412,443; orchestrator/cleanup.py:21,34,58 | Явные вызовы по главной копии вне перечня треб. 4 | Необъявленные обращения к главной копии | Все вызовы перечислены и обоснованы в PLAN. Все, кроме отката карты брифа, только читают. Откат карты брифа — прежнее поведение (T028): ветки, ссылки, HEAD и worktree он не меняет, инвариант 40 держится. Перенос меняет утверждение защищённого поведения, поэтому вынесен в «Предложения системе». Обоснование принято |
| R1-F3 | accepted | orchestrator/advance_gates/acceptance.py:247; orchestrator/advance_gates/tests_writing.py:152; orchestrator/fsm_advance.py:194 | Ошибка `workspace.ensure` игнорировалась | Прогон планки без кода | Исправлено во всех трёх местах: отказ «приёмочные тесты» с причиной; гейт `_tests_writing_code_copy_gate` до сухого сбора; журнал «автогейт приёмки пропущен». Сторож `tests/test_external_code_copy_refusal.py`. Временная мутация (условия → `False`, гейт снят из списка) красит все 3 метода |
| R1-F4 | accepted | orchestrator/ci.py:60-67 | `_repo_kwargs` подогнан под заглушки тестов | Лишняя развилка | Отклонение принято. Защищённый `tests/test_invariants.py:309` подменяет `head_sha` формой `lambda branch:`, поэтому безусловный `repo=` сломал бы инвариант 19 без приложения. После R1-F1 главная копия передаётся явно, и умолчание совпадает с клоном артели, так что развилка ничего не прячет. Снятие развилки — в «Предложения системе» |

## Вердикт
approved. Все записи реестра R1-F1..R1-F4 в статусе `accepted`. Новых замечаний blocker/major нет.

## Проверено исполнением
- `python3 -m pytest -q tests/test_main_ci_fetched_repo.py tests/test_external_code_copy_refusal.py tests/test_docs_dir_layout.py tests/test_pin.py tests/test_main_ci_line.py` — 42 passed. Упали 3: `FixesMainArgTest` (1 failed и 2 subtests). Причина — сторож роли «artel.py approve: команда недоступна процессу роли reviewer», это известный класс, он описан в PLAN «Риски».
- Временная мутация четырёх мест сразу: снят `repo=` в `pin.py` и `doctor/main_ci.py`; `if error is not None` → `if False` в `advance_gates/acceptance.py` и `fsm_advance._review_approved`; гейт `_tests_writing_code_copy_gate` убран из `tests_writing`. Затем прогон `tests/test_main_ci_fetched_repo.py tests/test_external_code_copy_refusal.py` — 5 failed из 5. Код возвращён `git checkout -- orchestrator`, `git status` чистый.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M42PENCS26D0656X8FR7DFA7` — 9 passed, код выхода pytest 0.
- `python3 -m pytest -q tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py tests/test_fsm_advance_tests_writing*.py tests/test_acceptance_tests_flow.py` — 130 passed, 15 subtests passed.
- `git apply --check` обоих приложений PLAN (извлечены из PLAN.md) — код 0 у обоих.
- Полный набор `tests/` не запускал — по правилу. CI коммита 4a44f54c зелёный (16 проверок).

## Предложения системе
- Сторож роли (`artel._refuse_if_role_restricted`) красит в шаге ревьювера тесты, которые зовут `approve` через `artel.main` (`tests/test_main_ci_line.py::FixesMainArgTest`). Каждая роль заново доказывает, что эти падения — «известные красные». Стоит снимать `ARTEL_ROLE` в песочнице `tests/sandbox.py`: разработчик это тоже предлагал.
