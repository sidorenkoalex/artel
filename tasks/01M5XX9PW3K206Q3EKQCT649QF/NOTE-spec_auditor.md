# Записка spec_auditor — 01M5XX9PW3K206Q3EKQCT649QF

## Выяснено
- Ссылки SPEC на код в целом верны; смещения: `Profile` — project_profile.py:66 (не :65), `_component_value_error` — targets.py:1207 (не :1206), вызов гейта на мерже — обёртка `_outcome_integrity_merge_gate` fsm_merge_gate.py:1389, её вызов :1517.
- `compare` (outcome_integrity.py:185-217) НЕ даёт находки на «зелёный в базе → красный в голове»: это делают `_rerun`/`_redness` (BROKEN). SPEC тр. 5 говорит обратное.
- «Неизвестно» полного набора = `FULL_SUITE_NOT_STARTED` + `UNKNOWN_PREFIX` (acceptance.py:384); только его `approve --accept-red` не принимает (fsm.py:1573-1588). `components_full_suite` ставит «неизвестно» раньше красного (acceptance.py:3343-3345, :3358) — SPEC тр. 3 переворачивает («красный старше неизвестно»).
- Гейт исходов: `_component_key` нужен выписке головы (outcome_integrity.py:813-826, :933), `_replacement_findings` без третьей выписки бросает `_Prepare` (:753-756); `in_outcome_bounds` требует `report` (advance_gates/acceptance.py:213-218).
- В forge нет чтения влитых MR по коммиту — кандидаты только через родителей git.
- Путь CI артели в `_acceptance_suite_run` требует равенства дерева гейта (с приложениями PLAN) и головы и свежести (acceptance.py:3424-3440); для режима `ci` SPEC это не задаёт.

## Не сработало
- Bash с `$W`/`cd … &&` и составными командами требует подтверждения — абсолютные пути, по одной команде.

## Где остановился
- SPEC-AUDIT.md написан, вердикт fail; guard прогнан.

## Чего не хватило
- Нет карточки «как approve --accept-red отличает неизвестно от красного» — искал через fsm.py:1573 и acceptance.is_unknown.
