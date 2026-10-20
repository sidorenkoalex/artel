# Записка spec_auditor — 01M5DDTVZEA40ZB9BHEH4YDEE7

## Выяснено
- Визит 2 (spec_sha f1b546bf): все 9 решений гейта SPEC №1 отражены в SPEC; факты сходятся с кодом.
- Документное отставание: pull.py:778-785 возвращает Fresh() без подтяжки на КАЖДОМ заходе; pull-main только в verifying (pull_main.py:64). Значит «сбой подготовки + повтори approve» при документном отставании — бессрочный отказ (Д-1).
- diff_base = merge-base с refs/remotes/origin/main (gitcmd.py:533); _origin_main_sha (fsm_merge_gate.py:150) это отслеживание не обновляет — базы in_dev и мержа могут разойтись, доказательство AC-4 тогда не срабатывает (Д-2).
- Многокомпонентная запись вне границы и в two_sided: from_components ставит только with_tools при одном компоненте (project_profile.py:276).
- Тест чисел PASSED_ACTION сверяет подмножеством (tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:1796).

## Где остановился
SPEC-AUDIT.md написан, вердикт concerns (Д-1 существенно, Д-2, Д-3 мелкие).

## Чего не хватило
Поведения сверки свежести при документном отставании на повторных заходах (pull.evaluate) — пришлось читать pull.py.
