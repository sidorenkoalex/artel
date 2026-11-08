# NOTE-reviewer (iteration 1)

## Выяснено
- Диф соответствует SPEC по требованиям 1–9; ссылок на `suite_run._POLL_SEC` нет (grep).
- Планка 8 passed; suite_run файл 26 passed за 177 с серийно; poll_step + mutation_run_flags 43 passed.
- Временная мутация ac21 (Popen фона B перед отказом по замку) — LockTest красный; код возвращён.
- Карта свежая (отличие только built_at_sha).
- ac24 лог базы строится из вывода запуска (`launch`), не из `run.json` — наблюдение для Оператора (указание 3), не замечание.

## Не сработало
- `scripts/codebase_map.py --help` перегенерирует карту, а не печатает справку — откатил `git checkout -- docs/codebase-map.md`.

## Где остановился
- REVIEW.md записан: approved, реестр пуст.

## Чего не хватило
- Режима проверки свежести карты без записи.
