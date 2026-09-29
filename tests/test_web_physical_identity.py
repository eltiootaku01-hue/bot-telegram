# -*- coding: utf-8 -*-
"""Contract tests for the declarative, non-secret Web physical identity source."""

from pathlib import Path
import tempfile
import unittest

from bot_ia.core.physical_resource_authority import PhysicalWebChatResourceAuthority
from bot_ia.core.web_physical_identity import (
    AuthenticationState,
    WebPhysicalIdentity,
    WebPhysicalIdentityConfigError,
    WebPhysicalIdentityRegistry,
    canonicalize_interaction_surface,
)


def _write_config(root: Path, body: str) -> Path:
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    path = config_dir / "runtime.toml"
    path.write_text(body, encoding="utf-8")
    return path


VALID_CONFIG = """
[web_identities.cari_gemini]
provider = "gemini"
principal_identity = "declared-web-principal-cari"
provider_session_identity = "declared-web-session-cari"
canonical_interaction_surface = "https://gemini.google.com/app/"
browser_profile = "./browser_data/cari"
authentication_state = "UNKNOWN"

[web_identity_bindings.cari_gemini]
logical_actor = "cari"
identity_id = "cari_gemini"
"""


class WebPhysicalIdentitySourceTests(unittest.TestCase):
    def test_id01_valid_descriptor(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = WebPhysicalIdentityRegistry.from_toml(
                _write_config(Path(tmp), VALID_CONFIG)
            )
            identity = registry.resolve_binding(
                "cari_gemini",
                expected_provider="gemini",
                expected_logical_actor="cari",
            )
            self.assertEqual(
                "https://gemini.google.com/app",
                identity.canonical_interaction_surface,
            )
            self.assertEqual(
                AuthenticationState.UNKNOWN,
                identity.authentication_state,
            )
            self.assertTrue(identity.physical_resource_id.startswith("pwr-"))

    def test_id02_missing_principal(self):
        body = VALID_CONFIG.replace(
            'principal_identity = "declared-web-principal-cari"',
            'principal_identity = ""',
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(WebPhysicalIdentityConfigError):
                WebPhysicalIdentityRegistry.from_toml(
                    _write_config(Path(tmp), body)
                )

    def test_id03_missing_provider_session(self):
        body = VALID_CONFIG.replace(
            'provider_session_identity = "declared-web-session-cari"',
            'provider_session_identity = ""',
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(WebPhysicalIdentityConfigError):
                WebPhysicalIdentityRegistry.from_toml(
                    _write_config(Path(tmp), body)
                )

    def test_id04_missing_surface(self):
        body = VALID_CONFIG.replace(
            'canonical_interaction_surface = "https://gemini.google.com/app/"',
            'canonical_interaction_surface = ""',
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(WebPhysicalIdentityConfigError):
                WebPhysicalIdentityRegistry.from_toml(
                    _write_config(Path(tmp), body)
                )

    def test_id05_duplicate_identity(self):
        duplicate = VALID_CONFIG.replace(
            "[web_identity_bindings.cari_gemini]",
            """
[web_identities.duplicate]
provider = "gemini"
principal_identity = "declared-web-principal-cari"
provider_session_identity = "declared-web-session-cari"
canonical_interaction_surface = "https://gemini.google.com/app"
browser_profile = "./browser_data/other"
authentication_state = "UNKNOWN"

[web_identity_bindings.cari_gemini]""",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(WebPhysicalIdentityConfigError):
                WebPhysicalIdentityRegistry.from_toml(
                    _write_config(Path(tmp), duplicate)
                )

    def test_id06_different_principal(self):
        first = WebPhysicalIdentity(
            "one",
            "gemini",
            "declared-principal-a",
            "declared-session",
            "https://gemini.google.com/app",
            "./browser_data/a",
        )
        second = WebPhysicalIdentity(
            "two",
            "gemini",
            "declared-principal-b",
            "declared-session",
            "https://gemini.google.com/app",
            "./browser_data/a",
        )
        self.assertNotEqual(
            first.physical_resource_id,
            second.physical_resource_id,
        )

    def test_id07_different_session(self):
        first = WebPhysicalIdentity(
            "one",
            "gemini",
            "declared-principal",
            "declared-session-a",
            "https://gemini.google.com/app",
            "./browser_data/a",
        )
        second = WebPhysicalIdentity(
            "two",
            "gemini",
            "declared-principal",
            "declared-session-b",
            "https://gemini.google.com/app",
            "./browser_data/a",
        )
        self.assertNotEqual(
            first.physical_resource_id,
            second.physical_resource_id,
        )

    def test_id08_different_surface(self):
        first = WebPhysicalIdentity(
            "one",
            "gemini",
            "declared-principal",
            "declared-session",
            "https://gemini.google.com/app",
            "./browser_data/a",
        )
        second = WebPhysicalIdentity(
            "two",
            "gemini",
            "declared-principal",
            "declared-session",
            "https://gemini.google.com/settings",
            "./browser_data/a",
        )
        self.assertNotEqual(
            first.physical_resource_id,
            second.physical_resource_id,
        )

    def test_id09_shared_logical_actors(self):
        body = VALID_CONFIG + """
[web_identity_bindings.sunna_gemini]
logical_actor = "sunna"
identity_id = "cari_gemini"
"""
        with tempfile.TemporaryDirectory() as tmp:
            registry = WebPhysicalIdentityRegistry.from_toml(
                _write_config(Path(tmp), body)
            )
            cari = registry.resolve_binding("cari_gemini")
            sunna = registry.resolve_binding("sunna_gemini")
            self.assertEqual(
                cari.physical_resource_id,
                sunna.physical_resource_id,
            )

    def test_id10_profile_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = WebPhysicalIdentityRegistry.from_toml(
                _write_config(root, VALID_CONFIG)
            ).resolve_binding("cari_gemini")
            self.assertEqual(
                (root / "browser_data/cari").resolve(),
                identity.browser_profile_path(project_root=root),
            )

    def test_id11_gui_binding_contract(self):
        app_source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "gui"
            / "app.py"
        ).read_text(encoding="utf-8")
        for token in (
            "WebPhysicalIdentityRegistry",
            "web_identity_binding",
            "physical_resource_adapter=",
            "identity.descriptor",
            "self._web_physical_authority",
        ):
            self.assertIn(token, app_source)

    def test_id12_unknown_identity_cannot_claim(self):
        authority = PhysicalWebChatResourceAuthority()
        identity = WebPhysicalIdentity(
            "unknown-auth",
            "gemini",
            "declared-principal",
            "declared-session",
            "https://gemini.google.com/app",
            "./browser_data/cari",
            AuthenticationState.UNKNOWN,
        )
        from services.qweb_physical_resource_adapter import (
            QWebPhysicalResourceAdapter,
            QWebPhysicalResourceIdentityError,
        )
        adapter = QWebPhysicalResourceAdapter(
            authority,
            identity.descriptor,
            authentication_state=identity.authentication_state,
        )
        with self.assertRaises(QWebPhysicalResourceIdentityError):
            adapter.claim_resource()

    def test_id13_declared_vs_verified(self):
        declared = WebPhysicalIdentity(
            "declared",
            "gemini",
            "declared-principal",
            "declared-session",
            "https://gemini.google.com/app",
            "./browser_data/cari",
            AuthenticationState.UNKNOWN,
        )
        verified = WebPhysicalIdentity(
            "verified",
            "gemini",
            "declared-principal",
            "declared-session",
            "https://gemini.google.com/app",
            "./browser_data/cari",
            AuthenticationState.VERIFIED,
        )
        self.assertFalse(declared.can_execute_physically)
        self.assertTrue(verified.can_execute_physically)

    def test_id14_canonicalization_stability(self):
        self.assertEqual(
            "https://gemini.google.com/app",
            canonicalize_interaction_surface(
                " HTTPS://GEMINI.GOOGLE.COM:443/app/// "
            ),
        )

    def test_id15_physical_resource_id_determinism(self):
        first = WebPhysicalIdentity(
            "one",
            "gemini",
            "declared-principal",
            "declared-session",
            "https://gemini.google.com/app",
            "./browser_data/a",
        )
        second = WebPhysicalIdentity(
            "two",
            "gemini",
            "declared-principal",
            "declared-session",
            "https://gemini.google.com/app/",
            "./browser_data/other",
        )
        self.assertEqual(
            first.physical_resource_id,
            second.physical_resource_id,
        )
        authority = PhysicalWebChatResourceAuthority()
        left = authority.resolve_resource(
            "gemini",
            "declared-principal",
            "declared-session",
            "https://gemini.google.com/app",
        )
        right = authority.resolve_resource(
            "gemini",
            "declared-principal",
            "declared-session",
            "https://gemini.google.com/app/",
        )
        self.assertEqual(
            left.physical_resource_id,
            right.physical_resource_id,
        )


if __name__ == "__main__":
    unittest.main()
