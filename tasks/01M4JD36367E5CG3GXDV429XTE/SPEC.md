---
task: 01M4JD36367E5CG3GXDV429XTE
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/amend.py, orchestrator/acceptance.py, orchestrator/plank_run.py, docs/codebase-map.md, tests/
budget_usd: 40
---

# SPEC: amend-tests и plank-run работают с планкой, импортирующей помощник `_pult.py`

## Контекст
Гейты пульта выкладывают планку приёмки вместе с помощником `_pult.py`
(`orchestrator/acceptance.py`: `materialize_from_branch`,
`materialize_files` → `_write_plank(..., _with_plank_helper(...))`,
`PLANK_HELPER_NAME`), а `amend-tests` — нет:
`orchestrator/amend.py::_materialize_tests_if_missing` пишет только файлы
`acceptance_tests/` из ссылки документов, и сухой сбор
(`_collect_and_run` → `acceptance.collect`) и простой путь
`acceptance.run(tdir)` падают на «No module named '_pult'». Штатно
поправить такую планку нельзя — три случая 06.10–08.10 (01M45FK56D,
01M4ARAXF7, 01M4C954HB) прошли через ручные обходы Оператора
(`.git/info/exclude`, PYTHONPATH). Выложенный помощник при этом не
исключён из `_tests_snapshot` (`ls-files --others --exclude-standard`) и
читается как правка планки (`plank_same`), уходит в ссылку через
`_commit_plank`, после чего гейт `tests_writing` отказывает на
зарезервированном имени. Отдельно `plank-run`
(`orchestrator/plank_run.py::cmd_plank_run` →
`acceptance.plank_in_code_copy` → `drop_from_code_copy`) перезаписывает и
после прогона удаляет `tasks/<id>/` рабочей копии, молча стирая
незафиксированную правку Оператора в `acceptance_tests/`, выложенную для
`amend-tests` (защита `_docs_in_code_copy` пропускает всё под
`acceptance_tests/`).

## Требования
1. `amend-tests` во всех трёх путях — простом, с долгоживущими файлами и в
   режиме `--from-branch` — выкладывает планку вместе с помощником
   `_pult.py` тем же узлом `orchestrator/acceptance.py`, которым это делают
   гейты; сухой сбор и прогон планки, импортирующей `_pult`, проходят без
   обходов (без строк в `.git/info/exclude`, без PYTHONPATH, без ручной
   генерации помощника).
2. Помощник `_pult.py` не считается правкой планки: он не входит в
   сравнение выложенной планки со ссылкой документов и никогда не
   фиксируется в ссылке документов задачи.
3. `plank-run` не стирает молча незафиксированную правку Оператора в
   `tasks/<id>/acceptance_tests/` рабочей копии кода: при расхождении этих
   файлов со ссылкой документов команда до прогона pytest отказывает
   именованным отказом, который называет расходящийся файл и подсказывает
   `amend-tests`; файлы правки остаются на диске нетронутыми. Без
   расхождения `plank-run` выкладывает и прогоняет планку, как сегодня.
4. Отказы `amend-tests` на настоящих дефектах планки сохраняются без
   ослабления: красный тест планки и падение сбора по причине, отличной от
   отсутствия помощника (например, синтаксическая ошибка), по-прежнему
   дают отказ.
5. Смена ожидания существующего тестового метода `tests/` допустима
   только через раздел SPEC «Меняемое поведение» (инвариант 38); на
   момент написания SPEC ни одно требование не меняет ожидание известного
   метода `tests/` — раздел отсутствует.

## Критерии приёмки
AC-1. Планка, файл которой делает `from _pult import …`, с правкой одного
файла: `amend-tests` в простом пути проходит (сухой сбор и прогон зелёные,
правка зафиксирована); без выкладки помощника (мутация) тот же сценарий
отказывает с «No module named '_pult'».

AC-2. Тот же сценарий, что в AC-1, в пути с долгоживущими файлами:
`amend-tests` проходит; без выкладки помощника — отказ с
«No module named '_pult'».

AC-3. Планка, импортирующая `_pult`, в режиме `amend-tests --from-branch`:
сбор и прогон проходят без ошибки импорта `_pult`.

AC-4. После успешного `amend-tests` по AC-1/AC-2 дерево ссылки документов
задачи не содержит `_pult.py` ни под `tasks/<id>/acceptance_tests/`, ни
где-либо ещё в `tasks/<id>/`; гейт `tests_writing`
(`orchestrator/advance_gates/tests_writing.py`) на этой ссылке не
отказывает по зарезервированному имени помощника.

AC-5. В рабочей копии выложена планка, совпадающая со ссылкой документов,
плюс помощник `_pult.py` (других правок нет): `amend-tests` отвечает
отказом «нет изменений» — как без помощника — и ничего не фиксирует в
ссылке документов.

AC-6. В `tasks/<id>/acceptance_tests/` рабочей копии кода лежит файл,
расходящийся со ссылкой документов (изменённый или новый): `plank-run`
отказывает до запуска pytest, текст отказа называет этот файл и
содержит `amend-tests`; после отказа файл на диске с тем же содержимым.

AC-7. Без расхождения в `tasks/<id>/acceptance_tests/` рабочей копии
(файлов нет либо они совпадают со ссылкой документов) `plank-run`
выкладывает и прогоняет планку, как сегодня: pytest запущен, итог
напечатан.

AC-8. Правка планки с синтаксической ошибкой в файле `test_*.py` —
`amend-tests` отказывает, ничего не фиксирует в ссылке документов.

AC-9. Правка планки, в которой тест красный (с выложенным помощником,
импорт `_pult` успешен), — `amend-tests` отказывает, ничего не фиксирует
в ссылке документов.

## Оценка объёма и деление
Прогноз диффа: 40 КиБ (код трёх модулей — ~10 КиБ, тесты `tests/` —
~30 КиБ), ниже половины потолка гейта ёмкости
(`REVIEW_SNAPSHOT_DIFF_MAX_BYTES`, 256 КиБ).

Сработавший сигнал — число файлов зоны (5). Два из них — общие зоны
(`docs/codebase-map.md`, `tests/`); собственных модулей кода три:
`orchestrator/amend.py`, `orchestrator/acceptance.py`,
`orchestrator/plank_run.py`. Прочие сигналы не срабатывают: 9 критериев
(< 10), `budget_usd` 40 (< 60), прогноз диффа выше.

Материал для решения Оператора — монолит:
- Требования 1 и 2 атомарны: выкладка помощника в `amend-tests` без его
  исключения из сравнения со ссылкой отправит `_pult.py` в ссылку
  документов через `_commit_plank`, и гейт `tests_writing` откажет на
  зарезервированном имени — промежуточное состояние хуже сегодняшнего;
  исключение без выкладки ничего не чинит.
- Требование 3 (`plank-run`) отделимо по смыслу, но его узел выкладки —
  тот же `acceptance.plank_in_code_copy` → `_write_plank` /
  `drop_from_code_copy` в `orchestrator/acceptance.py`, что и узел
  выкладки требования 1: часть, вынесенная отдельно, резала бы зону
  `orchestrator/acceptance.py` поперёк. Его объём мал (отказ до прогона
  с названием файла), а отдельная подзадача удвоила бы шаги аналитика и
  автора тестов при рамке ТЗ $40.

## Не входит
- Приложения PLAN на рубеже `in_dev → verifying` и в CI — отдельная
  задача.
- Смена формата или содержимого помощника `_pult.py`
  (`orchestrator/plank_helper.py`, `acceptance._plank_helper_text`).
- Правки путей «только чтение» ТЗ: `orchestrator/plank_helper.py`,
  `orchestrator/advance_gates/`, `orchestrator/artifact_branch.py`,
  `orchestrator/workspace.py`, `orchestrator/fsm_advance.py`,
  `orchestrator/checkpoint.py`, `orchestrator/runner.py`,
  `orchestrator/appendix_tree.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/zone_lock.py`, `orchestrator/catalog.py`,
  `orchestrator/doctor/`, `orchestrator/fsm.py`,
  `orchestrator/merge_after.py`, `orchestrator/config.py`, `scripts/`,
  `.gitignore`, `.github/workflows/ci.yml`, `tests/test_invariants.py`,
  `docs/invariants.md`, `docs/adr/`, `docs/roadmap.md`, `docs/backlog.md`,
  `docs/operator-session.md`, `templates/`, `skills/`, `CLAUDE.md`,
  `models.yaml`, `roles.yaml`, `targets.yaml`, `.artel/`. В частности,
  исключение помощника из сравнения (требование 2) достигается в зоне
  задачи, не правкой `.gitignore`.
- Ослабление гейта `tests_writing` на зарезервированном имени — гейт не
  меняется, требование 2 убирает причину его отказа.
- Неизменность ожиданий существующих тестов `tests/` вне раздела
  «Меняемое поведение» (требование 5) — её держит пульт (рубеж
  неослабления), отдельного AC нет.

## Материалы
- `tasks/01M4JD36367E5CG3GXDV429XTE/TZ.md` — факты по main c6c9245c с
  адресами строк.
- Копилка 06.10, 07.10 (две), 08.10: «amend-tests отказывает на планке,
  импортирующей помощник пульта»; решение Оператора 10.10.2026.
