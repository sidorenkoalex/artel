---
task: 01M29BANMM8X8JWJ5GDTJWKB0Z
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/role_prompt.py, tests/
budget_usd: 25
---

# SPEC: прогоны тестов ролями и шаг CI на минимальной версии Python — через pytest с таймаутом, тем же раннером, что у пульта

## Контекст
Пульт принимает планку задачи и полный набор `tests/` через pytest
(`orchestrator/acceptance.py::_pytest_command`, `-p timeout`,
`timeout=stack.PER_TEST_TIMEOUT_SEC`), но роль test_author до сих пор
инструктирована гонять приёмочные тесты через unittest
(`orchestrator/role_prompt.py`, миссия test_author, пункт 5;
`skills/test-authoring.md`; `skills/coding-standards.md`) — без таймаута
на отдельный тест. Тот же разнобой держит шаг CI «tests.test_invariants
на минимальной объявленной версии Python» (`.github/workflows/ci.yml`):
он идёт через unittest, без установки `requirements.lock` для этого
интерпретатора, и не покрыт `timeout-minutes` задания — зависший тест
держит раннер до общего лимита GitHub. В `docs/operator-session.md:193`
уже зафиксирован случай зависания прогона через unittest на $35 частичной
стоимости — pytest-timeout эту категорию сбоя ловит. Решение Оператора
12.09: одна задача на оба хвоста — инструкции ролям (код) и шаг CI
(приложение к PLAN, защищённый путь).

## Требования

1. `orchestrator/role_prompt.py`: пункт 5 миссии test_author вместо
   `python3 -m unittest discover -s <task_ref>/acceptance_tests` даёт
   команду pytest той же формы, что `acceptance._pytest_command`:
   `python3 -m pytest <task_ref>/acceptance_tests -p no:cacheprovider -p
   timeout -o timeout=<stack.PER_TEST_TIMEOUT_SEC>`, значение таймаута
   подставляется из константы `stack.PER_TEST_TIMEOUT_SEC`, не литералом;
   остальной текст пункта (про автокоммит, про неприкосновенность кода и
   SPEC.md) — без изменений.
2. Приложение к PLAN.md (unified-дифф, защищённый путь, коммит
   Оператора): в `.github/workflows/ci.yml` шаг «tests.test_invariants на
   минимальной объявленной версии Python» перед прогоном ставит
   зависимости `python3 -m pip install -r requirements.lock` для нового
   интерпретатора и запускает `python3 -m pytest tests/test_invariants.py
   -p no:cacheprovider -p timeout -o timeout=120` (литерал 120 дублирует
   `stack.PER_TEST_TIMEOUT_SEC` с тем же комментарием об известном
   ограничении, что у основного шага); заданию `python` добавляется
   `timeout-minutes: 40` с комментарием, что это страховка от зависшего
   раннера, а не рабочий ориентир.
3. То же приложение: `skills/test-authoring.md` раздел «Перед
   завершением» и `skills/coding-standards.md` раздел «Тесты» вместо
   команд unittest дают команды pytest той же формы
   (`python3 -m pytest tasks/<id>/acceptance_tests -p no:cacheprovider -p
   timeout -o timeout=120` и `python3 -m pytest tests/test_<модуль>.py -p
   no:cacheprovider -p timeout -o timeout=120` соответственно), с одной
   фразой, что это тот же раннер и таймаут, которыми пульт принимает
   планку; слова «в переднем плане с таймаутом» сохраняются в обоих
   файлах.
4. Тесты в `tests/`: миссия test_author (`role_prompt.mission_brief_package`
   или функция, собирающая пункт 5) содержит `-m pytest`, `-p timeout` и
   `timeout=<PER_TEST_TIMEOUT_SEC>`, и не содержит `unittest discover`;
   проверка читает значение таймаута из константы
   `stack.PER_TEST_TIMEOUT_SEC`, а не заносит литерал — при подмене
   константы на другое значение тест остаётся красным до
   соответствующей правки миссии; существующие тесты role_prompt — без
   ослабления.

## Критерии приёмки

AC-1. Пункт 5 миссии test_author в `orchestrator/role_prompt.py` задаёт
команду `python3 -m pytest <task_ref>/acceptance_tests -p no:cacheprovider
-p timeout -o timeout=<значение stack.PER_TEST_TIMEOUT_SEC>`, где значение
таймаута подставлено из константы `stack.PER_TEST_TIMEOUT_SEC`, а не
записано литералом.

AC-2. Остальной текст пункта 5 миссии test_author (упоминания
автокоммита, неприкосновенности кода и SPEC.md) не изменился относительно
текущей формулировки.

AC-3. Тест в `tests/` проверяет, что собранная миссия test_author
содержит подстроки `-m pytest`, `-p timeout` и `timeout=` со значением
`stack.PER_TEST_TIMEOUT_SEC`, и не содержит подстроку `unittest discover`;
тест берёт таймаут из константы, а не из литерала 120 — при подмене
`stack.PER_TEST_TIMEOUT_SEC` на другое значение в тесте тест остаётся
красным, если миссия не подставляет константу.

AC-4. Существующие тесты `orchestrator/role_prompt.py` (включая тесты
брифа/миссии test_author) не ослаблены: ни одна прежняя проверка не
удалена и не смягчена этой задачей.

AC-5. Приложение к PLAN.md — unified-дифф по `.github/workflows/ci.yml`:
шаг «tests.test_invariants на минимальной объявленной версии Python»
перед прогоном ставит `python3 -m pip install -r requirements.lock` для
интерпретатора минимальной версии и запускает
`python3 -m pytest tests/test_invariants.py -p no:cacheprovider -p
timeout -o timeout=120` (литерал 120 — с тем же комментарием об известном
ограничении дублирования константы, что несёт основной шаг).

AC-6. Тот же дифф добавляет заданию `python` в `.github/workflows/ci.yml`
`timeout-minutes: 40` с комментарием, что это страховка от зависшего
раннера, а не рабочий ориентир.

AC-7. Тот же дифф правит `skills/test-authoring.md` раздел «Перед
завершением» и `skills/coding-standards.md` раздел «Тесты»: команды
unittest заменены на pytest той же формы
(`python3 -m pytest tasks/<id>/acceptance_tests -p no:cacheprovider -p
timeout -o timeout=120` и `python3 -m pytest tests/test_<модуль>.py -p
no:cacheprovider -p timeout -o timeout=120` соответственно), с фразой, что
это тот же раннер и таймаут, которыми пульт принимает планку; слова «в
переднем плане с таймаутом» сохранены в обоих файлах.

## Не входит

- Перевод прогонов пульта (`orchestrator/acceptance.py`) на pytest — уже
  сделан.
- Параллель pytest-xdist для шага на минимальной версии Python (один
  файл, не нужна).
- Правка `docs/operator-session.md`.
- Изменение `requirements.lock` и `orchestrator/stack.py`.
- Переименование или перенос `tests/test_invariants.py`.

## Материалы

- `orchestrator/acceptance.py::_pytest_command` (форма команды pytest,
  строки 19–38), `orchestrator/stack.py:77` (`PER_TEST_TIMEOUT_SEC = 120`).
- `.github/workflows/ci.yml:215` (основной прогон pytest-xdist),
  `.github/workflows/ci.yml:236` (шаг на минимальной версии, сейчас
  unittest).
- `orchestrator/role_prompt.py:63–64` (текущая команда unittest discover
  в миссии test_author).
- `skills/test-authoring.md:151`, `skills/coding-standards.md:78–79`
  (текущие команды unittest).
- `docs/operator-session.md:193` (инцидент зависшего прогона на $35).
