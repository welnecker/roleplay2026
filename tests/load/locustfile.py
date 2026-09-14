from __future__ import annotations

import os
from uuid import uuid4

from locust import HttpUser, between, task


TEST_ID = os.getenv("LOAD_TEST_ID", "load-local")
PACKAGE_ID = os.getenv("LOAD_TEST_PACKAGE_ID", "roleplay2026.degustacao")
PASSWORD = os.getenv("LOAD_TEST_PASSWORD", "Carga-segura-2026")


class StoryUser(HttpUser):
    wait_time = between(0.7, 1.8)

    def on_start(self) -> None:
        suffix = uuid4().hex[:12]
        self.virtual_user = f"user-{suffix}"
        self.client.headers.update({
            "X-Load-Test-ID": TEST_ID,
            "X-Virtual-User-ID": self.virtual_user,
        })
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "display_name": f"Carga {suffix}",
                "email": f"loadtest_{TEST_ID}_{suffix}@example.invalid",
                "password": PASSWORD,
            },
            name="POST /api/v1/auth/register",
        )
        if response.status_code != 201:
            raise RuntimeError(f"Falha ao criar usuário virtual: HTTP {response.status_code}")
        self.client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
        self.frame: dict[str, object] | None = None
        self.identity = {
            "package_id": PACKAGE_ID,
            "preferred_name": f"Pessoa {suffix[:4]}",
            "story_gender": "De forma neutra",
        }

    def _open(self) -> None:
        with self.client.post(
            "/api/v1/runs/open", json=self.identity,
            name="POST /api/v1/runs/open", catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"abertura HTTP {response.status_code}: {response.text[:160]}")
                return
            payload = response.json()
            if payload.get("package_id") != PACKAGE_ID or not payload.get("frame_id"):
                response.failure("run retornou package_id/frame_id inválido")
                return
            self.frame = payload

    @task(8)
    def play_story(self) -> None:
        if self.frame is None or bool(self.frame.get("finished")):
            self._open()
            return

        revealed = int(self.frame.get("revealed_entries", 0))
        entry_count = int(self.frame.get("entry_count", 0))
        if revealed < entry_count:
            payload = {**self.identity, "frame_id": self.frame["frame_id"]}
            with self.client.post(
                "/api/v1/runs/reveal", json=payload,
                name="POST /api/v1/runs/reveal", catch_response=True,
            ) as response:
                if response.status_code != 200:
                    response.failure(f"reveal HTTP {response.status_code}: {response.text[:160]}")
                else:
                    updated = response.json()
                    if updated.get("frame_id") != self.frame.get("frame_id"):
                        response.failure("reveal mudou o quadro inesperadamente")
                    else:
                        self.frame = updated
            return

        previous_frame = str(self.frame["frame_id"])
        payload = {
            **self.identity,
            "frame_id": previous_frame,
            "revealed_entries": revealed,
        }
        with self.client.post(
            "/api/v1/runs/advance", json=payload,
            name="POST /api/v1/runs/advance", catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"avanço HTTP {response.status_code}: {response.text[:160]}")
                return
            updated = response.json()
            if not updated.get("finished") and updated.get("frame_id") == previous_frame:
                response.failure("avanço manteve o mesmo quadro")
            else:
                self.frame = updated

    @task(2)
    def catalog(self) -> None:
        with self.client.get("/api/v1/catalog", name="GET /api/v1/catalog", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"catálogo HTTP {response.status_code}")
            elif not any(item.get("package_id") == PACKAGE_ID for item in response.json().get("items", [])):
                response.failure("história do teste ausente no catálogo")
