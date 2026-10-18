from fastapi.testclient import TestClient

PASSWORD = "correct-horse-battery"

# ~7,600 characters in 20 paragraphs: several chunks at the default size.
SAMPLE_TEXT = "\n\n".join(
    f"Paragraph {i}. " + "Evidence based answers need sources. " * 10 for i in range(20)
)


def register(
    client: TestClient,
    email: str = "alice@example.com",
    password: str = PASSWORD,
    full_name: str = "Alice",
):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )


def login(client: TestClient, email: str = "alice@example.com", password: str = PASSWORD):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def auth_headers(
    client: TestClient, email: str = "alice@example.com", full_name: str = "Alice"
) -> dict[str, str]:
    assert register(client, email=email, full_name=full_name).status_code == 201
    token = login(client, email=email).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_collection(client: TestClient, headers: dict[str, str], name: str = "Research") -> str:
    response = client.post("/api/collections", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def upload(
    client: TestClient,
    headers: dict[str, str],
    collection_id: str,
    filename: str = "notes.txt",
    data: bytes = b"Hello evidence world.",
    content_type: str = "text/plain",
):
    return client.post(
        f"/api/collections/{collection_id}/documents",
        files={"file": (filename, data, content_type)},
        headers=headers,
    )


def make_pdf(pages: list[str]) -> bytes:
    """Build a tiny valid PDF with one line of text per page (no extra libraries)."""
    count = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(count))
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, text in enumerate(pages):
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET"
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {5 + 2 * i} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return bytes(out)
