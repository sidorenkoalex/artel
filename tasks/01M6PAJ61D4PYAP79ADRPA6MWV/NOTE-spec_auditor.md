# Записка аудитора SPEC 01M6PAJ61D4PYAP79ADRPA6MWV

## Выяснено
- Второй визит аудита: SPEC 94e9bb21… внёс решения второго круга гейта 1–6; все шесть пунктов прошлого вердикта (e06c94d3) закрыты по содержанию.
- Канал умолчания `command` (targets.load, :258-272) выполним: profile_of/decide берут запись из targets.target → load. Но profile_of (:190) и project_profile.decide (:378) режут поля единственного компонента по PROFILE_FIELDS — compose_* должны попасть в PROFILE_FIELDS+PROFILE_OPTIONAL либо идти через _with_component_fields (в зонах).
- _report_run (acceptance.py:806) — общий вход two_sided (:359) и outcome_integrity (:445, :736, только чтение); предел передают вызывающие → слагаемое compose_up_down_sec надо добавлять внутри acceptance.
- in_outcome_bounds (advance_gates/acceptance.py:213) — только компоненты: гейт исходов для test_profile compose вне границы (как pytest-own).
- Существующих тестов, ломающихся от новых полей/раннера, не нашёл (перечни берутся динамически или локальными константами).
- Новые пробелы: пределы `up`/`kill`/`down` не заданы; `down` после провала `up` не задан; канал предела 60 с `config` для теста не назван; `o: bind` буквально — обход `o: "bind,ro"`/`rbind` при type≠none; volumes_from.

## Не сработало
- ls/echo/command -v в Bash отклоняются; docker на машине шага нет — опыт Compose невозможен.

## Где остановился
- SPEC-AUDIT.md сдан для spec_sha 94e9bb21…: verdict concerns, status ready, guard ок. Пять пунктов: пределы up/kill/down; down после провала up; канал предела 60 с config; `o: bind` буквально + volumes_from; мелкое (AC-10 только компонент, AC-17 формулировка, порядок DOCKER_HOST).

## Чего не хватило
- Docker в окружении шага.
