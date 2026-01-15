from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_update_user_no_auth(client: "AsyncClient", csrf_headers: dict[str, str]) -> None:
    response = await client.patch(
        "/api/users/97108ac1-ffcb-411d-8b1e-d9183399f63b",
        json={"name": "TEST UPDATE"},
        headers=csrf_headers,
    )
    assert response.status_code == 401
    response = await client.post(
        "/api/users/",
        data={"name": "A User", "email": "new-user@example.com", "password": "S3cret!"},
        headers=csrf_headers,
    )
    assert response.status_code == 401
    response = await client.get("/api/users/97108ac1-ffcb-411d-8b1e-d9183399f63b")
    assert response.status_code == 401
    response = await client.get("/api/users")
    assert response.status_code == 401
    response = await client.delete(
        "/api/users/97108ac1-ffcb-411d-8b1e-d9183399f63b",
        headers=csrf_headers,
    )
    assert response.status_code == 401


async def test_accounts_list(client: "AsyncClient", superuser_token_headers: dict[str, str]) -> None:
    response = await client.get("/api/users", headers=superuser_token_headers)
    assert response.status_code == 200
    assert int(response.json()["total"]) > 0


async def test_accounts_get(client: "AsyncClient", superuser_token_headers: dict[str, str]) -> None:
    response = await client.get("/api/users/97108ac1-ffcb-411d-8b1e-d9183399f63b", headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "superuser@example.com"


async def test_accounts_create(
    client: "AsyncClient",
    csrf_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/users",
        data={"name": "A User", "email": "new-user@example.com", "password": "S3cret!"},
        headers={**csrf_headers, **superuser_token_headers},
    )
    assert response.status_code == 201


async def test_accounts_update(
    client: "AsyncClient",
    csrf_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    response = await client.patch(
        "/api/users/5ef29f3c-3560-4d15-ba6b-a2e5c721e4d2",
        json={
            "name": "Name Changed",
        },
        headers={**csrf_headers, **superuser_token_headers},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Name Changed"


async def test_accounts_delete(
    client: "AsyncClient",
    csrf_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    response = await client.delete(
        "/api/users/5ef29f3c-3560-4d15-ba6b-a2e5c721e4d2",
        headers={**csrf_headers, **superuser_token_headers},
    )
    assert response.status_code == 200
    # ensure we didn't cascade delete the teams the user owned
    response = await client.get(
        "/api/teams/97108ac1-ffcb-411d-8b1e-d9183399f63b",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200


async def test_accounts_with_incorrect_role(
    client: "AsyncClient",
    csrf_headers: dict[str, str],
    user_token_headers: dict[str, str],
) -> None:
    response = await client.patch(
        "/api/users/97108ac1-ffcb-411d-8b1e-d9183399f63b",
        json={"name": "TEST UPDATE"},
        headers={**csrf_headers, **user_token_headers},
    )
    assert response.status_code == 403
    response = await client.post(
        "/api/users/",
        data={"name": "A User", "email": "new-user@example.com", "password": "S3cret!"},
        headers={**csrf_headers, **user_token_headers},
    )
    assert response.status_code == 403
    response = await client.get("/api/users/97108ac1-ffcb-411d-8b1e-d9183399f63b", headers=user_token_headers)
    assert response.status_code == 403
    response = await client.get("/api/users", headers=user_token_headers)
    assert response.status_code == 403
    response = await client.delete(
        "/api/users/97108ac1-ffcb-411d-8b1e-d9183399f63b",
        headers={**csrf_headers, **user_token_headers},
    )
    assert response.status_code == 403
