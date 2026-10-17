# Записка spec_auditor

## Выяснено
- Факты SPEC о ci.py/ci_rerun.py/fsm_merge_gate.py/acceptance.py/github_adapter.py сверены — номера строк верны.
- `ci.gh` ставит `env` только при непустом токене (ci.py:65-71); у записи без `token_slot` токена нет (gitcmd.py:133-135) — GH_REPO там надо ставить отдельно, AC-2 этого не ловит.
- Подмены `ci.gh` без **kwargs: tests/test_invariants.py:326 (защищён), tests/test_ci_status.py:160, tests/test_main_ci_line.py:62; `trigger_rerun` `lambda branch:` — tests/test_merge_gate_ci_wait.py:82.

## Не сработало
- нет

## Где остановился
- SPEC-AUDIT.md написан, вердикт concerns.

## Чего не хватило
- Нет помощника «путь клона → url проекта» в ci.py; механизм отображения SPEC оставляет разработчику.
