# Записка spec_auditor — 01M5WDB7F14SQ30QVWJY2XYBG2 (аудит 4, spec_sha cc2c05a7)

## Выяснено
- Все 9 отклонений аудита 3 и ANSWER-1 п. 1–2 внесены в SPEC; факты кода прежние: catalog.py:844/900/918/1024/1031/1038, fsm.py:1016/1037(def)/1067/1070/1403, gitcmd.py:37/86/94/145/164/341/413/441/469.
- Новый класс находки: подставы конфигурации клона закрыты не полностью — `remote.origin.url` не сверяется с `url` записи, `url.*.insteadOf`/`pushInsteadOf`, `core.sshCommand` в config (в argv отказ, в config нет), `core.hooksPath` (хук получает ARTEL_HOSTING_TOKEN, gitcmd.py:160); в env — GIT_DIR/GIT_SSH_COMMAND/GIT_CONFIG_GLOBAL при отказе только GIT_CONFIG_COUNT/KEY/VALUE/PARAMETERS.
- targets.check (targets.py:616) не отвергает неизвестные поля — запись слоя репозитория с новыми полями пройдёт без проверки, если проверка только в merge_local.
- Вердикт: concerns.

## Не сработало
- `ls`, `xargs` в Bash — отказ/подтверждение; только простые grep/sed.

## Где остановился
- SPEC-AUDIT.md записан (status: ready, verdict: concerns, 3 отклонения), guard ок. Шаг завершён.

## Чего не хватило
- Списка тестов, считающих журнал после отправки (для (а) у артели) — не проверено поимённо.
