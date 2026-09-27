"""AC-5: `tests/test_analyst_role.py` проходит на карте, где у роли analyst
стоит `provider: codex`, — подменой карты в прогоне, без правки
`roles.yaml` репозитория.

Подмена — копией дерева кода с другим `roles.yaml`, не правкой файла на
месте: карту читают и `tests/sandbox.py`, и `tests/test_runner_role_model.py`
путём от `__file__` собственного модуля, а правка файла репозитория на
время прогона оставила бы дерево пульта испорченным при любом обрыве.
Имена `analyst` и `codex` — литералы: их называет сам критерий.

Кроме имени провайдера планка ничего в карте не трогает: ярус роли, её
скилы и слот остаются боевыми, локальный слой песочницы — прежним. Ровно
такую карту раздел «Контекст» SPEC называет сегодня красной
(«локальный слой моделей песочницы называет всем ярусам модели Claude,
провайдер роли приходит из боевой карты, и шаг отклоняется отказом
„модель роли не поддерживается CLI“»).

Красен до реализации: прогон воспроизведён 27.09 в копии дерева — падает
`RunAnalystTest::test_run_starts_analyst_when_tz_present` отказом
`runner.py` «модель роли не поддерживается CLI», ровно как описано в SPEC.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import providers  # noqa: E402


class AnalystRoleOnCodexProviderTest(unittest.TestCase):
    """Прогон файла роли analyst на карте с провайдером Codex."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def test_ac5_analyst_role_file_is_green_with_codex_provider(self):
        """Карта исполнителей отличается от боевой одной строкой
        (`provider: codex` у роли analyst); `tests/test_analyst_role.py`
        прогоняется в копии дерева с этой картой и обязан пройти без
        провалов и ошибок.

        Ловит мутацию: фикстура песочницы отдаёт свою карту только тем
        файлам, которые зовут её явным помощником, а `config.ROLES` на
        весь процесс по-прежнему указывает на боевой файл — файлы, которые
        доходят до шага роли, не называя карты вовсе (а
        `tests/test_analyst_role.py` именно такой), снова разрешают
        провайдер роли из боевого `roles.yaml` и краснеют отказом «модель
        роли не поддерживается CLI».
        """
        self.assertIn(
            _util.CODEX, providers.PROVIDERS,
            f"провайдера {_util.CODEX} нет в реестре orchestrator/providers — "
            f"значение поля не было бы допустимым")

        text = _util.real_roles_text()
        mutated = _util.roles_text_with(
            text, {_util.ANALYST: {"provider": _util.CODEX}})
        self.assertNotEqual(mutated, text,
                            "карта не изменилась — сценарий AC-5 не разыгран")
        entries = _util.role_entries(mutated)
        self.assertEqual(entries[_util.ANALYST].get("provider"), _util.CODEX,
                         mutated)
        self.assertEqual(
            {role: entry for role, entry in entries.items()
             if role != _util.ANALYST},
            {role: entry for role, entry in _util.role_entries(text).items()
             if role != _util.ANALYST},
            "подмена задела не только роль analyst — критерий говорит об "
            "одном поле одной роли")
        self.assertEqual(
            _util.real_roles_text(), text,
            f"{_util.ROLES_REL} репозитория изменился — критерий требует "
            f"подмены в прогоне, БЕЗ правки боевого файла")

        code = _util.repo_copy(self.tdir, mutated, name="analyst-codex")
        try:
            result = _util.run_pytest(code, [_util.ANALYST_TEST], timeout=110)
        except subprocess.TimeoutExpired as exc:  # pragma: no cover
            self.fail(f"прогон {_util.ANALYST_TEST} не уложился в отведённое "
                      f"время: {exc}")

        self.assertEqual(_util.failed_nodeids(result.stdout), [],
                         _util.run_report(result))
        self.assertEqual(result.returncode, 0, _util.run_report(result))


if __name__ == "__main__":
    unittest.main()
