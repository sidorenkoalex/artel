# Записка analyst

## Выяснено
- Итерация 3 (возврат 2 spec_gate 25.10): в SPEC внесены решения гейта 1–11 и У1–У4 ANSWER-1.
  Путь — repo_context.projects_root() (repo_context.py в зонах, только чтение); подпись компонента
  `conventions.md (.artel/projects/<имя>/conventions.md)`; пометка элемента обвязки —
  «путь обвязки, пропущен»; N — на элемент-каталог; ctx None → «не прочитаны: <причина> — <где>»
  + журнал без условия knowledge (треб. 3, AC-14); без сети — AC-13; символьная ссылка, OSError —
  AC-2/AC-11; сломанные sources/base_branch — AC-3/AC-9/AC-11; AC-7 — отрицательная часть по
  тексту role_prompt.py. Матрица — дословно из ANSWER-1. 14 AC, 9 файлов зоны, budget 60.
- Отказ approve «.claude/ не классифицирован»: guard.mentioned_paths проверяет существование
  относительно config.ROOT — у корня пульта `.claude/` есть, в worktree нет; guard в worktree
  молчал. Проверял `guard.spec_unclassified_paths(text, meta, Path('<корень пульта>'))` — пусто.
- Код блока: brief.py:777 `_project_conventions_parts` (подпись `f"{rel} ({where})"`).

## Не сработало
- `ls` в shell нет — пользоваться Read/git.

## Где остановился
SPEC.md готов, status: ready, guard ок, пути классифицированы и от корня пульта.

## Чего не хватило
Guard в worktree не воспроизводит отказ путей approve — нужно передавать root корня пульта.
