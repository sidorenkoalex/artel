# Записка spec_auditor

## Выяснено
- Вердикт concerns, SPEC-AUDIT.md сдан (status: ready), guard ок.
- Главное: SPEC не называет `commit_success_checkpoint` (checkpoint.py:828-911, вызов _commit_worktree_change :895; из runner.py:1931) — штатный путь коммита пультом за developer. ТЗ/SPEC указывают только `_wip_checkpoint` :230-238 (таймаут/авария/pause --now) и `commit_pull_checkpoint` :1531.
- Мелкое: `pult_commit_failed_paths` :1694 и `restore_out_of_bounds_deletions` :555 считают по `_zone_paths` без профиля; AC-4 не различает refusal/skip в project_profile.decide (:143-159).
- Факты SPEC подтверждены: zones.py:285-292 — источник профиля; own_zones добавляется только при непустом _zone_paths (:1770-1772).

## Не сработало
- grep с `cd` и `--include=*.py` в zsh/песочнице — отказ; работают абсолютные пути без glob-флагов.

## Где остановился
- Аудит завершён.

## Чего не хватило
- Перечня всех вызывающих `_commit_worktree_change` в ТЗ/SPEC — нашёлся grep'ом.
