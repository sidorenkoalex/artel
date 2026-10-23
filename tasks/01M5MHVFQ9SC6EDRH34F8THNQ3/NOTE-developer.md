## Выяснено
- `store.db_readonly(path=None, *, rows=True)` добавлена перед `db_usable` в orchestrator/store.py; пять мест зовут её через атрибут модуля `store.` (иначе шпион AC-6 не видит).
- Импорт `sqlite3` нигде не удалён: в preflight — аннотация, в knowledge_cards/suite_run/скрипте — `sqlite3.Error`.
- В скрипте добавлен `from orchestrator import config, store`; переменная `uri` убрана; вызов остался внутри `try … except sqlite3.Error`.
- Прогнаны: оба долгоживущих файла задачи + все тесты из списка SPEC «Не входит» + test_01m4tvbt9zcrqdy669qv3s95ma_reference.py — 104 passed. Карта регенерирована. guard PLAN — ок.

## Не сработало
- Ничего.

## Где остановился
- Шаг сделан, PLAN status: ready.

## Чего не хватило
- Ничего.
