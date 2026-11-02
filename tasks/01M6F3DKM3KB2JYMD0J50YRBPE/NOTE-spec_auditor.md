# Записка spec_auditor

## Выяснено
- Вердикт concerns по SPEC sha 4ea239fe. Главное: verify-ok при всех отметках ведёт в review без условия «CI зелёный + verifying_gate пройден» (fsm_advance.py:463-480); auto опрашивает verifying бесконечно, если потолок снят (auto.py:1080,1093-1100,528), и держит lease (auto.py:672) — auto.py только чтение по ТЗ.
- «Общего правила долгого ожидания Оператора» в коде нет (алерт attention только из auto_stop, alerts.py:36-42).
- Разделы description/policy/machine — только локальный слой targets (targets.py:338, _flatten :786).
- Обход FsmTest.commands без профиля verify у песочницы — пустой (test_invariants.py:412-415).

## Не сработало
- Bash с `cd …;` и `ls` отказаны песочницей — только абсолютные пути и grep/Read.

## Где остановился
- SPEC-AUDIT.md записан, status ready; guard — ок. Шаг завершён.

## Чего не хватило
- Дольше всего искал, есть ли алерт долгого ожидания гейта — не нашёл ни в config, ни в alerts.
