"""AC-3: мутации кода пульта, которые ловили изменённые методы файла
full_suite_limit_runs до правки, ловятся ими и после неё.

Группа: разовый
Зелёный с рождения: в main данные методов не тронуты и каждая мутация ниже краснит свой метод; планка держит, что подъём пределов (C, N) и `hold` правкой задачи эту чувствительность не потерял.

Каждая мутация вносится текстовой заменой в КОПИЮ рабочей копии (`.git`,
каталог задач не копируются) — в файлы пульта, которые задача не правит
(`orchestrator/acceptance.py`, `fsm_merge_gate.py`, `suite_run.py`,
`project_profile.py`); в копии гоняется один метод файла
full_suite_limit_runs ветки. Метод `test_ac5_*` гоняет копию пульта,
скопированную из корня дерева прогона, — поэтому мутация в копии дерева,
а не подмена в процессе. Копии гоняются одновременно: предел всего прогона
планки на гейте — `config.ACCEPTANCE_TIMEOUT_SEC` (300 с), а мутант метода
идёт десятки секунд.

Мутация «поймана» — метод красный: pytest вернул ненулевой код и итог
«failed», причём упавшая строка метода (`--tb=short`) — не утверждение о
старте пробника (`self.events("start")`):
краснота по необорванному старту — нестабильность, которую чинит задача, а
не ответ на мутацию. Метод, не уложившийся во внутренний предел pytest
(`-o timeout`), тоже красный — так мутанта `test_ac4_*` (прогон до конца
пробника) видит любой прогон набора с пределом теста.

Валидация стабом (11.10): пределы всех шести методов подняты (C 50–60 и N
20–25; C 20–25 без N; N 20–25 у `test_ac5_*`) — все семь мутантов красные,
тест зелёный за ~80 с.
"""
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

# Внутренний предел pytest метода-мутанта и общий срок ожидания всех копий;
# оба меньше предела теста планки (120 с).
INNER_TIMEOUT = 85
WAIT_ALL_SEC = 108

ACCEPTANCE = "orchestrator/acceptance.py"
MERGE_GATE = "orchestrator/fsm_merge_gate.py"
SUITE_RUN = "orchestrator/suite_run.py"
PROFILE = "orchestrator/project_profile.py"

# (метод, имя мутации, [(файл, было, стало)], дописка в конец файла или None)
MUTATIONS = [
    ("ac3_cut", "гейт мержа берёт config.FULL_SUITE_TIMEOUT_SEC, а не подполе профиля", [
        (ACCEPTANCE,
         '    limit = project_profile.full_suite_limit(target)\n'
         '    run_kwargs = {"limit": limit} if limit[1] != "config" else {}\n',
         '    limit = (config.FULL_SUITE_TIMEOUT_SEC, "config")\n'
         '    run_kwargs = {}\n'),
        (MERGE_GATE,
         'seconds, source = project_profile.full_suite_limit(ctx.target)\n',
         'seconds, source = config.FULL_SUITE_TIMEOUT_SEC, "config"\n'),
    ]),
    ("ac4", "предел без подполя взят при импорте (константа модуля)", [
        (ACCEPTANCE,
         '    limit = limit or (config.FULL_SUITE_TIMEOUT_SEC, "config")\n'
         '    with _machine_lock(None, limit) as holder:\n',
         '    limit = limit or (_LIMIT_AT_IMPORT, "config")\n'
         '    with _machine_lock(None, limit) as holder:\n'),
        (ACCEPTANCE, None,
         '\n\n_LIMIT_AT_IMPORT = config.FULL_SUITE_TIMEOUT_SEC\n'),
    ]),
    ("ac5", "фоновый прогон suite-run берёт config.FULL_SUITE_TIMEOUT_SEC", [
        (SUITE_RUN,
         '    limit = project_profile.full_suite_limit(target)\n'
         '    targets = ("tests",)\n',
         '    limit = (config.FULL_SUITE_TIMEOUT_SEC, "config")\n'
         '    targets = ("tests",)\n'),
    ]),
    ("ac5", "отчёт о таймауте suite-run печатает значение config, а не N", [
        (SUITE_RUN,
         '    seconds, source = limit or (config.FULL_SUITE_TIMEOUT_SEC, "config")\n'
         '    title = {\n',
         '    seconds, source = (config.FULL_SUITE_TIMEOUT_SEC, "config")\n'
         '    title = {\n'),
    ]),
    ("ac6_profile", "источник в текст таймаута всегда «config»", [
        (ACCEPTANCE,
         '            f"(источник: {source})")\n',
         '            f"(источник: config)")\n'),
        (MERGE_GATE,
         'f"(источник: {source}; "',
         'f"(источник: config; "'),
    ]),
    ("ac6_config", "без подполя источник назван профилем проекта", [
        (PROFILE,
         '    return config.FULL_SUITE_TIMEOUT_SEC, "config"\n',
         '    return config.FULL_SUITE_TIMEOUT_SEC, f"профиль тестов проекта {target}"\n'),
    ]),
    ("ac7", "источник вставлен в начало текста таймаута вместо дописывания", [
        (ACCEPTANCE,
         '    return (f"прогон полного набора tests/ превысил "\n',
         '    return (f"(источник: {source}) прогон полного набора tests/ превысил "\n'),
    ]),
]


def apply_mutation(tree: Path, edits: list) -> None:
    for rel, before, after in edits:
        path = tree / rel
        text = path.read_text(encoding="utf-8")
        if before is None:
            text += after
        else:
            count = text.count(before)
            if count != 1:
                raise AssertionError(
                    f"мишень мутации в {rel} найдена {count} раз(а), нужна "
                    f"ровно одна — код пульта разошёлся с main:\n{before}")
            text = text.replace(before, after)
        path.write_text(text, encoding="utf-8")


FAILED_LINE = re.compile(r":\d+: in test_\w+\n\s*(.+)")


def caught(code, out: str) -> bool:
    """Метод красный, и упал не на утверждении о старте пробника."""
    if code in (None, 0):
        return False
    if " failed" not in out:
        return False
    if "Timeout" in out:
        return True
    lines = FAILED_LINE.findall(out)
    return bool(lines) and not any("events(" in line and "start" in line
                                   for line in lines)


class MutationsStillCaughtTest(unittest.TestCase):

    def test_ac3_each_mutation_reddens_its_changed_method(self):
        """Каждая мутация списка краснит свой изменённый метод на ветке.

        Сценарий: изменённые методы — ac3_cut, `test_ac4_*`, `test_ac5_*`
        всегда, `test_ac6_*`/`test_ac7_*` — если правка их тронула; для
        каждого — копия дерева с мутацией из AC-3 и прогон метода в ней.
        Все прогоны обязаны покраснеть не на утверждении о старте пробника.

        Ловит мутацию: правка задачи подняла пределы так, что мутант больше
        не виден — например, C метода `test_ac4_*` взят равным 900 (значению
        config в main, которое мутант берёт при импорте) или N ac3_cut равен
        C — прогон мутанта зелёный, тест покраснеет с именем мутации.
        """
        changed = _util.changed_limit_methods()
        chosen = [m for m in MUTATIONS if m[0] in changed]
        self.assertTrue(chosen, "нет ни одного изменённого метода")
        with tempfile.TemporaryDirectory(prefix="artel-ac3-") as tmp:
            runs = []
            for index, (key, title, edits) in enumerate(chosen):
                tree = _util.copy_tree(Path(tmp) / f"m{index}")
                apply_mutation(tree, edits)
                cls, name = _util.LIMIT_METHODS[key]
                argv = _util.pytest_argv(f"{_util.LIMIT_FILE}::{cls}::{name}",
                                         INNER_TIMEOUT)
                runs.append((key, title, _util.start(argv, tree)))
            deadline = time.monotonic() + WAIT_ALL_SEC
            results = [(key, title, *_util.finish(proc, deadline))
                       for key, title, proc in runs]
        missed = [f"{key} — «{title}»: код {code}\n{_util.tail(out, 2500)}"
                  for key, title, code, out in results if not caught(code, out)]
        self.assertFalse(missed, "мутация не краснит изменённый метод:\n\n"
                         + "\n\n".join(missed))


if __name__ == "__main__":
    unittest.main()
