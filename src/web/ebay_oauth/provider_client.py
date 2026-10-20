import base64
import http.client
import json
import re
from urllib.parse import urlencode
from xml.etree import ElementTree

from django.conf import settings
from django.views.decorators.debug import sensitive_variables

from .configuration import SCOPES, configuration
from .rejected import OAuthRejected

GET_USER_BODY = ('<?xml version="1.0" encoding="utf-8"?>'
                 '<GetUserRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
                 '<OutputSelector>User.UserID</OutputSelector></GetUserRequest>')


class ProviderClient:
    """Fixed-origin, bounded transport; only OAuth issuance and GetUser are allowed."""

    @sensitive_variables()
    def _request(self, method, path, body, headers):
        allowed = method == "POST" and (
            path == "/identity/v1/oauth2/token"
            or (path == "/ws/api.dll" and headers.get("X-EBAY-API-CALL-NAME") == "GetUser"
                and body == GET_USER_BODY)
        )
        if not allowed:
            raise OAuthRejected
        connection = None
        try:
            connection = http.client.HTTPSConnection("api.ebay.com", timeout=10)
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read(262145)
            if response.status != 200 or len(data) > 262144:
                raise OAuthRejected
            return data
        except Exception:
            raise OAuthRejected from None
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    @sensitive_variables()
    def exchange(self, code):
        _, runame, _ = configuration()
        credentials = base64.b64encode(f"{settings.EBAY_APP_ID}:{settings.EBAY_CERT_ID}".encode()).decode()
        body = urlencode({"grant_type": "authorization_code", "code": code, "redirect_uri": runame})
        raw = self._request("POST", "/identity/v1/oauth2/token", body, {
            "Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded",
        })
        try:
            data = json.loads(raw)
            for field in ("access_token", "refresh_token"):
                if not isinstance(data.get(field), str) or not 1 <= len(data[field]) <= 32768:
                    raise ValueError
            for field in ("expires_in", "refresh_token_expires_in"):
                if type(data.get(field)) is not int or not 1 <= data[field] <= 315360000:
                    raise ValueError
            if data.get("token_type", "Bearer").casefold() not in ("bearer", "user access token"):
                raise ValueError
            if "scope" in data:
                if not isinstance(data["scope"], str) or set(data["scope"].split()) != set(SCOPES):
                    raise ValueError
            return data
        except (ValueError, TypeError, KeyError, AttributeError):
            raise OAuthRejected from None

    @sensitive_variables()
    def seller(self, access_token):
        body = GET_USER_BODY
        raw = self._request("POST", "/ws/api.dll", body, {
            "X-EBAY-API-CALL-NAME": "GetUser", "X-EBAY-API-SITEID": "77",
            "X-EBAY-API-COMPATIBILITY-LEVEL": "1487", "X-EBAY-API-IAF-TOKEN": access_token,
            "Content-Type": "text/xml; charset=utf-8",
        })
        try:
            if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                raise ValueError
            root = ElementTree.fromstring(raw)
            ns = {"e": "urn:ebay:apis:eBLBaseComponents"}
            if root.findtext("e:Ack", namespaces=ns) not in ("Success", "Warning"):
                raise ValueError
            seller = root.findtext("e:User/e:UserID", namespaces=ns)
            if not seller or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", seller):
                raise ValueError
            return seller
        except (ElementTree.ParseError, ValueError, TypeError):
            raise OAuthRejected from None
