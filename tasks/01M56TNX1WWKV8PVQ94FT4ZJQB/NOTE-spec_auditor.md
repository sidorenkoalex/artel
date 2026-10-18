# Записка spec_auditor — 01M56TNX1WWKV8PVQ94FT4ZJQB

## Выяснено
- Визит 2, SPEC sha 2f8d2e1c. Решения Оператора пп.1–6 перенесены в SPEC полностью; ссылки 142, 294-313, 316-337, 441-457, 447-449, _journal_pass 1236-1239, invariants.md:68, config.py:758-764 сверены — верны.
- БЛОКЕР: `docs/invariants.md` стоит в `zones:` SPEC. Гейт SPEC отказывает approve по защищённой зоне: `orchestrator/fsm.py:1068-1086` (`_spec_protected_zones_refusal`), вызов `fsm.py:1143-1147`; `guard.protected_zones([...зоны SPEC])` → `['docs/invariants.md']`. Путь надо убрать из zones и назвать в «Материалы»/«Не входит» (иначе — неклассифицированный путь).
- Прочее (concerns): «имя-метка» в AC-10 не литерал; алиас импорта `as`, аннотированное присваивание, модульный вызов в try/except не названы ни в требованиях, ни в «Не входит»; AC-8 смена только tests/marks.py не покрыта.
- Вердикт: fail (approve на гейте откажет механически).

## Не сработало
- `$?` в bash-команде отклоняется (simple_expansion) — без него.

## Где остановился
- SPEC-AUDIT.md переписан, guard прогнан.

## Чего не хватило
- Что гейт SPEC отказывает по защищённым путям в zones — нашёл по `PROTECTED_ZONE_REFUSAL` в guard.py:4169 → fsm.py:1068.
