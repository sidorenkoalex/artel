# Записка spec_auditor 01M4VC31NFCS6JZ0VE8HNJ7FYM

## Выяснено
- Третий визит (spec_sha 78a7664d…): Т-1 (промежуточные записи в AC-1..AC-3),
  Т-2 (нет ключа = NULL, треб. 4 и AC-9), Ф-1 (адрес :2232 в
  `_run_task_in_ephemeral_clone`) — закрыты.
- Факты подтверждены заново: models.py:1128/1136/1149-1151/1174/1196-1197,
  :996-998; canary.py:291, :1848, :2232, :2328-2343, :2416-2424, :2565-2581,
  :2645, :2762; store.py:1442-1468 (`_ensure_canary_tables`, add_column);
  config.py:805; catalog.py:667/:670; auto.py:400; canary_drive.py:67-87;
  store.py:852 — set_state пишет `state -> X`.
- Новая находка (concerns, Е-1): эскалации пульта идут тем же `state -> escalated`
  из текущего состояния — `budget.enforce_budget` (budget.py:300, деталь «бюджет
  исчерпан»), fixation.py:248. По правилу «роль = состояние» бюджетная эскалация
  в `spec_audit`/`spec_writing` засчитается как эскалация spec_auditor/analyst:
  analyst-ловушка + бюджет в spec_audit — чистый (на main — не чистый, 2 > 1).
  ТЗ запрещает разбор детали — решать Оператору.
- Мелкое (В-1): AC-1 «строка, записанная `_run_one_task`» — уровень подмены
  в тесте может навязать место вычисления ролей.

## Не сработало
- Bash: составные команды с `;`, `$n`, циклы — отклоняются; только одиночные grep/sed.

## Где остановился
- SPEC-AUDIT.md написан: status ready, verdict concerns (Е-1, В-1).

## Чего не хватило
- Перечень всех мест `set_state(..., "escalated")` пульта — искал grep'ом по `"escalated", "fsm"`.
