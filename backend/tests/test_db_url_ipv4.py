from backend.utils.config import force_ipv4_hostaddr


def test_force_ipv4_appends_hostaddr_when_missing(monkeypatch):
    def fake_getaddrinfo(host, port, family):
        assert family == 2  # socket.AF_INET
        return [(None, None, None, None, ("203.0.113.10", port))]

    monkeypatch.setattr("backend.utils.config.socket.getaddrinfo", fake_getaddrinfo)

    url = "postgresql+psycopg://user:pass@db.project.supabase.co:5432/postgres?sslmode=require"
    updated, forced, ipv4 = force_ipv4_hostaddr(url)
    assert forced is True
    assert ipv4 == "203.0.113.10"
    assert "hostaddr=203.0.113.10" in updated


def test_force_ipv4_noop_when_already_present():
    url = "postgresql+psycopg://user:pass@db.project.supabase.co:5432/postgres?sslmode=require&hostaddr=203.0.113.10"
    updated, forced, ipv4 = force_ipv4_hostaddr(url)
    assert forced is True
    assert ipv4 == "203.0.113.10"
    assert updated.endswith("hostaddr=203.0.113.10")


def test_force_ipv4_ignores_non_supabase_host():
    url = "postgresql+psycopg://user:pass@db.internal:5432/postgres?sslmode=require"
    updated, forced, ipv4 = force_ipv4_hostaddr(url)
    assert forced is False
    assert ipv4 is None
    assert updated == url
