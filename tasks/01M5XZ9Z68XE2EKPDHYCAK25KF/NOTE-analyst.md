# Записка аналитика — 01M5XZ9Z68XE2EKPDHYCAK25KF

## Выяснено
- ТЗ = подраздел «Деление» SPEC родителя 01M5XXA2HY73D3WTXDR19Z5SWW; merge_after = часть 1 01M5XZ9Z68V75VXF5Z66C708T4 (Б2.1а).
- Шаг 3 (возврат с гейта SPEC №2): имена Б2.1а — `targets.delivery_policy(entry) -> dict`, столбцы `mr_iid INTEGER`/`mr_url TEXT`, функции store.py Б2.1а (их имён SPEC Б2.1а пока не называет — в нашем SPEC без имён). Обновление описания MR на гейте убрано: описание пишется только при open_mr (черновик — на входе в verifying, draft_mr:false — на гейте); AC-15 переписан. Отказ open_mr(draft) → in_dev, следующий advance повторяет open_mr даже при голове на сервере (AC-21). На пути amend-tests черновой MR не открывается (треб. 6, AC-13).
- SPEC Б2.1а читается: `git show refs/artifacts/01M5XZ9Z68V75VXF5Z66C708T4:tasks/01M5XZ9Z68V75VXF5Z66C708T4/SPEC.md` (каталог документов другой задачи закрыт).
- `gitlab_adapter.EDIT_MR_FIELDS` (:67) = {assignee_id, title}; повтор черновика: `github_adapter.py:238-239` (no-op при голове на сервере), `:252`.

## Не сработало
- `ls` в каталоге другой задачи заблокирован; `ls` в шелле вообще не найден.

## Где остановился
- SPEC правлен, status: ready; guard ок.

## Чего не хватило
- Имён функций store.py для mr_iid/mr_url — в SPEC Б2.1а их нет.
