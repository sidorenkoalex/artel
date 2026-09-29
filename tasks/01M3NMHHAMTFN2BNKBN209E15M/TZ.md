---
task: 01M3NMHHAMTFN2BNKBN209E15M
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Трассируемость AC видит долгоживущие файлы test_author в tests/ кодовой ветки (исправление 01M3N3Z1)

# ТЗ: Трассируемость AC видит долгоживущие файлы test_author в tests/ кодовой ветки — исправление задачи 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ

Источник: решение Оператора 29.09.2026; красная канарейка 20260929T004220Z
на вершине main a4cf36bb (первый прогон схемы ADR-0020 после мержа задачи
01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ). Пин пульта не сдвинут (171ab4c6) до мержа
этого исправления.

Факты (origin/main a4cf36bb):
- Канареечная задача 01M3N9SNEZSNC2G4X2Y2DGEY4R: test_author по правилу
  `skills/test-authoring.md` записал долгоживущий файл
  `tests/test_01m3n9snezsnc2g4x2y2dgey4r_version_json.py` с префиксом
  задачи. Выход из `tests_writing` трижды отказал: «трассируемость AC —
  AC-1: нет теста и нет пометки … добавь тестовый метод в
  acceptance_tests/» (AC-1, AC-2, …). На четвёртой попытке test_author
  продублировал тесты в `acceptance_tests/`, и переход прошёл. Четыре
  шага test_author — $18.70; прогон — $38.98 при потолке шаблона $25
  (однократный подъём до $50). Диагностика:
  `.artel/canary/20260929T004220Z/01M3N9SNEZSNC2G4X2Y2DGEY4R/` (журнал
  `steps.txt`, логи четырёх шагов test_author).
- Трассируемость на выходе из `tests_writing`:
  `orchestrator/fsm_advance.py::tests_writing` читает долгоживущие файлы
  через `_tests_writing_code_diff` только при
  `gitcmd.branch_exists(t["branch"])`; тексты передаются в
  `orchestrator/fsm.py::_tests_writing_ac_state` как
  `long_lived_sources`. Если кодовой ветки нет или файлы не закоммичены в
  неё к моменту проверки, долгоживущие файлы трассируемость не видит.
  Коммит файлов test_author в кодовую ветку делает
  `orchestrator/checkpoint.py` на чекпоинте шага. Порядок «чекпоинт —
  проверка перехода», существование кодовой ветки в `tests_writing` и
  место чтения (голова ветки против рабочего каталога) — SPEC проверяет
  по коду и по диагностике канарейки и называет причину.
- Тесты задачи 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ (`tests/test_long_lived_manifest.py`,
  `tests/test_long_lived_transitions.py`) проверяют узлы по отдельности;
  сквозного сценария «test_author записал файл → чекпоинт → выход из
  `tests_writing` засчитал покрытие» нет.

Требуется:
1. Долгоживущий файл test_author с префиксом задачи, записанный в `tests/`
   рабочей копии задачи в шаге test_author, засчитывается трассируемостью
   на выходе из `tests_writing` того же шага: критерий, покрытый методом
   `test_ac<n>_…` такого файла, покрыт. Причина прежнего отказа названа в
   SPEC и PLAN.
2. Перечень контрольных сумм (`long_lived.sha256.txt`) пишется для этих
   файлов в том же проходе; гейт «только добавление» и проверки задачи
   01M3N0BWYQ9KHVN41Z4G72706R применяются к ним — поведение, заданное
   задачей 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, не ослабляется.
3. Сквозной тест в `tests/` на песочнице `tests/sandbox.py`: шаг
   test_author (подменённый агент) создаёт долгоживущий файл в `tests/`
   рабочей копии задачи и SPEC с AC, покрытыми только этим файлом; после
   чекпоинта и `advance` задача в `in_dev`, перечень записан, в журнале
   нет отказа трассируемости. Заявка «Ловит мутацию: трассируемость не
   читает долгоживущие файлы кодовой ветки — отказ «нет теста»». Второй
   сценарий: тот же файл без префикса задачи — отказ трассируемости
   остаётся (или отказ гейта «только добавление»), как задано задачей
   01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ.
4. Проверка канарейкой — после мержа, вне задачи (сессия ассистента).

Зоны: orchestrator/fsm_advance.py, orchestrator/fsm.py, orchestrator/checkpoint.py, orchestrator/advance_gates/tests_writing.py, tests/.

Только чтение (не менять): orchestrator/gitcmd.py, orchestrator/canary.py,
orchestrator/acceptance.py, orchestrator/fsm_merge_gate.py,
orchestrator/role_prompt.py, orchestrator/config.py, scripts/guard.py,
skills/, templates/, docs/adr/, docs/invariants.md, tests/test_invariants.py,
.artel/canary/20260929T004220Z/01M3N9SNEZSNC2G4X2Y2DGEY4R/ (диагностика),
docs/backlog.md.

Не входит: задача 3 ADR-0020 (`amend-tests` для файлов в `tests/`,
исключение из диффа ревью); локальный слой моделей клона канарейки
(строка бэклога 29.09); правка правил ролей.

Рамка: $40.
