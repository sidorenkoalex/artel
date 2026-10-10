---
task: 01M4JD36367E5CG3GXDV429XTE
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: amend-tests и plank-run с помощником _pult.py

# ТЗ: amend-tests и plank-run работают с планкой, импортирующей помощник `_pult.py`

Источник: строки копилки 06.10, 07.10 (две), 08.10 «amend-tests
отказывает на планке, импортирующей помощник пульта» (приоритет 1);
решение Оператора 10.10.2026 — заводить (очередь критичных, пункт 1).

Случаи:
- 06.10 часть 2 этапа 3 (01M45FK56D): правку планки (test_ac12,
  test_ac14) штатно провести нельзя — «No module named '_pult'»; обход
  Оператора: строка `_pult.py` в `.git/info/exclude` клона задачи,
  помощник сгенерирован `acceptance._plank_helper_text` руками.
- 07.10 01M4ARAXF7: снять AC-2 по решению Оператора штатно нельзя; обход
  через PYTHONPATH на сгенерированный вне планки помощник.
- 08.10 01M4C954HB (test_ac10_operator_docs.py): тот же отказ, тот же
  обход.
- 06.10: plank-run после прогона удаляет `tasks/<id>/` из рабочей копии —
  правка Оператора, выложенная для amend-tests, стирается молча.

Факты (main c6c9245c, сверка 10.10; `orchestrator/amend.py` с 06.10 не
менялся):
- `orchestrator/amend.py::_materialize_tests_if_missing` (~110–126)
  пишет только файлы `acceptance_tests/` из ссылки документов, без
  помощника; в amend.py нет ни `_pult`, ни `PLANK_HELPER_NAME`.
- Сухой сбор `_collect_and_run` (~769) → `acceptance.collect` (~530)
  отказывает на ошибке импорта (~531–533); простой путь
  `acceptance.run(tdir)` (~682) тоже без помощника.
- Гейты кладут помощник через `orchestrator/acceptance.py`:
  `materialize_from_branch` (~676–736), `materialize_files` (~830–844) →
  `_write_plank(..., _with_plank_helper(...))` (~797–806),
  `PLANK_HELPER_NAME = "_pult.py"` (~743), текст —
  `_plank_helper_text` (~762–794) по `orchestrator/plank_helper.py`;
  `plank_present` (~362–371) помощник не считает.
- `_tests_snapshot` (~260, `ls-files --others --exclude-standard`)
  помощник не исключает (`.gitignore` — только `/_*` от корня): выложенный
  помощник читается как правка (`plank_same` ~648–649) и уходит в ссылку
  через `_commit_plank` (~308–329, вызовы ~697, ~787), после чего гейт
  `tests_writing` отказывает на зарезервированном имени
  (`orchestrator/advance_gates/tests_writing.py` ~149–175).
- `orchestrator/plank_run.py::cmd_plank_run` (~84) →
  `acceptance.plank_in_code_copy` (~137–145) → `_write_plank` перезаписывает
  файлы и удаляет чужие, `finally` → `drop_from_code_copy`
  (acceptance.py ~855, ~875–876) удаляет `tasks/<id>/`; защита
  `_docs_in_code_copy` (plank_run.py ~72–81) пропускает всё под
  `acceptance_tests/`.

Требуется:
1. amend-tests (простой путь, путь с долгоживущими файлами, режим
   `--from-branch`) выкладывает планку с помощником тем же узлом, что
   гейты; сухой сбор и прогон планки, импортирующей `_pult`, проходят без
   обходов.
2. Помощник не считается правкой планки: не входит в сравнение с
   ссылкой документов и никогда не фиксируется в ней.
3. plank-run не стирает молча незафиксированную правку Оператора в
   `tasks/<id>/acceptance_tests/` рабочей копии: при расхождении с ссылкой
   документов — именованный отказ до прогона (с подсказкой
   `amend-tests`), правка остаётся на диске.
4. Отказы amend-tests на настоящих дефектах планки (тест красный, сбор
   падает по другой причине) сохраняются — ослабления нет.
5. Смена поведения существующих тестов — только разделом SPEC
   «Меняемое поведение» (инвариант 38).

Критерии приёмки (направление; планку пишет test_author):
- Планка с `from _pult import …`: amend-tests с правкой одного файла
  проходит в простом пути и в пути с долгоживущими файлами; без выкладки
  помощника (мутация) — отказ «No module named '_pult'».
- После amend-tests ссылка документов не содержит `_pult.py`; гейт
  `tests_writing` не отказывает на зарезервированном имени.
- Выложенный только помощник (правки нет) amend-tests считает «без
  изменений».
- plank-run при незафиксированной правке в `acceptance_tests/` отказывает
  с названием файла, правка цела; без правки — прогон, как сегодня.
- Планка с синтаксической ошибкой по-прежнему отказ amend-tests.

Зоны: orchestrator/amend.py, orchestrator/acceptance.py,
orchestrator/plank_run.py, docs/codebase-map.md, tests/.

Только чтение (не менять): orchestrator/plank_helper.py,
orchestrator/advance_gates/, orchestrator/artifact_branch.py,
orchestrator/workspace.py, orchestrator/fsm_advance.py,
orchestrator/checkpoint.py, orchestrator/runner.py,
orchestrator/appendix_tree.py, orchestrator/fsm_merge_gate.py,
orchestrator/zone_lock.py, orchestrator/catalog.py, orchestrator/doctor/,
orchestrator/fsm.py, orchestrator/merge_after.py, orchestrator/config.py,
scripts/, .gitignore, .github/workflows/ci.yml, tests/test_invariants.py,
docs/invariants.md, docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, templates/, skills/, CLAUDE.md, models.yaml,
roles.yaml, targets.yaml, .artel/.

Не входит: приложения PLAN на рубеже in_dev → verifying и в CI (отдельная
задача); смена формата или содержимого помощника `_pult.py`.

Рамка: $40.

Набор моделей: по умолчанию.
