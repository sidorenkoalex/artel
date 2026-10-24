---
task: 01M5PCB66D936FDGG7H09CVGA1
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Сведение тестов, волна 1б: тесты doc-commit и сверки по базе — в файл модуля pytest с доказательством мутациями

# Сведение тестов, волна 1б: тесты `doc-commit` и сверки по базе (`orchestrator/notes.py`) — в файл модуля в стиле pytest с доказательством множеством убиваемых мутаций

## Факты

Строка бэклога «Периодическая консолидация тестов артели» (решение Оператора 23.10.2026); ADR-0027 п. 8 и ADR-0020 п. 8; мандат Оператора 23.10.2026 (дословно): «Волна сведения тестов по note; после бери все остальные модули в работу - даю мандат»; решение Оператора 24.10.2026 вести волну 1б параллельно с 1а («ок»). Порядок работы — тот же, что у волны 1а (01M5NNDYGQ8G6VFDEEXYBB0W3D, решения её гейта SPEC кругов 1–3 перенесены сюда в требования). Сверено с origin/main 549e997e.

- Файлы волны: `tests/test_doc_commit.py` (28 тестов, 28 строк «Ловит мутацию»), `tests/test_doc_commit_suite_gate.py` (17/17), `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py` (13/13), `tests/test_doc_commit_held_base.py` (4/4), `tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py` (6/6), `tests/test_notes_batch_flush_edges.py` (3/3) — около 71 теста, около 2270 строк. Импорты между файлами: `tests/test_doc_commit_suite_gate.py` берёт из `tests/test_doc_commit.py`, `tests/test_notes_batch_flush_edges.py` — `SuiteGateSandbox`, `CONFIG_REL`, `NEW_CONFIG_TEXT` из `tests/test_doc_commit_suite_gate.py`; вне волны импортов нет. Два файла с префиксом id — долгоживущие тесты задач в `done` (`tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py`, `tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py`); их перечни сумм после мержа не сверяются (ADR-0020 п. 6), удаление — ветвь ADR-0020 п. 8 «без замены долгоживущим тестом — решением Оператора».
- Команда `mutation-run` (01M5NPKPWF, доработка 01M5P2BHX6): `artel.py mutation-run <id> --ref base|worktree --tests <файлы> [--patches a-b] --wait <минуты>` печатает шапку (источник патчей, sha ревизии, sha256 патчей) и все строки таблицы; разрешена роли; общий замок машины с полными прогонами — при занятом замке отказ сразу с держателем. Параллельно идёт волна 1а со своими прогонами мутаций.
- Общие фикстуры — `tests/fixtures.py`; помощники с утверждениями (`DocCommitRefusalTest.assert_refused`, `_stale_scenario`, `assert_nothing_sent` и др.) фикстурами быть не могут (ADR-0027 п. 3) — функции модуля.
- Мандат на удаление файлов выдаётся командой `answer` на гейте SPEC (гейт неослабления читает мандат только из `ANSWER-n.md`).

## Требования

1. Мутации: для каждой строки «Ловит мутацию» шести файлов — патч к коду `orchestrator/` в `tasks/<id>/mutation-<nnn>.diff` (первый уровень каталога документов, номера подряд; одинаковые по смыслу строки — одна мутация со списком тестов). Таблица «до»: `mutation-run <id> --ref base --tests <шесть файлов>` (части `--patches` под предел; вывод каждой части переносится в PLAN раздела «Мутации до» дословно, с шапкой, до старта следующей части). Мутация, «убитая» ошибкой сбора, импорта, setup или только падением подготовки песочницы (`setUp`), — не доказательство: патч переписывается так, чтобы падало утверждение теста; узлы падения подготовки роль отмечает в PLAN. Не убитая никем — находка в PLAN. Если замок занят прогоном другой задачи — повторить позже, не эскалировать.
2. Свод: тесты шести файлов — в новый `tests/test_doc_commit_module.py` в стиле pytest (функции, `assert`, `parametrize`, фикстуры `tests/fixtures.py` и собственные фикстуры файла; помощники с утверждениями — функции модуля). Утверждения и проверяемые свойства не меняются: ожидания дословно; `pytest.raises(..., match=re.escape(<текст>))` — только где исходник проверял текст исключения, голый `assertRaises(E)` → `pytest.raises(E)` без `match`; перебор по константам кода — `parametrize` по самой константе или цикл в теле функции, не литералы; итерации с общим состоянием и случайный выбор — прежним циклом. Дубль удаляется только если (а) каждую его мутацию по таблице «до» убивает и другой сохраняемый тест и (б) каждый литерал и вид каждого утверждения удаляемого теста есть в утверждениях сохраняемого теста, убивающего те же мутации; удалённые дубли — в PLAN с мутациями. Тест, чью мутацию не убил никто, не удаляется (строка «Ловит мутацию» переписывается на мутацию, которую он убивает, со своим патчем, либо находка в PLAN). У каждой функции — «Ловит мутацию:».
3. Таблица «после»: `mutation-run <id> --ref worktree --tests tests/test_doc_commit_module.py`, вывод — в PLAN «Мутации после». Каждая мутация, убитая «до», убита «после»; дерево `orchestrator/` ревизий обеих шапок совпадает (`git diff --quiet <sha до> <sha после> -- orchestrator/`), sha256 каждого патча в обеих шапках совпадает; при подтяжке main между прогонами «до» прогоняется заново. Число тестов, строк и время адресного прогона до и после — в PLAN.
4. Шесть исходных файлов удаляются (мандат — `answer` на гейте SPEC; удаление утверждения без переноса, ослабление сравнения, `skip`/`xfail`, подъём пределов не разрешены).
5. Независимая проверка (повтор `mutation-run` сессией при Операторе на зафиксированном наборе патчей) — до approve на merge_gate.

Зоны: tests/, docs/codebase-map.md

Ограничение зон по смыслу: в `tests/` — удаление шести файлов из «Фактов» и новый `tests/test_doc_commit_module.py`; `tests/fixtures.py`, `tests/sandbox.py`, файлы волны 1а (`tests/test_notes.py`, `tests/test_notes_apply.py`, `tests/test_notes_row_format.py`, `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py`, `tests/test_notes_module.py`) не меняются; код `orchestrator/` не меняется.

Только чтение: orchestrator/ (весь код пульта; мутации — только во временной копии `mutation-run`), orchestrator/notes.py, orchestrator/mutation_run.py, tests/fixtures.py, tests/sandbox.py, orchestrator/advance_gates/test_integrity.py, orchestrator/advance_gates/outcome_integrity.py, scripts/guard.py, tests/test_invariants.py, skills/test-authoring.md, docs/adr/0027-pytest-style-tests.md, docs/adr/0020-long-lived-acceptance-tests-in-tests.md.

Не входит: файлы волны 1а; `tests/test_01m5n8a5jbeq15dchdp95ebdzr_batch_flush.py` (тесты пакетного сброса копилки, вместе с модулем note позже); изменение кода `notes.py`; правка общих фикстур.

Бюджет: $70.
