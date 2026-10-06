---
task: 01M490TDWEMDQ700VXTKYANF7K
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: guard --all принимает паспорт задачи артели без frontmatter

# ТЗ: guard --all принимает паспорт задачи артели без frontmatter (мерж задач артели заблокирован)

Источник: 06.10, гейт мержа задачи 01M48FRD9RJDBBVT2SN0FY5G2A — «merge
отклонён: guard --all по дереву мержа нашёл нарушения:
tasks/01M48FRD9RJDBBVT2SN0FY5G2A/PASSPORT.md: нет frontmatter». С мержа
части 3 этапа 3 ADR-0021 (01M484RNV3QBDY3B0M16J916ZP, строка 14 SPEC)
паспорт задачи ведётся и у задач артели; снимок артефактной ветки ложится на
main, и `guard --all` по дереву мержа требует frontmatter у каждого
`tasks/**/*.md`. Мерж любой задачи артели отказывает, CI main на таком
дереве покраснел бы заданием guard. Решение Оператора 06.10: срочная
задача, первой в очереди.

Факты (пин 73ce3329, сверка кода 06.10):
- `scripts/guard.py::main` (~3764) при `--all` обходит
  `Path("tasks").rglob("*.md")`, исключает посторонние файлы
  (`scan_extraneous_task_root_files`) и передаёт остальное в проверку
  артефакта; отказ «нет frontmatter» — ~3657.
- Белый список имён первого уровня `TASK_ROOT_ALLOWED_MD` (~1674) уже знает
  `PASSPORT.md` (hotfix №21, 11.09: паспорт внешнего проекта), но проверку
  frontmatter паспорт не проходит: паспорт — журнал переходов, который пишет
  пульт (`orchestrator/artifact_branch.py`, `PASSPORT_REL_TMPL` ~35,
  запись ~664), заголовок «# Паспорт живой задачи» и строки «<время>
  <состояние> actor=<кто>», frontmatter у него нет.
- Гейт мержа запускает `scripts/guard.py` из корня дерева мержа
  (`orchestrator/fsm_merge_gate.py::_guard_all_violations` ~456); правка
  guard в ветке задачи действует уже на её собственном мерже. В `main`
  паспортов в `tasks/` сейчас нет.

Требуется:
1. `guard --all` не проверяет frontmatter и обязательные разделы у
   `tasks/<id>/PASSPORT.md` (первый уровень каталога задачи): файл паспорта
   — не артефакт роли. Прочие проверки не ослабляются: посторонний `.md`
   первого уровня — по-прежнему отказ; `PASSPORT.md` в любом другом месте
   (`acceptance_tests/`, вложенный каталог) — по-прежнему посторонний.
2. Проверка одиночного файла `guard.py tasks/<id>/PASSPORT.md` (без
   `--all`) ведёт себя так же, как `--all` (решение SPEC: пропуск с
   пометкой либо явное «не артефакт»), без ложного отказа.
3. Тесты в `tests/` с заявками «Ловит мутацию»: дерево `tasks/` с
   паспортом без frontmatter и с корректными артефактами — `guard --all`
   код 0; тот же паспорт под другим именем первого уровня — отказ
   «посторонний файл»; артефакт SPEC.md без frontmatter рядом с паспортом —
   по-прежнему отказ «нет frontmatter». Существующие тесты не ослабляются.

Зоны: scripts/guard.py, tests/, docs/codebase-map.md.

Только чтение (не менять): tasks/, orchestrator/artifact_branch.py,
orchestrator/fsm_merge_gate.py, conftest.py, tests/test_invariants.py,
docs/invariants.md, docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, templates/, skills/, CLAUDE.md, models.yaml,
roles.yaml, targets.yaml, .github/workflows/ci.yml.

Не входит: исключение паспорта из снимка артефактной ветки на main; формат
паспорта; правка задач 01M48FRD9RJDBBVT2SN0FY5G2A и
01M48WR0HKZW8KJCBWDZTFC4ZY (их мерж Оператор повторит после мержа этой
задачи).

Рамка: $20.
