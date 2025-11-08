# tests/test_auth.py
def test_register_login_me(client):
    email = "buyer@test.local"
    password = "buyer123"

    # register
    r = client.post("/api/auth/register", json={
        "name": "Buyer",
        "email": email,
        "password": password,
        "role": "buyer"
    })
    assert r.status_code in (200, 409)  # puede estar ya creado
    # login
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    token = r.get_json()["data"]["token"]
    # me
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    me = r.get_json()["data"]
    assert me["email"] == email
    assert me["role"] in ("buyer", "seller", "admin")
