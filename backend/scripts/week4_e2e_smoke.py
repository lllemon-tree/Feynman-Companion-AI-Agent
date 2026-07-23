import fitz
from fastapi.testclient import TestClient

from backend.app.main import app


def build_demo_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (50, 50),
        (
            "Dijkstra algorithm computes single-source shortest paths in a weighted graph. "
            "It requires non-negative edge weights. The algorithm repeatedly selects the "
            "unvisited vertex with the smallest tentative distance and relaxes its edges. "
            "Non-negative weights ensure a selected vertex cannot later receive a shorter path."
        ),
    )
    document.set_toc([[1, "Shortest Path Algorithms", 1]])
    content = document.tobytes()
    document.close()
    return content


def main() -> None:
    with TestClient(app) as client:
        upload_response = client.post(
            "/api/v1/material/upload",
            data={"subject": "计算机"},
            files={
                "file": (
                    "week4-smoke.pdf",
                    build_demo_pdf(),
                    "application/pdf",
                )
            },
        )
        upload_response.raise_for_status()
        material_id = upload_response.json()["data"]["material_id"]

        status_response = client.get(f"/api/v1/material/{material_id}/status")
        status_response.raise_for_status()
        status = status_response.json()["data"]
        if status["status"] != "done":
            raise RuntimeError(f"material workflow failed: {status}")

        tree_response = client.get(
            "/api/v1/material/tree",
            params={"subject": "计算机"},
        )
        tree_response.raise_for_status()
        material = next(
            item
            for item in tree_response.json()["data"]
            if item["material_id"] == material_id
        )
        kp = material["chapters"][0]["knowledge_points"][0]

        greeting_response = client.get(
            "/api/v1/feynman/greeting",
            params={"kp_id": kp["kp_id"]},
        )
        greeting_response.raise_for_status()

        chat_response = client.post(
            "/api/v1/feynman/chat",
            json={
                "session_id": f"smoke-{material_id}",
                "kp_id": kp["kp_id"],
                "user_input": "Dijkstra repeatedly selects the nearest unvisited vertex.",
            },
        )
        chat_response.raise_for_status()
        chat_data = chat_response.json()["data"]

        print(f"material_id={material_id}")
        print(f"kp_id={kp['kp_id']}")
        print(f"material_status={status['status']}")
        print(f"chat_next_action={chat_data['next_action']}")


if __name__ == "__main__":
    main()
