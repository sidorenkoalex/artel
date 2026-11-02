# Записка spec_auditor

## Выяснено
- Аудит SPEC sha 77ccd3d4 (итерация 3). Решения гейта №1 (1–6) и №2 (1–9) отражены. Ссылки SPEC на код верны.
- Находки (вердикт concerns, 6 пунктов): В1 — pull-main меняет голову внутри визита verifying (pull_main.py:61-107), AC на это нет; В2 — потолок CI для проекта с verify не покрыт (test_verifying_ceiling.py — без verify); А1 — _epic_view (auto.py:1308) _WAITING только по состоянию, требование 5 запрещает нужную правку; А2 — актор перехода verify-ok не назван, _child_holds ждёт actor=operator (auto.py:1207-1222); В3 — waiting_on при CI в ожидании у проекта с verify не проверен; В4 — verify: [] без AC.

## Не сработало
- `ls` в Bash отказан; работают git ls-files, grep, sed.

## Где остановился
- SPEC-AUDIT.md записан (status ready, verdict concerns), guard — ок. Шаг завершён.

## Чего не хватило
- Как надзор эпика различает «ждёт Оператора» и «держит после остановки» — auto.py:1225-1312 (_child_holds, _epic_view).
