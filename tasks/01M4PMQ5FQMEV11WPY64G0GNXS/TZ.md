---
task: 01M4PMQ5FQMEV11WPY64G0GNXS
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Итог прогона и провал внутри subTest — в отчёте suite-run и перечнях упавших

# ТЗ: Итог прогона и провал внутри subTest — в отчёте suite-run и в перечнях упавших гейтов

Источник: копилка 11.10, приоритет 1 («suite-run не видит провал внутри
subTest…», задача 01M4M67SGN, прогоны №3 и №4) и строка бэклога
«Разбор красных тестов видит провал внутри subTest» (приоритет 3) —
один механизм. Решение Оператора 12.10.2026 — заводить.

Факты (origin/main 3a1be8b0; замер pytest 9.1.1, pytest-xdist 3.8.0 —
версии requirements.lock):
- Случай 11.10: настоящая итоговая строка прогона — `1 failed, 4936
  passed, 2 skipped, 2144 subtests passed in 436.40s`, в коротком итоге —
  `SUBFAILED[merge_gate] tests/test_invariants.py::ManualGatesNeedTheOperatorTest::test_operator_approve_passes_each_gate - …`;
  отчёт `suite-run` — «красный прогон, прошло: 1, упало: 0»,
  `failed.json` — `{"run": 4, "failed": []}`.
- Причина «прошло: 1» — `orchestrator/acceptance.py::run_summary_line`
  (~153): берёт ПЕРВОЕ совпадение `_RUN_SUMMARY` во всём выводе. В логе
  прогона 3 первое совпадение — строка хода подтеста существующего теста
  `[gw8] [ 87%] SUBPASSED(mode="'full'", output="'1 passed in 0.1s'") tests/test_suite_run.py::SuiteRunJournalTest::…`
  (метка подтеста содержит текст, похожий на итог). Функция питает
  `suite_run` (подсчёт), `run_digest` (журнал гейтов),
  `save_suite_result`, `_remember_gate_failures`.
- Причина «упало: 0» — разборы упавших не знают статуса подтеста:
  - `acceptance._FAILED_LINE` (~150) = `^(?:FAILED|ERROR) \S+.*$` →
    `failed_test_lines` (журнал гейтов `run_digest`, `orchestrator/amend.py:551`);
  - `acceptance._FAILED_ENTRY` / `failed_entries` (~1397-1430) →
    сохранённые перечни упавших гейта и базы (`save_suite_result`,
    `_remember_gate_failures`, `saved_failures`), по которым
    `suite_run.render` делит «новые на ветке / падают и на базе»;
  - `suite_run._STATUS` (~76) = `PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS`,
    `_PROGRESS` (~79) — строки хода.
- Замер вида вывода:

  | Где | Без xdist (`-vv`) | С xdist (`-n 2 -p xdist -vv`) |
  |---|---|---|
  | Строки хода, unittest subTest | строки SUBFAILED нет; родитель — `<nodeid> PASSED [ 25%]` | `[gw0] [ 50%] SUBFAILED[merge_gate] <nodeid> `, затем `[gw0] [ 50%] PASSED <nodeid>` |
  | Строки хода, фикстура `subtests` | `<nodeid> SUBFAILED[px] (x=2) [100%]`, затем `<nodeid> FAILED` | `[gw1] [100%] SUBFAILED[px] (x='2') <nodeid>`, затем `FAILED <nodeid>` |
  | Короткий итог | `SUBFAILED[merge_gate] <nodeid> - <сообщение>`; `SUBFAILED(i=1) <nodeid> - …` | то же, метка `(i='1')` |
  | Итоговая строка | `5 failed, 3 passed, 4 subtests passed in 0.03s` | то же |

  Каждый упавший подтест считается в «N failed» отдельно; родитель
  unittest при этом считается «passed». Метка может содержать пробелы,
  скобки и кавычки, вид метки зависит от xdist.

Требуется:
1. `acceptance.run_summary_line` возвращает ПОСЛЕДНЕЕ совпадение итоговой
   строки в выводе, а не первое (привязку к рамке из «=» не вводить:
   около десяти файлов `tests/` подают синтетический вывод без рамки).
2. Провал подтеста попадает во все три разбора упавших:
   `acceptance.failed_test_lines` (`_FAILED_LINE`),
   `acceptance.failed_entries` (`_FAILED_ENTRY`, сохранённые перечни
   гейта и базы) и строки хода `suite_run` (`_STATUS`/`_PROGRESS`).
   Разбор: nodeid — слово с `::` (в строке хода — последнее, в коротком
   итоге — перед « - »), метка — всё между `SUBFAILED` и nodeid.
3. Единица упавшего для подтеста — пара «nodeid родителя + метка», в
   выводе — `<nodeid> <метка>`. Сравнение «новые на ветке / падают и на
   базе» — по этой паре; повтор `--failed` — по nodeid родителя. Число
   упавших в отчёте `suite-run` = число таких пар плюс упавшие тесты без
   подтестов; оно совпадает с суммой «N failed» и «N errors» итоговой
   строки; тест с фикстурой `subtests`, сам помеченный FAILED, — отдельная
   единица, как его считает pytest. Если разбор
   нашёл меньше упавших, чем итоговая строка, отчёт говорит об этом прямо
   («итог pytest: N упавших, разобрано M»), а не «упало: 0».
4. Строка `PASSED <nodeid>` родителя после `SUBFAILED` того же nodeid
   провала не снимает (правило «упавший хоть раз остаётся упавшим»).
5. Вердикт гейтов и `suite-run` (красный/зелёный) по-прежнему по коду
   выхода pytest; ни одна прежде видимая строка FAILED/ERROR из перечней
   не выпадает.
6. Тесты в `tests/` на захваченном выводе обоих видов (с xdist и без,
   образцы — таблица выше) и один настоящий прогон временного файла с
   subTest под `-n 2 -p xdist`. «Ловит мутацию»: возврат к первому
   совпадению итоговой строки (вывод, где строка хода с «1 passed in
   0.1s» стоит раньше настоящего итога); удаление статуса подтеста из
   каждого из трёх разборов; ключ «только родитель» вместо пары (подтест
   A падает на базе, подтест B того же теста — только на ветке → B
   новый); снятие провала строкой PASSED родителя. Существующие тесты не
   ослабляются.
7. Раздел SPEC «Меняемое поведение» называет: текст отчёта `suite-run`;
   `orchestrator/amend.py:551` — при провале только подтеста маркер
   «Красен до реализации» теперь требуется лишь от файла упавшего
   подтеста (то же правило, что для обычного теста); «прошло» итоговой
   строки включает родителей с упавшими подтестами.

Матрица неослабления (независимая проверка 12.10): вердикт по коду
выхода не трогается; перечни упавших только расширяются; сравнение с
базой по паре «родитель + метка» не грубее, чем у обычного теста; при
расхождении вида метки между прогонами провал считается новым — строже,
не мягче (прогоны ветки и базы в `suite-run` идут одной командой, вид
совпадает).

Зоны: orchestrator/suite_run.py, orchestrator/acceptance.py, tests/,
docs/codebase-map.md.

Только чтение (не менять): orchestrator/amend.py, orchestrator/fsm.py,
orchestrator/fsm_merge_gate.py, orchestrator/config.py,
orchestrator/liveness.py, tests/sandbox.py, tests/test_invariants.py,
docs/invariants.md, docs/adr/, docs/backlog.md, skills/, templates/,
CLAUDE.md, roles.yaml, .github/, .artel/.

Не входит: правило в skills/test-authoring.md о приёме «один ассерт по
списку вместо subTest» (защищённый путь); `suite-run --workers`.

Рамка: $25.

Набор моделей: по умолчанию.
