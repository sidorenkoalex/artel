---
task: 01M4JD3SRN66SD6BM63XAGHB11
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Приложения PLAN на рубеже in_dev → verifying и в CI ветки

# ТЗ: Приложения PLAN — рубеж in_dev → verifying и CI ветки по одному правилу

Источник: строки копилки 06.10 «Рубеж in_dev → verifying гоняет планку
без приложений PLAN» и «Признание "приложение PLAN уже наложено в базе"
есть не у всех узлов» (приоритет 1); решение Оператора 10.10.2026 —
заводить (очередь критичных, пункт 2).

Случаи:
- 06.10 часть 2 этапа 3 (01M45FK56D): сторож AC-13 на рубеже
  in_dev → verifying красен по построению — планка гоняется без
  приложения PLAN; обход Оператора (приложение к targets.yaml вперёд кода
  в main) сломал тест планки AC-14; итого на одном рубеже 3 эскалации и
  2 решения Оператора.
- 06.10: операторский коммит защищённого файла вперёд кода несовместим с
  приложением, которое этот файл несёт: CI ветки отказывает
  «не накладывается на дерево чекаута», хотя приложение уже в базе.

Факты (main c6c9245c, сверка 10.10):
- `orchestrator/advance_gates/acceptance.py::_acceptance_run_body` (~260):
  `workspace.ensure` (~322), `acceptance.plank_in_code_copy` (~347–348),
  `acceptance.run` (~370, ~373) — в рабочей копии без приложений; слов
  `appendix`/`suite_tree` в файле нет.
- Остальные прогоны накладывают приложения через
  `orchestrator/appendix_tree.py::suite_tree`: автогейт
  (`orchestrator/fsm_autogate.py` ~322), approve (`orchestrator/fsm.py`
  ~1133), suite-run (`orchestrator/suite_run.py` ~446).
- Признание «уже в базе» (`git apply --reverse --check`) написано трижды:
  `orchestrator/fsm_merge_gate.py::_appendix_already_in_main` (~851),
  вложенная `in_tree` в `appendix_tree._prepared` (~187–191, без записи
  журнала), `orchestrator/advance_gates/plan_appendix.py::_appendix_already_in_base`
  (~212, журнал «приложение PLAN уже в базе»).
- `scripts/plan_appendix_ci.py::apply_appendix` (~188) — только прямой
  `git apply`; `run` (~228–234) печатает «не накладывается на дерево
  чекаута» и возвращает 1. Обратной проверки нет. Скрипт не импортирует
  модули пульта.
- CI по pull_request приложения уже накладывает (01M466ZERX), не входит.

Требуется:
1. Рубеж in_dev → verifying гоняет планку и долгоживущие файлы задачи на
   дереве с наложенными приложениями PLAN — тем же узлом, что автогейт,
   approve и suite-run (`appendix_tree.suite_tree` или его общая часть);
   неприменимое приложение — именованный отказ, как у тех узлов.
2. Признание «приложение уже в базе» — одно правило для гейта мержа,
   дерева полного прогона, гейта применимости на выходе in_dev и CI ветки:
   уже наложенное приложение пропускается с записью «приложение PLAN N
   уже в базе» (в журнал — у узлов пульта, в вывод — у CI), а не
   отказывает. Где можно — одна общая функция; CI-скрипт без импорта
   модулей пульта повторяет то же правило, совпадение проверяется тестом.
3. Приложение, которое не накладывается ни прямо, ни обратно, — по-прежнему
   отказ (ослабления нет).
4. Смена поведения существующих тестов — только разделом SPEC
   «Меняемое поведение» (инвариант 38).

Критерии приёмки (направление; планку пишет test_author):
- Задача с приложением PLAN к защищённому тесту, без которого её код
  красен: рубеж in_dev → verifying зелёный; без наложения (мутация) —
  красный.
- Приложение уже в базе: CI-скрипт ветки завершается успехом и печатает
  «уже в базе»; рубеж in_dev → verifying и гейт мержа его пропускают.
- Неприменимое ни прямо, ни обратно приложение — отказ во всех четырёх
  узлах.
- Признание в узлах пульта и в CI-скрипте даёт одинаковый ответ на одном
  наборе случаев (тест сверки).

Зоны: orchestrator/advance_gates/acceptance.py,
orchestrator/advance_gates/plan_appendix.py, orchestrator/appendix_tree.py,
orchestrator/fsm_merge_gate.py, scripts/plan_appendix_ci.py,
docs/codebase-map.md, tests/.

Только чтение (не менять): orchestrator/fsm_autogate.py,
orchestrator/fsm.py, orchestrator/suite_run.py, orchestrator/acceptance.py,
orchestrator/amend.py, orchestrator/workspace.py, orchestrator/config.py,
orchestrator/zone_lock.py, orchestrator/catalog.py, orchestrator/doctor/,
orchestrator/merge_after.py, scripts/guard.py, .github/workflows/ci.yml,
tests/test_invariants.py, targets.yaml, docs/invariants.md, docs/adr/,
docs/roadmap.md, docs/backlog.md, docs/operator-session.md, templates/,
skills/, CLAUDE.md, models.yaml, roles.yaml, .artel/.

Не входит: условия шагов CI по событиям push/pull_request (сделано
01M466ZERX); уточнение урока «защищённый файл — первым» в
docs/operator-session.md (правка Оператора); amend-tests и помощник
`_pult.py` (отдельная задача).

Рамка: $40.

Набор моделей: по умолчанию.
