"""AC-3 (SPEC 01M3H3K73XBMJMD0EPXZX6HYY9): обе половины выбранного
решения стоят на месте — ключ окружения оболочки присутствует и в
конфигурации курируемого дома, и в параметрах команды шага Codex; файл
дома роли присутствует в референсе `docs/reference/role-home/codex/` и
проверяется сверкой дома роли.

Зелёный с рождения: критерий условный («если решение задаётся ключом… если
решение использует файл…») и требует сохранить симметрию половин для ЛЮБОГО
решения — сегодняшние пары конфига и команды сходятся, а сверка дома роли
уже смотрит на каждый файл референса; тест ломается ровно тогда, когда
новая половина решения появляется только в одной из них.

Обе проверки написаны от ПЕРЕЧНЯ, а не от имени ключа: планка не знает,
какой именно ключ окружения оболочки выберет PLAN (SPEC требование 1
оставляет способ на этап PLAN), и утверждает то, что критерий утверждает
про любой из них.
"""
import os
import shutil
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import doctor  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402

from _step_env import ProviderStepEnvSandbox, as_config_text  # noqa: E402

#: Префикс ключей курируемого конфига, которым в команде шага отвечает не
#: `-c`-пара, а флаг выключения функции (`--disable <имя>`).
FEATURES_PREFIX = "features."
DISABLE_FLAG = "--disable"
OVERRIDE_FLAG = "-c"


def _values_comparable(*values):
    """Значения половин сравнимы буквально. Абсолютный путь — нет:
    рантайм-адрес (дом роли, каталог пульта) курируемым файлом
    репозитория статически не выражается, и требовать от половин
    побайтового совпадения такого значения критерий не может — он требует,
    чтобы КЛЮЧ стоял в обеих половинах."""
    return not any(isinstance(value, str) and os.path.isabs(value)
                   for value in values)


class CodexSolutionHalvesTest(ProviderStepEnvSandbox):

    def command_overrides(self):
        """Пары `-c ключ=значение` команды шага Codex."""
        cmd = self.step_command(codex_provider.CLI_NAME)
        pairs = {}
        for flag, item in zip(cmd, cmd[1:]):
            if flag == OVERRIDE_FLAG and "=" in item:
                key, _, value = item.partition("=")
                pairs[key] = value
        return pairs

    def command_disabled_features(self):
        """Функции, выключенные флагами команды шага Codex."""
        cmd = self.step_command(codex_provider.CLI_NAME)
        return {item for flag, item in zip(cmd, cmd[1:])
                if flag == DISABLE_FLAG}

    def test_ac3_every_config_key_stands_in_the_step_command_too(self):
        """Каждый ключ курируемого конфига дома роли стоит и в параметрах
        команды шага Codex — `-c`-парой с тем же значением либо флагом
        выключения функции.

        Ловит мутацию: ключ решения дописан только в курируемый
        `config.toml` (дом роли эфемерен, ADR-0005 п.3) — на пульте, где
        `.artel/home` потерян или развёрнут не до конца, шаг идёт без него,
        и половина решения молча исчезает.
        """
        overrides = self.command_overrides()
        disabled = self.command_disabled_features()

        for key, value in sorted(self.curated_config().items()):
            with self.subTest(key=key):
                if key.startswith(FEATURES_PREFIX) and value is False:
                    self.assertIn(key[len(FEATURES_PREFIX):], disabled,
                                  f"{key} выключен только конфигом дома роли")
                    continue
                self.assertIn(key, overrides,
                              f"{key} стоит только в конфиге дома роли")
                expected = as_config_text(value)
                if expected is not None and _values_comparable(
                        expected, overrides[key]):
                    self.assertEqual(expected, overrides[key],
                                     f"значения половин {key} разошлись")

    def test_ac3_every_step_command_override_stands_in_the_curated_config_too(self):
        """Обратная половина: каждая `-c`-пара команды шага и каждая
        выключенная флагом функция стоят и в курируемом конфиге дома роли с
        тем же значением.

        Ловит мутацию: ключ решения дописан только в команду шага —
        курируемый дом роли (и его референс, который Оператор разворачивает
        руками) о нём не знает, и `doctor` сверкой дома роли молчит о
        расхождении, которого не видит.
        """
        config_pairs = self.curated_config()

        for key, value in sorted(self.command_overrides().items()):
            with self.subTest(override=key):
                self.assertIn(key, config_pairs,
                              f"{key} стоит только в команде шага")
                expected = as_config_text(config_pairs[key])
                if expected is not None and _values_comparable(expected, value):
                    self.assertEqual(expected, value,
                                     f"значения половин {key} разошлись")

        for feature in sorted(self.command_disabled_features()):
            with self.subTest(feature=feature):
                self.assertIs(False, config_pairs.get(f"{FEATURES_PREFIX}{feature}"),
                              f"функция {feature} выключена только командой шага")

    def test_ac3_every_reference_file_is_checked_by_the_role_home_check(self):
        """Каждый файл референса дома роли `codex` — предмет сверки дома
        роли: развёрнутый из референса слой даёт `ok`, а пропажа ЛЮБОГО из
        файлов (в том числе файла решения, который PLAN может добавить)
        делает строку жёлтой и называет этот файл.

        Ловит мутацию: сверка смотрит на фиксированный перечень имён или
        только на верхний уровень каталога — файл дома роли, которым
        держится паритет окружения, пропадает из развёрнутого слоя молча,
        и `doctor` остаётся зелёным при шаге, который снова видит системный
        интерпретатор.
        """
        reference = self.reference_dir()
        deployed = self.deployed_home()
        files = sorted(p for p in reference.rglob("*") if p.is_file())
        self.assertTrue(files, f"референс пуст: {reference}")

        self.assertEqual("ok", doctor.check_codex_role_home().status,
                         "развёрнутый из референса слой обязан совпадать")

        for path in files:
            rel = path.relative_to(reference)
            with self.subTest(file=str(rel)):
                counterpart = deployed / rel
                counterpart.unlink()
                try:
                    check = doctor.check_codex_role_home()
                finally:
                    shutil.copy2(path, counterpart)
                self.assertEqual("warn", check.status, check.detail)
                self.assertIn(str(rel), check.detail)


if __name__ == "__main__":
    unittest.main()
