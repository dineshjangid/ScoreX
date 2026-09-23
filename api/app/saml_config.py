"""SAML SSO configuration, entirely driven by environment variables so the
same image works whether SSO is configured or not — see DEPLOY.md for what
each variable means and how to get it from Azure AD (Entra ID).

Role is derived from the IdP's group claim rather than stored/edited in
this app: SAML_GROUP_<ROLE>_ID holds the Azure AD group Object ID for each
role, and whichever configured group the user belongs to (most-privileged
first) becomes their role on every login.
"""
from __future__ import annotations

import os
from typing import Any

SAML_ENABLED = bool(os.environ.get("SAML_IDP_ENTITY_ID"))

# Most-privileged first: if a user is in more than one mapped group, the
# highest-privilege role wins rather than being ambiguous.
ROLE_PRIORITY = ["approver", "validator", "analyst"]

GROUP_CLAIM_NAME = os.environ.get(
    "SAML_GROUP_ATTRIBUTE", "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"
)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set — SAML SSO is misconfigured. See DEPLOY.md.")
    return value


def saml_settings() -> dict[str, Any]:
    return {
        "strict": True,
        "debug": os.environ.get("SAML_DEBUG", "false").lower() == "true",
        "sp": {
            "entityId": _require_env("SAML_SP_ENTITY_ID"),
            "assertionConsumerService": {
                "url": _require_env("SAML_SP_ACS_URL"),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        },
        "idp": {
            "entityId": _require_env("SAML_IDP_ENTITY_ID"),
            "singleSignOnService": {
                "url": _require_env("SAML_IDP_SSO_URL"),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": _require_env("SAML_IDP_X509_CERT"),
        },
        "security": {
            # Azure AD signs assertions by default; the SP doesn't need its
            # own certificate unless your IdP is configured to require
            # signed AuthnRequests or encrypted assertions.
            "wantAssertionsSigned": True,
            "authnRequestsSigned": False,
            "wantMessagesSigned": False,
        },
    }


def role_from_groups(group_ids: list[str]) -> str | None:
    """The highest-privilege role whose configured Azure AD group Object ID
    appears in the user's group claim, or None if none match (caller
    decides whether that means "reject" or "fall back to a default")."""
    for role in ROLE_PRIORITY:
        configured_id = os.environ.get(f"SAML_GROUP_{role.upper()}_ID")
        if configured_id and configured_id in group_ids:
            return role
    return os.environ.get("SAML_DEFAULT_ROLE") or None
