"""Сторож зеркала: поле `no_paths` записи `artel` реального `targets.yaml`
по множеству записей равно `config.PROTECTED_PATHS`.

Группа: долгоживущий
Красен до реализации: test_ac13_artel_no_paths_mirrors_protected_paths — у записи `artel` в `targets.yaml` 9 записей `no_paths` против 18 записей `config.PROTECTED_PATHS`; зеленеет на дереве с наложенным приложением PLAN к `targets.yaml` (CI ветки накладывает его перед тестами), на дереве ветки без приложения красен по построению (SPEC, «Не входит»). test_ac13_divergence_report_names_each_entry_and_side зелёный с рождения — проверяет вывод самого сторожа на подложенном расхождении.

Сторож — метод `check_mirror`: читает запись артели штатным
`orchestrator.targets.target` по `config.TARGETS` (у реального запуска — файл
репозитория) и падает, называя каждую расходящуюся запись и сторону, где её
нет. Второй метод подкладывает `targets.yaml` во временный каталог со
случайным расхождением и проверяет текст провала сторожа.

Провалидировано на рабочей копии с временно наложенным образцом
приложения (`no_paths` записи `artel` = `config.PROTECTED_PATHS`; правка
откачена) — оба метода зелёные.

Зерно печатается и входит в текст провала.
"""
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config, targets

MISSING_IN_TARGETS = "нет в no_paths записи artel targets.yaml"
MISSING_IN_CONFIG = "нет в config.PROTECTED_PATHS"

ENTRY = """targets:
  {name}:
    forge: github
    url: http://localhost/artel
    base: main
    token_slot: artel-token
    no_paths: [{no_paths}]
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""


class NoPathsMirrorTest(unittest.TestCase):

    def check_mirror(self) -> None:
        """Сторож: множество `no_paths` записи артели равно
        `config.PROTECTED_PATHS`; иначе провал с перечнем расхождений."""
        no_paths = targets.target(config.DEFAULT_TARGET)["no_paths"]
        declared, protected = set(no_paths), set(config.PROTECTED_PATHS)
        lines = ([f"{entry}: {MISSING_IN_TARGETS}"
                  for entry in sorted(protected - declared)]
                 + [f"{entry}: {MISSING_IN_CONFIG}"
                    for entry in sorted(declared - protected)])
        self.assertEqual(lines, [], "поле no_paths записи artel расходится с "
                         "config.PROTECTED_PATHS:\n" + "\n".join(lines))

    def test_ac13_artel_no_paths_mirrors_protected_paths(self):
        """`no_paths` записи `artel` реального `targets.yaml` по множеству записей равно `config.PROTECTED_PATHS`.

        Сценарий: сторож читает реальный `targets.yaml` репозитория и
        сверяет множества; при расхождении провал называет каждую запись.

        Ловит мутацию: в `config.PROTECTED_PATHS` добавлен защищённый путь, а
        зеркало `no_paths` записи `artel` не обновлено (или наоборот) —
        сторож краснеет, называя запись; приложение к `targets.yaml`
        оставило часть записей пульта вне `no_paths`.
        """
        self.check_mirror()

    def test_ac13_divergence_report_names_each_entry_and_side(self):
        """При расхождении сторож красный и называет каждую расходящуюся запись со стороной, где её нет.

        Сценарий: `targets.yaml` во временном каталоге (подмена
        `config.TARGETS`) — запись `artel`, чьё `no_paths` = записи
        `config.PROTECTED_PATHS` без одной-трёх случайных плюс одна-две
        лишние `zz…/`. Сторож падает `AssertionError`; текст провала несёт
        каждую пропущенную запись в строке с пометкой «нет в no_paths…» и
        каждую лишнюю в строке с пометкой «нет в config.PROTECTED_PATHS».
        Затем `no_paths` = ровно `config.PROTECTED_PATHS` в случайном порядке
        — сторож зелёный.

        Ловит мутацию: сторож сверяет только число записей — расхождение
        «одна убрана, одна добавлена» проходит; сторож называет одну
        (первую) расходящуюся запись или не называет сторону, где её нет;
        сторож сверяет списки с порядком — перестановка краснеет.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "targets.yaml"
        protected = list(config.PROTECTED_PATHS)
        dropped = rng.sample(protected, rng.randint(1, min(3, len(protected))))
        extra = [f"zz{rng.randrange(10 ** 6)}x{i}/" for i in range(rng.randint(1, 2))]
        kept = [p for p in protected if p not in dropped] + extra
        rng.shuffle(kept)
        path.write_text(ENTRY.format(name=config.DEFAULT_TARGET,
                                     no_paths=", ".join(kept)), encoding="utf-8")
        with mock.patch.object(config, "TARGETS", path):
            with self.assertRaises(AssertionError) as caught:
                self.check_mirror()
        report = str(caught.exception).splitlines()
        for entry, side in ([(e, MISSING_IN_TARGETS) for e in dropped]
                            + [(e, MISSING_IN_CONFIG) for e in extra]):
            self.assertTrue([line for line in report
                             if line.startswith(f"{entry}: ") and side in line],
                            f"зерно: {seed}; {entry} ({side}) не назван:\n"
                            + "\n".join(report))

        shuffled = list(protected)
        rng.shuffle(shuffled)
        path.write_text(ENTRY.format(name=config.DEFAULT_TARGET,
                                     no_paths=", ".join(shuffled)), encoding="utf-8")
        with mock.patch.object(config, "TARGETS", path):
            self.check_mirror()


if __name__ == "__main__":
    unittest.main()
