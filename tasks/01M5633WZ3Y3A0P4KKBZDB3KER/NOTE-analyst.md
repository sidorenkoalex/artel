# NOTE analyst — 01M5633WZ3Y3A0P4KKBZDB3KER

## Выяснено
- Правило: `scripts/guard.py:2612-2614` `_allowed_import_tops()` (stdlib + orchestrator/scripts/tests + stack.THIRD_PARTY_EXCEPTIONS), применение `_import_signs` `:2709-2730`, вызывается из `long_lived_sign_hits` `:2785` без параметра проекта. Текст отказа — `_SIGN_EXPLANATIONS[SIGN_FOREIGN_IMPORT]` `:2597-2598`.
- Три рубежа зовут `guard.long_lived_errors_from_files(..., network_addresses=is_artel)`: tests_writing.py:351, 470; preflight.py:186, 203 (флаг из :259); amend.py:512-515. Профиль доступен во всех трёх (`project_profile.Profile`, есть `workdir`).
- `Profile.workdir` есть (project_profile.py:78); поле профиля для перечня импортов отсутствует — нужно добавить в `targets.PROFILE_FIELDS` (targets.py:43-60), а значение для sled — в targets.yaml (защищённый путь, no_paths artel, targets.yaml:36).
- sled: uv + `backend/uv.lock`, `backend/pyproject.toml` (оба в no_paths sled). Имена дистрибутивов ≠ имена импорта (pyjwt→jwt, python-jose→jose, python-dotenv→dotenv) — вывод перечня из lock/pyproject ненадёжен.
- Признаки п.2: «закрытое имя» (`_CODE_PACKAGES` guard.py:2605, :2727) у внешнего проекта не срабатывает на `from src._x`; «закрытый атрибут» освобождает только stdlib/tests (:2692-2706) — у внешнего проекта поймает `app._x` (применим); `sys.path` применим как есть; «git-модуль» (`_GIT_MODULES`) — про модули пульта, у внешнего не срабатывает.

## Не сработало
- Чтение клона sled (`.artel/projects/sled/repo`) — вне рабочего каталога, нужно подтверждение; не читал.

## Где остановился
- Выбор источника перечня требует правок вне зон ТЗ (targets.py) и защищённого targets.yaml → QUESTIONS.md, SPEC не писал.

## Чего не хватило
- Явного разрешения расширить зоны на `orchestrator/targets.py` (ТЗ: «эскалация до SPEC»).
