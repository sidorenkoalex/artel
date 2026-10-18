## Выяснено
- Код: `_SignalDeferral` (canary.py ~2300) + 3 вызова release() в `_drive_in_clone`; требования 1–9 выполнены.
- Модули: 34 passed; plank-run: 5 passed; мутации AC-3 (SIG_IGN) и AC-4 (без release в except BaseException) — обе красные.
- Карта свежая (отличие только в built_at_sha).
- Наблюдение (не в реестре): release() восстанавливает обработчики циклом; живой сигнал посреди цикла оставляет SIGINT на `_defer`.

## Не сработало
- `scripts/codebase_map.py --help` перегенерировал карту вместо справки; вернул `git checkout`.

## Где остановился
- REVIEW.md iteration 1, approved, реестр пуст.

## Чего не хватило
- Ничего существенного.
