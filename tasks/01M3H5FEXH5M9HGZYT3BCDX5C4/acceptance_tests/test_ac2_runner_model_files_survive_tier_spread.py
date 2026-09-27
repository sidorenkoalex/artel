"""AC-2: та же подменённая карта исполнителей, что у AC-1, и прогоны
`tests/test_runner_role_model.py` и
`tests/test_runner_model_preflight.py` — каждый файл отдельным прогоном,
как того требует формулировка «ноль провалов и ноль ошибок в каждом
файле».

Оба файла строят карту исполнителей тем же `_roles_yaml_text`, который
правит разработчик, и оба пишут свой локальный слой моделей
(`ModelFlagJournalTest.set_tier_model`, `_StepSandbox.set_model`) — то
есть попадают в ту же зону правки, что и файл AC-1.

Зелёный с рождения: сегодня оба файла проходят и на разведённых ярусах —
их сценарии доходят до шага роли `developer`, чей ярус они задают сами, и
чужая нерезолвящаяся цепочка их пока не задевает (`stack.check_stack`
в песочнице `TmpRootTest` подменён заглушкой, предполёт отключён). Тест
сторожит, чтобы покрытие всех ярусов, которое разработчик добавляет ради
AC-1, не сломало эти два файла: правится общий для них
`_roles_yaml_text`, и обратная зависимость «прогон краснеет от чужого
яруса» может приехать сюда вместе с починкой.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import models  # noqa: E402

TARGETS = (_util.ROLE_MODEL_TEST, _util.PREFLIGHT_TEST)


class RunnerModelFilesTierSpreadTest(unittest.TestCase):
    """Прогоны файлов модели шага на карте с разведёнными ярусами."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def test_ac2_runner_model_and_preflight_files_are_green_each(self):
        """Карта исполнителей та же, что у AC-1 (одна agent-роль, не
        названная этими файлами, на другом ярусе `models.TIERS`): каждый
        из двух файлов прогоняется отдельно и обязан пройти без провалов
        и ошибок.

        Ловит мутацию: покрытие всех ярусов внесено в `_roles_yaml_text`
        так, что ярус НАЗВАННОЙ тестом роли перестаёт быть тем, который
        тест просил (например, перебор `TIERS` затирает вставленный
        `model_tier` последним значением перечня) — модель шага
        разрешается не в ту, и сценарии обоих файлов («ярус не задан —
        отказ», «модель ниже минимума CLI», argv шага) начинают проверять
        не свой предмет.
        """
        text, role, other_tier, base_tier = _util.spread_roles_text(TARGETS)

        tiers = _util.agent_roles(text)
        self.assertNotEqual(other_tier, base_tier)
        self.assertIn(other_tier, models.TIERS)
        self.assertEqual(tiers.get(role), other_tier, tiers)
        self.assertEqual({t for name, t in tiers.items() if name != role},
                         {base_tier}, tiers)

        code = _util.repo_copy(self.tdir, text)

        for target in TARGETS:
            with self.subTest(target=target):
                result = _util.run_pytest(code, [target], timeout=90)
                self.assertEqual(_util.failed_nodeids(result.stdout), [],
                                 _util.run_report(result))
                self.assertEqual(result.returncode, 0,
                                 _util.run_report(result))


if __name__ == "__main__":
    unittest.main()