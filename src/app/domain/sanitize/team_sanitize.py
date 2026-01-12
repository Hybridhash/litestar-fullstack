from __future__ import annotations

from advanced_alchemy.service import ModelDictT, is_dict

from app.db import models as m
from app.domain.sanitize.sanitize_base import clean_text


def sanitize_team_payload(data: ModelDictT[m.Team]) -> ModelDictT[m.Team]:
    if is_dict(data):
        name = data.get("name")
        if isinstance(name, str):
            cleaned_name = clean_text(name)
            data["name"] = cleaned_name or name
        description = data.get("description")
        if isinstance(description, str):
            cleaned_description = clean_text(description)
            data["description"] = cleaned_description or None
        slug = data.get("slug")
        if isinstance(slug, str):
            cleaned_slug = clean_text(slug)
            data["slug"] = cleaned_slug or None
    return data
