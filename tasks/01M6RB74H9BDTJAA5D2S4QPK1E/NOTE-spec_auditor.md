# Записка spec_auditor

## Выяснено
- Второй визит (spec_sha 0f70a2a1). Факты SPEC о коде подтвердились: gitcmd.py:559-582, :625-660 (name != username -> отказ, :656), projects.py:889-893, :986, project_checks.py:53-66, catalog.py:856.
- Мандатные тесты (pair_support:161, unsupported_project:399) при нынешнем делении fail/warn не краснеют: песочница отдаёт refused_gitlab_transport (tests/sandbox.py:668, :692) -> token_user с причиной -> warn -> new заводит задачу.
- tests/test_01m6ezxvfgh5z2876xwmqg35fp_gitlab_doctor_lines.py:813/:819 держат точный список строк github и 8 строк артели — новую строку нельзя класть в _names.
- doctor_probe expiry_line_names (:262-270) не ломается: /user без адреса -> warn в обоих прогонах.
- В projects.py уже есть сверка блока целиком: _target_set_block_mismatches (:900).

## Не сработало
- —

## Где остановился
- SPEC-AUDIT.md сдан: concerns, ready.

## Чего не хватило
- Как песочница отвечает на GET /user без подмены — нашёл в tests/sandbox.py:665-696 не сразу.
