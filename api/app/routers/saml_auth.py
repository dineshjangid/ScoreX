"""SAML SSO (Azure AD / Entra ID) sign-in, alongside the existing local
username+password login. Only registered when SAML_ENABLED (see
saml_config.py and main.py) — a deployment that hasn't configured SSO
env vars keeps working exactly as before.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.settings import OneLogin_Saml2_Settings

from .. import saml_config
from ..auth import create_session, set_session_cookie, upsert_saml_user

router = APIRouter(prefix="/api/auth/saml", tags=["auth"])


async def _saml_request_dict(request: Request, script_name: str) -> dict[str, Any]:
    # Built from the *configured* public ACS URL rather than trusting
    # request.url, which behind a reverse proxy would otherwise reflect the
    # container-internal host unless proxy headers are perfectly forwarded
    # and trusted — SAML's entity ID / ACS URL matching is strict enough
    # that it's safer to just use the value Azure AD was actually given.
    from urllib.parse import urlparse

    parsed = urlparse(saml_config.saml_settings()["sp"]["assertionConsumerService"]["url"])
    post_data = dict(await request.form()) if request.method == "POST" else {}
    return {
        "https": "on" if parsed.scheme == "https" else "off",
        "http_host": parsed.netloc,
        "script_name": script_name,
        "get_data": dict(request.query_params),
        "post_data": post_data,
    }


@router.get("/login")
async def saml_login(request: Request) -> RedirectResponse:
    req = await _saml_request_dict(request, "/api/auth/saml/login")
    auth = OneLogin_Saml2_Auth(req, saml_config.saml_settings())
    return RedirectResponse(auth.login())


@router.post("/acs")
async def saml_acs(request: Request) -> Response:
    req = await _saml_request_dict(request, "/api/auth/saml/acs")
    auth = OneLogin_Saml2_Auth(req, saml_config.saml_settings())
    auth.process_response()

    errors = auth.get_errors()
    if errors:
        raise HTTPException(status_code=401, detail=f"SAML login failed: {'; '.join(errors)}")
    if not auth.is_authenticated():
        raise HTTPException(status_code=401, detail="SAML authentication failed")

    email = auth.get_nameid()
    if not email:
        raise HTTPException(status_code=401, detail="SAML response did not include a NameID (email)")

    attributes = auth.get_attributes()
    group_ids = attributes.get(saml_config.GROUP_CLAIM_NAME, [])
    role = saml_config.role_from_groups(group_ids)
    if role is None:
        raise HTTPException(
            status_code=403,
            detail="Your account isn't a member of a group authorized for this app. Contact your admin.",
        )

    user_id = upsert_saml_user(email, role)
    token, _ = create_session(user_id)

    redirect = RedirectResponse(url="/", status_code=302)
    set_session_cookie(redirect, token)
    return redirect


@router.get("/metadata")
def saml_metadata() -> Response:
    settings = OneLogin_Saml2_Settings(saml_config.saml_settings(), sp_validation_only=True)
    return Response(content=settings.get_sp_metadata(), media_type="application/xml")
