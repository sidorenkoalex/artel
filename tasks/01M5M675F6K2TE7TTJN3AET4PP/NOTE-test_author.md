# Записка test_author — 01M5M675F6K2TE7TTJN3AET4PP

## Выяснено
- AC-1..AC-3 — долгоживущий tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py; AC-4..AC-7 — долгоживущий tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py; AC-8 — разовый acceptance_tests/test_ac8_retention_doc.py (docs/retention.md через CODE_ROOT из _pult).
- Сбой и шпион git — подмена `gitcmd.git` (в долгоживущем файле через `pin.gitcmd`/`prune.gitcmd`, импорт orchestrator.gitcmd guard запрещает); `gitcmd.in_repo` = git("-C", repo, …), поэтому подмена ловит и in_repo, и прямой git главной копии. Репозиторий вызова — `-C <путь>` либо config.ROOT.
- prune-песочница: RealGitSandbox с ARTEL_CLONE_IS_ROOT=False, клон артели — свой репозиторий в config.PROJECTS/artel/repo; рабочие копии — настоящий `git worktree add --detach` в config.WORKTREES.
- Сбой rmtree — chmod 0o500 подкаталога `sub` бесхозного каталога.
- Валидация стабом: все 8 методов долгоживущих файлов зелёные на стабе pin/prune; мутации «пропуск только при обоих сбоях» и «N = все строки вывода» дают красный; AC-8 зелёный на временной правке документа (стаб поймал регистр «Бесхозные» — сравнение теперь без учёта регистра). Стабы откачены `git checkout`.
- До реализации: AC-1, AC-2, AC-4, AC-5, AC-6, AC-8 красные; AC-3 и оба AC-7 зелёные (держат существующее поведение).
- preflight: все проверки пройдены.

## Не сработало
- ls/cat в Bash к каталогу документов запрещены — читать Read.

## Где остановился
- Шаг завершён. docs/codebase-map.md не регенерировал: правка вне tests/ у test_author откатывается пультом — регенерация за разработчиком.

## Чего не хватило
- —
