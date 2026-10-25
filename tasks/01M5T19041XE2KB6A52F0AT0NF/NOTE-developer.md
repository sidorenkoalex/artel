# Записка developer

## Выяснено
- Реализация готова, PLAN.md `ready`. Планка 5/5, долгоживущие 50/50, затронутые модули зелёные.
- Зоны ТЗ/SPEC сверяет `guard.protected_zones` (catalog.py:218, fsm.py:1188) → теперь
  `config.is_protected_zone` (расширение «сам каталог» только для записей `**/<d>/`; AC-5).
- `workspace._exclude_wrapper`: `sparse-checkout list` ≠ нужного → `set --no-cone /* !…`
  (git сам включает worktreeConfig); свой `core.excludesFile` в config.worktree (+ текст глобального
  игнора); `git clean -fdx` по pathspec обвязки. Сбой → причина ensure → `runner.role_cwd` OSError.
- `repo_context.wrapper_paths(ctx)` — действующий список; `RepoContext.agent_wrapper` — сырое поле.
- Мандатные правки тестов: `test_project_protected_paths.py:87`, выборки `artel_only_path` и
  перебор в draft_mr — исключение `config.is_protected_path(e, AGENT_WRAPPER_MARKERS)`.
- Свой тест `tests/test_workspace_wrapper_excludes.py` — мутация проверена (красный).

## Не сработало
- `pytest -n` (xdist) в шаге — все воркеры падают «node down»; гонял последовательно.
- `scripts/guard.py` на файлах tests/ требует frontmatter — гонять только на PLAN.md.

## Где остановился
- Сдано: PLAN.md `ready`, код в worktree незакоммичен (коммитит пульт), карта регенерирована.

## Чего не хватило
- Как `git add -A` ведёт себя в sparse-копии — подсказала записка test_author (код 1 → игнор копии).
