# Записка analyst — 01M5XZSKK8GZTECA2KWAFHE029

## Выяснено
- Шаг 2: возврат с гейта SPEC (К1, пп. 1–9). Правится существующий SPEC.md,
  вопросов нет.
- К1 уточняет П1: статус `failed` без права падать + в разобранном отчёте
  failed/error → красный (`--accept-red` принимает); `failed` без failed/error
  или без разобранного отчёта, `canceled`/иной не-success → «неизвестно».
  Читаю «красный» только для статуса `failed`; иной не-success — «неизвестно»
  при любом отчёте.
- Свежесть у артели — `origin/{config.MAIN_BRANCH}` (acceptance.py:3436-3439);
  для `ci`/`both` — `origin/<base>` записи (`targets.FIELDS["base"]`, targets.py:37).
- `checks_local` — в `acceptance_suite` после `_acceptance_suite_run`
  (acceptance.py:3380-3407); незелёный итог не перекрашивается.
- Автогейт: fsm_autogate.py:426 (подстрока «принят итог CI»).
- `_last_attempt` — gitlab_adapter.py:449-457; forge.py:16 импортирует targets.

## Не сработало
- `$VAR` и `for` в шелле отказаны — только абсолютные пути.

## Где остановился
- SPEC.md поправлен по всем пунктам возврата (К1, 1–9): требования 1–2,
  AC-1, AC-7…AC-10, новые AC-14 (значение full_suite) и AC-15 (checks_local),
  четыре строки матрицы (+checks_local, +автогейт), «Не входит» (состав
  ci_job, Б2.3), строка gitlab_adapter.py:449-457. guard — «ок», status: ready,
  budget 45 без изменений.
- Красный задаю только для статусов `success`/`failed` с failed/error в
  отчёте; `canceled` с failed в отчёте — «неизвестно» (К1 называет красным
  только `failed`).

## Чего не хватило
- Ничего.
