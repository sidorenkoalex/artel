# Записка spec_auditor

## Выяснено
- Факты SPEC о коде подтверждены: targets.py:29-30, :283, :299; forge.py:163, :184; catalog.py:856; runner.py:184; fsm.py:1794 и auto.py:1038 зовут runner.refuse_unsupported_project.
- ANSWER-*.md в каталоге документов задачи нет — мандата на правку сторожа А0 в этой задаче пока нет.
- Тесты, подменяющие SUPPORTED_*: mr_delivery/mr_sync используют gitlab+target-human (после SUPPORTED_PAIRS поддержано); awaiting_* — github+target-human, но до unsupported_reason не доходят (zone_lock/cleanup). mr_sync «other» = gitlab+operator, только ghost-задачи + mr-sync, не run/auto/approve.
- rewrite_flow gitlab+operator — advance/pull_main, не гейтятся поддержкой.

## Не сработало
- zsh: `ls` не найден в PATH шага; `--include` grep не работает — git grep.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок. Отклонения: (1) нет ANSWER с мандатом/матрицей/независимой проверкой; (2) условия (б) не перечисляют сохраняемые утверждения ac2–ac8 — мандат на весь файл; (3) AC-4 только запрещает подстроку для `_hosting`, не требует, что текст называет.

## Чего не хватило
- Нет.
