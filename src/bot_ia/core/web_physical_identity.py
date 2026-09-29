# -*- coding: utf-8 -*-
"""Declarative, non-secret physical Web identity registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import tomllib
from urllib.parse import urlsplit, urlunsplit

from .physical_resource_authority import PhysicalResourceDescriptor


class WebPhysicalIdentityConfigError(ValueError):
    """Raised when declarative Web physical identity is invalid."""


class AuthenticationState(str, Enum):
    DECLARED = "DECLARED"
    VERIFIED = "VERIFIED"
    UNKNOWN = "UNKNOWN"
    INVALID = "INVALID"


SUPPORTED_WEB_PROVIDERS = frozenset(
    {
        "gemini",
        "chatgpt",
        "copilot",
        "grok_claude",
    }
)


def canonicalize_interaction_surface(value: str) -> str:
    """Normalize a stable web application surface without runtime state."""
    if not isinstance(value, str):
        raise WebPhysicalIdentityConfigError(
            "CANONICAL_SURFACE_MUST_BE_STRING"
        )
    raw = value.strip()
    if not raw:
        raise WebPhysicalIdentityConfigError("CANONICAL_SURFACE_REQUIRED")

    parsed = urlsplit(raw)
    scheme = parsed.scheme.strip().lower()
    if scheme not in {"http", "https"}:
        raise WebPhysicalIdentityConfigError(
            "CANONICAL_SURFACE_SCHEME_UNSUPPORTED"
        )
    if parsed.username or parsed.password:
        raise WebPhysicalIdentityConfigError(
            "CANONICAL_SURFACE_MUST_NOT_CONTAIN_CREDENTIALS"
        )
    if parsed.query or parsed.fragment:
        raise WebPhysicalIdentityConfigError(
            "CANONICAL_SURFACE_MUST_NOT_CONTAIN_QUERY_OR_FRAGMENT"
        )

    hostname = parsed.hostname
    if not hostname:
        raise WebPhysicalIdentityConfigError(
            "CANONICAL_SURFACE_HOST_REQUIRED"
        )
    try:
        port = parsed.port
    except ValueError as error:
        raise WebPhysicalIdentityConfigError(
            "CANONICAL_SURFACE_PORT_INVALID"
        ) from error

    hostname = hostname.casefold()
    netloc = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        netloc = f"{netloc}:{port}"

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"

    return urlunsplit((scheme, netloc, path, "", ""))


def _normalize_id(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise WebPhysicalIdentityConfigError(
            f"{field_name.upper()}_MUST_BE_STRING"
        )
    normalized = " ".join(value.strip().split()).casefold()
    if not normalized:
        raise WebPhysicalIdentityConfigError(
            f"{field_name.upper()}_REQUIRED"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class WebPhysicalIdentity:
    """A non-secret declaration of one physical Web principal/session."""

    identity_id: str
    provider: str
    principal_identity: str
    provider_session_identity: str
    canonical_interaction_surface: str
    browser_profile: str
    authentication_state: AuthenticationState = AuthenticationState.UNKNOWN

    def __post_init__(self) -> None:
        identity_id = _normalize_id(self.identity_id, "identity_id")
        provider = _normalize_id(self.provider, "provider")
        principal = _normalize_id(
            self.principal_identity,
            "principal_identity",
        )
        session = _normalize_id(
            self.provider_session_identity,
            "provider_session_identity",
        )
        surface = canonicalize_interaction_surface(
            self.canonical_interaction_surface
        )
        browser_profile = str(self.browser_profile).strip()
        if not browser_profile:
            raise WebPhysicalIdentityConfigError(
                "BROWSER_PROFILE_REQUIRED"
            )
        if provider not in SUPPORTED_WEB_PROVIDERS:
            raise WebPhysicalIdentityConfigError(
                f"WEB_PROVIDER_UNSUPPORTED:{provider}"
            )

        try:
            authentication_state = (
                self.authentication_state
                if isinstance(self.authentication_state, AuthenticationState)
                else AuthenticationState(str(self.authentication_state))
            )
        except ValueError as error:
            raise WebPhysicalIdentityConfigError(
                "AUTHENTICATION_STATE_INVALID"
            ) from error

        object.__setattr__(self, "identity_id", identity_id)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "principal_identity", principal)
        object.__setattr__(
            self,
            "provider_session_identity",
            session,
        )
        object.__setattr__(
            self,
            "canonical_interaction_surface",
            surface,
        )
        object.__setattr__(self, "browser_profile", browser_profile)
        object.__setattr__(
            self,
            "authentication_state",
            authentication_state,
        )

    @property
    def descriptor(self) -> PhysicalResourceDescriptor:
        """Resolve the Authority descriptor from the declared identity tuple."""
        return PhysicalResourceDescriptor.resolve(
            provider=self.provider,
            authenticated_account_identity=self.principal_identity,
            session_identity=self.provider_session_identity,
            canonical_interaction_surface=self.canonical_interaction_surface,
        )

    @property
    def physical_resource_id(self) -> str:
        return self.descriptor.physical_resource_id

    @property
    def can_execute_physically(self) -> bool:
        return self.authentication_state is AuthenticationState.VERIFIED

    def browser_profile_path(self, *, project_root: Path) -> Path:
        path = Path(self.browser_profile).expanduser()
        if path.is_absolute():
            return path.resolve()
        return (project_root / path).resolve()


@dataclass(frozen=True, slots=True)
class WebPhysicalIdentityBinding:
    """Map a logical actor to an explicit physical identity definition."""

    binding_id: str
    logical_actor_id: str
    identity_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "binding_id",
            _normalize_id(self.binding_id, "binding_id"),
        )
        object.__setattr__(
            self,
            "logical_actor_id",
            _normalize_id(self.logical_actor_id, "logical_actor_id"),
        )
        object.__setattr__(
            self,
            "identity_id",
            _normalize_id(self.identity_id, "identity_id"),
        )


class WebPhysicalIdentityRegistry:
    """Load and resolve non-secret Web physical identity declarations."""

    def __init__(
        self,
        identities: dict[str, WebPhysicalIdentity],
        bindings: dict[str, WebPhysicalIdentityBinding],
    ) -> None:
        self._identities = dict(identities)
        self._bindings = dict(bindings)

    @classmethod
    def from_toml(cls, path: Path) -> "WebPhysicalIdentityRegistry":
        if not path.is_file():
            raise FileNotFoundError(
                f"web physical identity configuration not found: {path}"
            )

        with path.open("rb") as handle:
            data = tomllib.load(handle)

        identities_raw = data.get("web_identities", {})
        bindings_raw = data.get("web_identity_bindings", {})
        if not isinstance(identities_raw, dict):
            raise WebPhysicalIdentityConfigError(
                "WEB_IDENTITIES_SECTION_INVALID"
            )
        if not isinstance(bindings_raw, dict):
            raise WebPhysicalIdentityConfigError(
                "WEB_IDENTITY_BINDINGS_SECTION_INVALID"
            )

        identities: dict[str, WebPhysicalIdentity] = {}
        ids_by_canonical_tuple: dict[str, str] = {}
        for identity_id, raw in identities_raw.items():
            if not isinstance(raw, dict):
                raise WebPhysicalIdentityConfigError(
                    f"WEB_IDENTITY_INVALID:{identity_id}"
                )
            identity = cls._parse_identity(str(identity_id), raw)
            physical_id = identity.physical_resource_id
            previous = ids_by_canonical_tuple.get(physical_id)
            if previous is not None and previous != identity.identity_id:
                raise WebPhysicalIdentityConfigError(
                    "DUPLICATE_PHYSICAL_IDENTITY:"
                    f"{previous},{identity.identity_id}"
                )
            ids_by_canonical_tuple[physical_id] = identity.identity_id
            identities[identity.identity_id] = identity

        bindings: dict[str, WebPhysicalIdentityBinding] = {}
        for binding_id, raw in bindings_raw.items():
            if not isinstance(raw, dict):
                raise WebPhysicalIdentityConfigError(
                    f"WEB_IDENTITY_BINDING_INVALID:{binding_id}"
                )
            binding = WebPhysicalIdentityBinding(
                binding_id=str(binding_id),
                logical_actor_id=str(raw.get("logical_actor", "")),
                identity_id=str(raw.get("identity_id", "")),
            )
            if binding.identity_id not in identities:
                raise WebPhysicalIdentityConfigError(
                    "BINDING_REFERENCES_UNKNOWN_IDENTITY:"
                    f"{binding.binding_id}:{binding.identity_id}"
                )
            bindings[binding.binding_id] = binding

        return cls(identities, bindings)

    @staticmethod
    def _parse_identity(
        identity_id: str,
        raw: dict[str, object],
    ) -> WebPhysicalIdentity:
        state_raw = str(
            raw.get(
                "authentication_state",
                AuthenticationState.UNKNOWN.value,
            )
        ).strip().upper()
        try:
            authentication_state = AuthenticationState(state_raw)
        except ValueError as error:
            raise WebPhysicalIdentityConfigError(
                f"AUTHENTICATION_STATE_INVALID:{identity_id}"
            ) from error

        if authentication_state in {
            AuthenticationState.VERIFIED,
            AuthenticationState.INVALID,
        }:
            raise WebPhysicalIdentityConfigError(
                "RUNTIME_AUTHENTICATION_STATE_REQUIRED:"
                f"{identity_id}:{authentication_state.value}"
            )

        return WebPhysicalIdentity(
            identity_id=identity_id,
            provider=str(raw.get("provider", "")),
            principal_identity=str(raw.get("principal_identity", "")),
            provider_session_identity=str(
                raw.get("provider_session_identity", "")
            ),
            canonical_interaction_surface=str(
                raw.get("canonical_interaction_surface", "")
            ),
            browser_profile=str(raw.get("browser_profile", "")),
            authentication_state=authentication_state,
        )

    def get_identity(self, identity_id: str) -> WebPhysicalIdentity:
        key = _normalize_id(identity_id, "identity_id")
        try:
            return self._identities[key]
        except KeyError as error:
            raise WebPhysicalIdentityConfigError(
                f"UNKNOWN_WEB_PHYSICAL_IDENTITY:{key}"
            ) from error

    def resolve_binding(
        self,
        binding_id: str,
        *,
        expected_provider: str | None = None,
        expected_logical_actor: str | None = None,
    ) -> WebPhysicalIdentity:
        key = _normalize_id(binding_id, "binding_id")
        try:
            binding = self._bindings[key]
        except KeyError as error:
            raise WebPhysicalIdentityConfigError(
                f"UNKNOWN_WEB_IDENTITY_BINDING:{key}"
            ) from error

        if (
            expected_logical_actor is not None
            and binding.logical_actor_id
            != _normalize_id(expected_logical_actor, "logical_actor_id")
        ):
            raise WebPhysicalIdentityConfigError(
                "LOGICAL_ACTOR_BINDING_MISMATCH"
            )

        identity = self.get_identity(binding.identity_id)
        if expected_provider is not None:
            provider = _normalize_id(expected_provider, "provider")
            if identity.provider != provider:
                raise WebPhysicalIdentityConfigError(
                    "WEB_IDENTITY_PROVIDER_MISMATCH:"
                    f"{identity.provider}!={provider}"
                )
        return identity


__all__ = [
    "AuthenticationState",
    "SUPPORTED_WEB_PROVIDERS",
    "WebPhysicalIdentity",
    "WebPhysicalIdentityBinding",
    "WebPhysicalIdentityConfigError",
    "WebPhysicalIdentityRegistry",
    "canonicalize_interaction_surface",
]
