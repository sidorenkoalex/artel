# Записка spec_auditor — 01M5XZ9Z68V75VXF5Z66C708T4

## Выяснено
- Повторный аудит SPEC bc5bf696 (после возврата с гейта, решения п. 1–8): SPEC-AUDIT.md сдан, verdict concerns, status ready, guard ок.
- Решения гейта перенесены все; прежние находки (mr_assignee, имена, формы отправки, kill в in_dev, amend-tests) закрыты.
- Новые отклонения: форма «толкования» mr_assignee в выдаче delivery_policy не задана (AC-2); треб. 13 «вход в эскалацию только answer/kill» противоречит треб. 17 (реальные пути — fixation.py:239, store.py:1281, budget.py:384); нет строки матрицы на лимит параллельности эпика (auto.py:1168); в tests/test_report.py перечней состояний нет (report.STATE_ORDER = fsm.STATES); «сервер не трогается» vs досылка коммита закрытия kill (cleanup.py:644-645, snapshot.py:298); AC-5..8 не называют вход gitcmd.in_repo.
- Мандата на правку тестов в ANSWER-n по-прежнему нет.

## Не сработало
- Составные bash-команды (`;`, `cd &&` с несколькими grep, grep с -e) требуют подтверждения — работают одиночные команды и Read.

## Где остановился
Готово.

## Чего не хватило
Где kill пишет в сервер помимо уборки ветки: _commit_closing → snapshot.commit_closing → push refs/artifacts.
