# Записка аналитика

## Выяснено
- ТЗ достаточно для SPEC; вопросов батчем не задано.
- Места, перебирающие `refs/artifacts/*` и выводящие из имени ссылки id задачи: `artifact_branch.fetch_all_from_origin` (`:711`, зовут `docs_fetch.py:135`, `workspace._fetch_docs_refs` `:140`), `artifact_cleanup._inventory` (`:50`), `retro_corpus._local_artifact_refs`/`_retro_entry` (`:45`, `:58`), `snapshot._history_pass` (`:343`), `doctor/artifact_branches._origin_artifact_refs` (`:17`, сверка идёт от строк БД), `scripts/plan_appendix_ci.remote_docs_refs`/`docs_ref_for_branch` (`:168`). `doctor/orphans.py` ссылок не перебирает.
- `tasks.start_after` вводит Э2а (01M5TBCY7WTN121S136XP2C6SR, его SPEC требование 11), а promote по ТЗ пишет `start_after` задачи → в `merge_after` добавлен Э2а с обоснованием в SPEC.
- Id эпика — `E` + id пульта (SPEC Э1, требование 2); ссылка — `refs/artifacts/epic-<id>`.

## Не сработало
- `artel.py docs` недоступна роли; SPEC соседей читал `git show refs/artifacts/<id>:tasks/<id>/SPEC.md`.

## Где остановился
- SPEC.md написан (16 требований, AC-1…AC-14, budget 65, монолит — на решение Оператора), `scripts/guard.py` — ок.

## Чего не хватило
- Формы адреса черновика ТЗ не задаёт — выбрана `<id эпика>/<n>`, отмечено в SPEC как выбор аналитика для правки Оператором на гейте.
