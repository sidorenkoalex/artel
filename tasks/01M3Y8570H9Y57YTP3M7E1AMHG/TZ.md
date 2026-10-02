---
task: 01M3Y8570H9Y57YTP3M7E1AMHG
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Шаг test_author с целиком долгоживущей планкой не считается проваленным

# ТЗ: Шаг test_author с целиком долгоживущей планкой не считается проваленным

Источник: строка копилки 02.10 (П1) «Противоречие правил: планка целиком долгоживущая … не оставляет автору тестов ни одного законного файла в acceptance_tests/»; решение Оператора 02.10.

Факты (origin/main; номера строк аналитик сверяет):
- `orchestrator/runner.py::_missing_required_artifact` (около строк 996–1021): для роли `test_author` шаг считается сданным, только если в `tasks/<id>/acceptance_tests/` рабочего каталога роли есть хотя бы один файл; иначе — «шаг завершён без артефакта acceptance_tests/», запись `agent run FAILED` и повтор (до 3 попыток).
- По ADR-0020 планка может быть целиком долгоживущей: тесты лежат в `tests/test_<префикс задачи>_<имя>.py` (правило пути — `scripts/guard.py::is_long_lived_test_path`), а перечень `acceptance_tests/long_lived.sha256.txt` пишет пульт на выходе из `tests_writing`, то есть после шага роли.
- До 02.10 условие выполнял `acceptance_tests/README.md`; с мержа 01M3XVW94Z8E8R71XN7QWYMSP4 `skills/test-authoring.md` запрещает класть `.md` в `acceptance_tests/`.
- 02.10 12:03Z: шаг test_author задачи 01M3Y75GCRESC2KDS9VPRJK4PS написал `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`, каталога `acceptance_tests/` не создал — шаг признан проваленным ($2.20), начата попытка 2/3.

Требуется:
1. Для роли `test_author` шаг считается сданным, если в рабочем каталоге роли есть хотя бы один файл под `tasks/<id>/acceptance_tests/` ЛИБО хотя бы один долгоживущий файл задачи — путь, для которого `guard.is_long_lived_test_path(task_id, rel)` истинно (новый или изменённый относительно базы ветки, тем же признаком, которым пульт коммитит долгоживущие файлы test_author). Правило пути — только через `guard.is_long_lived_test_path`, без второй копии.
2. Нет ни того, ни другого — прежний отказ «шаг завершён без артефакта …»; текст называет обе ожидаемые формы.
3. Остальные роли (`analyst`, `developer`, `reviewer`) — без изменений.
4. Тесты в новом файле `tests/test_test_author_long_lived_artifact.py`, каждый с «Ловит мутацию: …»: а) только долгоживущий файл задачи, `acceptance_tests/` нет — шаг сдан; б) файл `tests/test_<чужой префикс>_x.py` или `tests/test_other.py` — не засчитывается, отказ; в) только файл в `acceptance_tests/` — сдан, как раньше; г) ничего — отказ, текст называет обе формы.

Зоны: orchestrator/runner.py, tests/test_test_author_long_lived_artifact.py, docs/codebase-map.md.

Только чтение (не менять): scripts/guard.py, orchestrator/checkpoint.py, orchestrator/advance_gates/, orchestrator/fsm_advance.py, остальные файлы tests/, skills/, docs/adr/, docs/invariants.md, tests/test_invariants.py, tasks/.

Не входит: изменение момента записи перечня `long_lived.sha256.txt`; правка `skills/test-authoring.md`; пересмотр попыток шага.

Рамка: $15.
