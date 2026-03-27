---
description: Restart the backend container without rebuilding (same image, fresh process)
---

## Restart Container

1. From project root, run:

```bash
podman-compose down 2>/dev/null; podman-compose up -d
```

2. Verify the app is up:

```bash
curl -s http://localhost:8000/health
```

Expect `{"status":"ok",...}`.

## When to use

- Restart after config/env changes (if env is passed at runtime)
- Restart to clear in-memory state
- **Not** for backend code changes — use `/rebuild-container` instead.
