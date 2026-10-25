# Записка developer — 01M5SCGSQN0AT0B07H7M9803RA

## Выяснено
- Требования 1–14 реализованы и закоммичены пультом (0366c1c8).
- По ANSWER-2 (вариант (а)) в `ProjectAreaSandbox.setUp`
  (tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py:175) добавлена одна строка
  `(self.root / ".artel" / "targets.yaml").unlink(missing_ok=True)`. Больше в файле ничего не менялось.
- После правки: project_area + invariants::MainCopyGit… + acceptance_suite_profile + 4 долгоживущих
  файла задачи — 98 passed; tests/test_invariants.py целиком — 84 passed.
- Карта перегенерирована (изменился только built_at_sha).

## Не сработало
- `ls`, `$VAR`, перенаправление в /tmp в Bash шага требуют подтверждения — работать через git/Read.
- pytest -n 4 в шаге падает (node down) — гонять последовательно.

## Где остановился
- PLAN.md status: ready, раздел «Эскалация» снят, добавлен шаг 8. Guard: ок.
- ANSWER-2 требует, чтобы сессия при Операторе сверила дифф файла до approve на merge_gate.

## Чего не хватило
- Пересечение адреса локального слоя с раскладкой RealGitSandbox (tests/sandbox.py:1925-1931) — не было в SPEC/записке test_author.
