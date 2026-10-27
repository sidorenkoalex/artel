# Записка spec_auditor — 01M5XZ9Z68XE2EKPDHYCAK25KF

## Выяснено
- Проверена версия SPEC 6d25d492. Решение Оператора №2 перенесено, три отклонения прошлого аудита (описание на гейте, повтор черновика, amend-tests) закрыты. Адреса кода верны.
- Код Б2.1а на ветке ещё пуст (`git diff main...task/01m5xz9z68v75…` пуст). Её SPEC читается командой `git show refs/artifacts/01M5XZ9Z68V75VXF5Z66C708T4:tasks/01M5XZ9Z68V75VXF5Z66C708T4/SPEC.md`. В ней `delivery_policy` и целый `mr_assignee`.
- `forge._GitHub` умеет только `pipeline_status`. Значит, у `target-human` с `forge: github` нет `open_mr`, а `gh`-черновик продолжает работать (Е-1).
- Отказ push в `ensure_draft_mr` идёт в `_incident`, то есть в алерт (`github_adapter.py:167-171`). AC-18 алерт не проверяет (В-1).
- Отказ push в `amend-tests` уходит в `_recovery_exit` уже после коммита (`amend.py:826-837`), а `amend.py` вне зон (Г-1).

## Не сработало
- Bash с `;`/`|` требует подтверждения, ls недоступен. Читать нужно через Read; ADR — из worktree, не из корня пульта.

## Где остановился
- SPEC-AUDIT.md: status ready, verdict concerns, 4 отклонения и замечания. guard ок.

## Чего не хватило
- Какие методы реализует `forge._GitHub`, стало видно только при чтении `forge.py:115-200`; SPEC это не называл.
