async def test_health_responde_ok(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "copiloto"}
