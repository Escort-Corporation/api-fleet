"""Fake minimo do client Supabase (so o que o servico usa) para testar as regras do MVP."""

import os
import uuid

import pytest

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret-key")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:3000")


_NOW = "2026-11-16T12:00:00+00:00"


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, table):
        self._db, self._table, self._op, self._payload = db, table, "select", None
        self._filters, self._limit = [], None

    def select(self, *_a, **_k):
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, col, val):
        self._filters.append(lambda r, c=col, v=val: r.get(c) == v)
        return self

    def in_(self, col, vals):
        vals = set(vals)
        self._filters.append(lambda r, c=col: r.get(c) in vals)
        return self

    def is_(self, col, val):
        self._filters.append(lambda r, c=col: r.get(c) is None)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        rows = self._db.tables.setdefault(self._table, [])
        if self._op == "insert":
            # Defaults que o Postgres aplicaria (status, timestamps).
            defaults = {"id": str(uuid.uuid4()), "created_at": _NOW, "updated_at": _NOW}
            if self._table == "vehicles":
                defaults["status"] = "active"
            if self._table == "carrier_drivers":
                defaults.setdefault("started_at", _NOW)
                defaults["ended_at"] = None
            row = {**defaults, **self._payload}
            rows.append(row)
            return _Result([dict(row)])
        matched = [r for r in rows if all(f(r) for f in self._filters)]
        if self._op == "update":
            for r in matched:
                r.update(self._payload)
        elif self._op == "delete":
            for r in matched:
                rows.remove(r)
        if self._limit is not None:
            matched = matched[: self._limit]
        return _Result([dict(r) for r in matched])


class FakeSupabase:
    def __init__(self):
        self.tables = {}

    def table(self, name):
        return _Query(self, name)

    def add(self, table, **row):
        row.setdefault("id", str(uuid.uuid4()))
        self.tables.setdefault(table, []).append(row)
        return row


@pytest.fixture()
def db(monkeypatch):
    import app.services.driver_service as driver_service
    import app.services.vehicle_service as vehicle_service

    fake = FakeSupabase()
    monkeypatch.setattr(vehicle_service, "get_supabase_admin_client", lambda: fake)
    monkeypatch.setattr(driver_service, "get_supabase_admin_client", lambda: fake)
    return fake
