---
task: 01M1SHK3MD4ZF9NYXSCT67J8AP
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: пульт не зависит от профиля оболочки — самовыбор интерпретатора при старте

## Фаза A: проверка плана

1. Покрытие требований — таблица PLAN.md полна: все 8 требований SPEC
   сведены к шагам 1-2, включая требование 6 (проверено отсутствием
   правок `agent_log.py`) и требование 2 (проверено фактическим AST-
   разбором `stack.py`/`config.py`, не декларативно).
2. Размер шагов — оба шага MR-размера, не микрооперации: шаг 1
   (точка входа + правка аннотации + тесты) и шаг 2 (доп. строка
   `_python_check`) — проверяемые единицы.
3. Подход не конфликтует с конвенциями: top-level проверка версии до
   рискового импорта — единственный способ перехватить крах при всех
   трёх способах запуска (`python3 artel.py`, `python3 -m
   orchestrator.artel`, простой импорт), обоснование в PLAN корректно
   и подтверждено чтением кода (см. ниже).

Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_ensure_supported_interpreter()` — top-level вызов (`orchestrator/artel.py:416`) СТРОГО до `from orchestrator import (amend, ..., doctor, ...)` (:419); AST-тест `Ac1...` в приёмочной планке подтверждает отсутствие `X|None`/`match` до этой точки — прогнан, зелёный. |
| 2 | OK | `REQUIRED_PYTHON` читается прямым импортом `orchestrator.stack` (`artel.py:346`); `stack.py`/`config.py` подтверждённо 3.9-совместимы (`Path | None` → `Optional[Path]`, `stack.py:211`); транзитивные импорты обоих модулей — только stdlib + друг друга (проверено `ast`-обходом вручную), риска протащить `doctor` нет. |
| 3 | OK | Старый интерпретатор + пригодный `.artel/venv/bin/python` + маркера нет → `os.execv` тем же путём, `sys.argv[0]` + `sys.argv[1:]` в хвосте, маркер добавлен в `os.environ` (не построен заново — `os.execv`, не `execve`, наследует текущее окружение процесса). |
| 4 | OK | venv нет/непригоден → именованный отказ одной строкой (версия, `sys.executable`, `venv-sync`), код выхода 2. |
| 5 | OK | Маркер уже стоит — проверяется РАНЬШЕ проверки venv (`artel.py:407-409`), отказ без повторного `execv`, даже если venv пригоден. |
| 6 | OK | Современный интерпретатор — без `os.execv`; `agent_log.py` не тронут вовсе (0 строк в diff); ручной прогон `python3 orchestrator/artel.py status` и `python3 -m orchestrator.artel status` — оба доходят до существующего отказа инварианта T056 (git-worktree), поведение не изменилось. |
| 7 | OK | `stack._interpreter_provenance_text()` добавляет строку `sys.executable`+наличие `.artel/venv` в `detail` проверки `python`, статус (ok/warn) остаётся функцией только версии — подтверждено и тестом (`PythonCheckProvenanceTest`), и ручным прогоном `stack.check_stack()` в реальном (не замоканном) окружении. |
| 8 | OK | `tests/test_artel_bootstrap.py` + `tasks/.../acceptance_tests/test_python_bootstrap.py` покрывают все перечисленные исходы; `tests/test_stack.py`/`tests/test_doctor.py` зелёные без изменения статусов существующих проверок. |

## Замечания

Пусто — блокеров и major-замечаний не найдено.

Одно наблюдение вкуса (не формализую как замечание, см. «Предложения
системе» ниже): пять новых тестовых методов в `tests/test_artel_bootstrap.py`
(`RequiredPythonReadFromStackTest`, `OldInterpreterWithUsableVenvTest`,
`OldInterpreterWithoutUsableVenvTest`, `ReexecMarkerAlreadySetTest`,
`ModernInterpreterPassthroughTest`) не несут буквальной строки «Ловит
мутацию: …» в докстринге (в отличие от новых тестов того же коммита в
`tests/test_stack.py::PythonCheckProvenanceTest`, где тег есть). По
существу докстринги описывают сценарий и наблюдаемое свойство, и по
чтении кода заявленная мутация правдоподобна и ловится — содержательного
дефекта нет, поэтому не блокирую.

## Реестр замечаний

Пусто — замечаний в этой итерации не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_artel_bootstrap tests.test_stack tests.test_doctor -v` — 147 тестов, все зелёные (включая новые `PythonCheckProvenanceTest`, все классы `tests/test_artel_bootstrap.py`, и весь существующий `test_doctor.py`/`test_stack.py` без регрессий).
- `python3 -m pytest tasks/01M1SHK3MD4ZF9NYXSCT67J8AP/acceptance_tests/test_python_bootstrap.py -v` — 14 приёмочных тестов (AC-1..AC-9), все зелёные.
- `python3 scripts/codebase_map.py` — регенерация карты дала диф только в строке `built_at_sha` (`git diff --stat docs/codebase-map.md` → 1 insertion, 1 deletion), т.е. карта в ветке уже актуальна по содержимому.
- `python3 orchestrator/artel.py status` и `python3 -m orchestrator.artel status` (реальный интерпретатор 3.13, без моков) — оба способа запуска проходят проверку версии без `os.execv` и доходят до существующего отказа инварианта T056 («git-worktree, не главная копия»), т.е. поведение для современного интерпретатора не изменилось (требование 6).
- Ручной прогон `stack.check_stack()` в реальном (не замоканном) окружении: проверка `python` вернула `status="ok"` со строкой `Python 3.13.12; запущен .../python3, .artel/venv (...) не существует` — подтверждает требование 7 на живых данных, не только на моках теста.
- Проверка zon/diff: `git diff --stat` подтверждает изменения ограничены `orchestrator/artel.py`, `orchestrator/stack.py`, `docs/codebase-map.md` (регенерация картой, обязательна конвенцией), `tests/test_artel_bootstrap.py` (новый), `tests/test_stack.py` — совпадает с зоной SPEC и «Влиянием на систему» PLAN; `orchestrator/doctor.py` не тронут, как и заявлено.
- CI коммита 69ef02b6 (голова ветки) — зелёный, 7 проверок (из ревью-пакета).

## Предложения системе

- `skills/test-authoring.md` формулирует тег докстринга «Ловит мутацию:
  …» как обязательный для приёмочных тестов test_author
  (`acceptance_tests/`), а `skills/review-checklist.md` (п. «Тесты»)
  требует сверять с этим тегом «каждый новый или изменённый тест» —
  формулировка не разграничивает явно, распространяется ли обязательность
  тега на тесты `tests/`, которые пишет сам разработчик (не test_author).
  В этой задаче разработчик применил тег в одном новом файле
  (`tests/test_stack.py::PythonCheckProvenanceTest`) и не применил в
  другом (`tests/test_artel_bootstrap.py`, 5 методов) — область
  действия тега для тестов разработчика стоило бы явно закрыть в
  `test-authoring.md`, чтобы это не решалось каждый раз на усмотрение
  ревьювера.
