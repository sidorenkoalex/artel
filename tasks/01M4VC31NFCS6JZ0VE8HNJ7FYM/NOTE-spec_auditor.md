# Записка spec_auditor 01M4VC31NFCS6JZ0VE8HNJ7FYM

## Выяснено
- Второй визит (spec_sha 1c21d1d6…): все четыре отклонения прошлого аудита
  (О-1 источник `spec_writing` по умолчанию, О-2 литерал `unknown`, О-3 вычисление
  пультом из `steps`, О-4 прочие условия чистоты для строк с ролями) в SPEC закрыты.
- Факты SPEC подтверждены: models.py:1128/1136/1174, :996-998; canary.py:291,
  :1848, :1867, :2330-2343, :2416, :2645, :2762; store.py:1442; config.py:805;
  catalog.py:667/:670; auto.py:400; canary_drive.py:67-87.
- Неточность: canary.py:2232 `steps = result["steps"]` — в `_run_task_in_ephemeral_clone`
  (def :2146), не в `_run_one_task` (def :2504); steps возвращаются в `_run_one_task` :2565.
- Новые находки (concerns): фикстуры AC-1..AC-3 без промежуточных записей журнала —
  мутация «роль по непосредственно предыдущей записи» проходит приёмку;
  `tests/test_model_sets.py:22-28` `canary_row` — dict без ключа `escalation_roles`,
  `row["escalation_roles"]` уронит KeyError в долгоживущих тестах, SPEC молчит.

## Не сработало
- `ls`, `awk`, конвейеры с `;`/`|` в Bash отклоняются — только одиночные grep/sed/find.

## Где остановился
- SPEC-AUDIT.md написан (status ready, verdict concerns: Т-1, Т-2, Ф-1), guard ок.

## Чего не хватило
- Где в журнале клона промежуточные записи между `state -> spec_audit` и `state -> escalated` — по докстрингу canary.py:1840 («agent run …» пишет cmd_run).
