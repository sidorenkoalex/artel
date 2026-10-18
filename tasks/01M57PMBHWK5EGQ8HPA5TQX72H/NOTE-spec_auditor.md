# Записка spec_auditor

## Выяснено
- SPEC sha b908af76… (итерация 2) проверен; вердикт concerns, SPEC-AUDIT.md status: ready.
- Решения Оператора 1–8 в SPEC отражены; факты по коду подтвердились (watch.py:303-308, store.advance_notified per-observation, artel.py:1132-1136).
- Отклонения: (1) tasks.target бывает NULL (schema.py:115, project_label.py:79) — треб. 3 считает проекты без нормализации NULL→DEFAULT_TARGET; (2) AC-2 не проверяет строку панели report у алерта target=id задачи; (3) AC-3 не ловит «глобальное окно 10, потом разбивка»; (4) AC-8 не требует эталон литералом до правки.
- safe_text(None) в watch._print_line упал бы — треб. 5 необходимо.
- docs/codebase-map.md входит в config.COMMON_ZONES (config.py:803).

## Не сработало
- `cd …; sed` и составные команды требуют подтверждения — пользовался git grep и Read.

## Где остановился
- Аудит завершён; guard прогнан.

## Чего не хватило
- Знания, что tasks.target nullable при утверждении Оператора «NULL у задач не бывает» — нашёл через schema.py и фикстуру теста плитки.
