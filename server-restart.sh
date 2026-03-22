#!/bin/bash -x
podman stop meme-stocks-backend
podman rm meme-stocks-backend
podman run -d --name meme-stocks-backend \
  -p 8000:8000 \
  -v meme-stocks-data:/app/data \
  -e LEADER_FOLLOWER_ENABLED=true \
  -e PYTHONPATH=/app \
  -e DATABASE_URL=sqlite:///./data/app.db \
  -e SERVING_FRONTEND=true \
  meme-stocks:latest
podman logs meme-stocks-backend -t --tail 200 -f
