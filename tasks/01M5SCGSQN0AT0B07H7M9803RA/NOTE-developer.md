# Записка developer — 01M5SCGSQN0AT0B07H7M9803RA

## Выяснено
- Требования 1–14 реализованы (незакоммичено в worktree): targets.py (local_path, layers, merge_local, cache_dir,
  check(..., source)), projects.cmd_targets_migrate, artel.py диспетчер+usage, doctor/cli.targets_local_layer_check,
  checkpoint.MainCopyWatch.local_layer_digest, test_lint, config.TARGETS_LOCAL_REL, правка
  tests/test_acceptance_suite_profile.py::call (треб. 14), карта регенерирована.
- Долгоживущие тесты задачи + test_acceptance_suite_profile: 67 passed.
- 29 существующих тестов красные по одной причине: RealGitSandbox сеет плоский targets.yaml с artel в
  root/.artel/targets.yaml, ProjectAreaSandbox (tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py:171)
  перенаправляет TARGETS на root/targets.yaml → посеянный файл = локальный слой → отказ «запись артели».
  Однострочная правка `(self.root / ".artel" / "targets.yaml").unlink(missing_ok=True)` после
  targets_patcher.start() даёт 31 passed (проверено и откачено).

## Не сработало
- `ls`, `$VAR`, перенаправление в /tmp в Bash шага требуют подтверждения — работать через git/Read.
- pytest -n 4 в шаге падает (node down) — гонять последовательно.

## Где остановился
- PLAN.md status: escalate — ждёт мандата Оператора на правку ProjectAreaSandbox.setUp (вариант (а)).
  После ANSWER: применить строку из PLAN «Эскалация», прогнать project_area + invariants::MainCopyGit…,
  поставить status: ready.

## Чего не хватило
- Пересечение адреса локального слоя с раскладкой RealGitSandbox (tests/sandbox.py:1925-1931) — не было в SPEC/записке test_author.
