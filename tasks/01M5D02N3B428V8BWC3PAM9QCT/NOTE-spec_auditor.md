# Записка spec_auditor — 01M5D02N3B428V8BWC3PAM9QCT (аудит №2, spec_sha 1608215d)

## Выяснено
- О-1…О-4 гейта SPEC №1 в SPEC перенесены (AC-14…AC-16, AC-6, AC-10, тр. 2 по `in_outcome_bounds`, «Не входит» о пробеле по краям).
- `decide` даёт профиль только записи из одного компонента (`repo_context.py:161-163`), `with_tools` ставит `component`/`from_components` (`project_profile.py:276-284`).
- Н-1: прежний `_covered` у артели ПРИНИМАЕТ pytest-идентификатор с `tests/…py` (`_TEST_REF_RE`, `mandate.py:314`) — AC-14 «отказана» неточен.
- Н-2: форма идентификатора в «Чем покрыто после» не задана.
- Вердикт: concerns.

## Не сработало
- `ls` в шелле недоступен; читать через sed/grep из рабочего каталога.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Как профиль задачи получает `from_components`: через `with_tools` в `decide`, не через `Profile.from_values`.
