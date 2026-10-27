# NOTE-spec_auditor

## Выяснено
- SPEC (sha 39e1ee7f…) — дословный перенос подраздела «GitLab В1.1» SPEC родителя (refs/artifacts/01M5XX9PW3K206Q3EKQCT649QF); требования 1–4, 7 и AC-1…AC-13 совпадают.
- Факты о коде подтверждены: acceptance.py:3414 `_acceptance_suite_run`, три условия 3421-3440, локальный откат 3449-3457, `components_full_suite` порядок 3358-3359, fsm.py:1573-1582, fsm_autogate.py:426, targets.py:95/988/1207, project_profile.py:66/434; `with_tools` (project_profile.py:418-431) ведёт и запись из одного компонента через `_with_component_fields`.
- Свежесть у артели — `origin/config.MAIN_BRANCH` ("main", acceptance.py:3438-3439), а SPEC/ANSWER-2 в.2 требуют `origin/<base>` проекта; AC-9 этого не закрепляет.
- `checks_local` (acceptance.py:3388-3411) — после любого источника; ни AC, ни матрица не держат его в режиме `ci`.
- Вердикт: concerns.

## Не сработало
- grep с `$W`/`cd … ;` — песочница требует абсолютных путей без переменных.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Где взять базу проекта для свежести: `targets.FIELDS["base"]` (targets.py:37), не config.MAIN_BRANCH.
