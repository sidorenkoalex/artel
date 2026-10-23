# Записка spec_auditor — 01M5KNXGEMBAC1QRNHY3KC14JR

## Выяснено
- Ссылки SPEC о коде подтвердились: canary_pool.py:41/:73/:82, cli.py:146, config.py:414/:654, canary.py:516, claude.py:61/:63, codex.py:315/:316, docs/stack.md:577, tests/test_doctor_canary_pool.py:161.
- Логи Codex пишутся отрендеренными строками (`codex.py:904` `_call_line`, `agent_log.py:166-174`), 1г работает для обоих провайдеров.
- `git grep` образца AC-9 по orchestrator/scripts/skills/templates/tests на 906f0732 пуст.
- В окружении роли HOME = `config.ROLE_HOME` (`claude.py:223`): `Path.home()` там — дом роли, а не Оператора, поэтому 1а (абсолютная форма) и 1б в этом режиме проверяют не тот путь.
- `base.py:110` не сокращает пути с CANARY_POOL_DIRNAME — абсолютные пути пула в строке вызова остаются.

## Не сработало
- —

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready; 6 отклонений, все в разделе «Вердикт».

## Чего не хватило
- Как задаётся HOME роли и что с ним происходит в doctor из-под роли — нашёл через `providers/claude.py:223`, а не через runner.role_env.
