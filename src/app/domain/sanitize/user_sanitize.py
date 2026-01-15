from __future__ import annotations

from typing import TYPE_CHECKING

from advanced_alchemy.service import ModelDictT, is_dict

if TYPE_CHECKING:
    from app.db import models as m
from app.domain.sanitize.sanitize_base import clean_text


def sanitize_user_payload(data: ModelDictT[m.User]) -> ModelDictT[m.User]:
    if is_dict(data):
        email = data.get("email")
        if isinstance(email, str):
            cleaned_email = clean_text(email).lower()
            data["email"] = cleaned_email or email
        name = data.get("name")
        if isinstance(name, str):
            cleaned_name = clean_text(name)
            data["name"] = cleaned_name or None
    return data
