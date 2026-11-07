# NOTE-analyst

## Выяснено
- Факты ТЗ сверены с кодом: `PULT_ACTOR_TRAILER` gitcmd.py:544, `pult_message` :585-593, `LOCAL_FIELDS` targets.py:391-411, `_check_delivery` :664, `co_author` :721-727, `_flatten` :849-859, `merge_local(name, entry, source=None)` targets.py:486.
- Второй возврат с гейта SPEC (07.11, 2 решения) закрыт: AC-4 — «две строки» через `targets.merge_local(<имя>, dict)`, прочие через файл слоя, добавлен отказ `"Key:   "` (пробельное значение = пустое, требования 1-2); Контекст — `snapshot.py:281` передаёт `config.DEFAULT_TARGET` (запись артели, в локальном слое запрещена `merge_local`:492), снимки сохраняют Artel-Actor; «существующие тесты зелёные» — требование 7, убрано из «Не входит».

## Не сработало
- Bash с несколькими командами иногда отклоняется правами — читать через Read.

## Где остановился
- SPEC.md status: ready, guard ок. budget_usd 25.

## Чего не хватило
- Ничего.
