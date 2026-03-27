---
description: Rebuild and restart the backend container (picks up backend code changes)
---

## Rebuild Container

1. From project root, run:

```bash
podman-compose down 2>/dev/null; podman-compose up --build -d
```

2. Optionally force a full rebuild with no cache (use when cached layers might be stale):

```bash
podman-compose down 2>/dev/null; podman compose build --no-cache backend && podman-compose up -d
```

3. Verify the app is up:

```bash
curl -s http://localhost:8000/health
```

Expect `{"status":"ok",...}`.

## Notes

- Uses podman-compose (Fedora). For Docker: `docker compose` instead.
- Backend code is baked into the image; rebuild required for code changes.
