---
task: 01M443HPZBMJGCHVGV4JQN88RS
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Тесты не подменяют time.sleep на весь процесс

# ТЗ: тесты не подменяют time.sleep на весь процесс

Источник: бэклог — строки «Подмены time.sleep на весь процесс в tests/ —
общий шаблон» и «Подмена time.sleep во всём процессе в
tests/test_main_ci_line.py» (обе приоритет 2). Решение Оператора 04.10.2026
«заводи» — параллельно задаче 01M443BPQEA9ZMJ3R50THNB1MF.

Факты (пин 16f663b4, сверка 04.10):
- Подмена `mock.patch("time.sleep")`, `mock.patch.object(time, "sleep", …)`
  или `mock.patch.object(<модуль пульта>.time, "sleep", …)` (у модулей
  пульта `time` — это сам модуль стандартной библиотеки) меняет паузу
  всего процесса. Её ловят паузы стандартной библиотеки, прежде всего
  `subprocess.Popen._wait` при ещё живом дочернем процессе: на медленном
  раннере тест с `sleep.assert_not_called()` или со счётчиком пауз
  краснеет случайным образом, а подменённые «часы» сдвигаются.
- Исправлено точечно: `tests/test_merge_gate_ci_wait.py`
  (01M3YJ7VQ7CSBBPC8X84Z0YG3R, регрессионный приём —
  `tests/test_merge_gate_clock_isolation.py`) и `CmdRunFailureTest`
  (01M3YS928033B1QF89VN2N5KC3).
- Оставшиеся вхождения (поиск 04.10, 21 место в 10 файлах):
  `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py` (8),
  `tests/test_merge_queue.py` (3), `tests/test_step_cost.py` (2),
  `tests/test_invariants.py` (2), `tests/test_main_ci_line.py` (1, ~360,
  с `sleep.assert_not_called()`), `tests/test_acceptance_tests_flow.py`
  (1), `tests/test_agent_failure.py` (1), `tests/test_runner_role_model.py`
  (1), `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py` (1),
  `tests/test_merge_gate_clock_isolation.py` (1 — сам регрессионный
  тест, упоминание в объяснении приёма).

Требуется:
1. Ни один тест в `tests/` не подменяет `time.sleep` на весь процесс.
   Пауза подменяется только там, где её зовёт проверяемый код: подменой
   ссылки модуля на `time` (объект-заместитель, у которого `sleep`
   подменён, а остальное — настоящий `time`), либо уже существующей
   точкой паузы модуля, если она есть. Утверждения о паузах (число,
   длительность, «пауз не было») остаются прежними по смыслу.
2. Сторож в `tests/`: проверка исходников `tests/`, которая находит
   глобальную подмену `time.sleep` (все три формы из «Фактов») и
   краснеет с именем файла и строки; заявка «Ловит мутацию».
   Регрессионный тест `tests/test_merge_gate_clock_isolation.py`
   сторожем не отвергается (SPEC решает, как: исключение по смыслу
   или правка формулировки в нём).
3. `tests/test_invariants.py` — защищённый путь: его правка — приложением
   к PLAN. Долгоживущие файлы других задач
   (`tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`,
   `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`): SPEC
   сверяет, допускают ли гейты сохранности тестов и перечня
   долгоживущих тестов правку без ослабления; если нужна команда
   Оператора — называет её в SPEC.
4. Код пульта не меняется. Если без обёртки паузы в коде пульта
   какое-то место не решается — эскалация с перечнем таких мест, без
   правки `orchestrator/`.
5. Существующие тесты не ослабляются: ни одно утверждение не удаляется
   и не смягчается; полный прогон `tests/` зелёный.

Зоны: tests/.

Приложением: tests/test_invariants.py.

Только чтение (не менять): orchestrator/, scripts/, docs/, templates/,
skills/, CLAUDE.md, models.yaml, roles.yaml, .github/workflows/ci.yml,
conftest.py.

Не входит: паузы в коде пульта; другие глобальные подмены (часы
`time.monotonic`, `datetime`) — их класс фиксируется в «Предложениях
системе», если встретится.

Рамка: $25.
