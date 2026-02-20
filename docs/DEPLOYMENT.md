# Deployment: Local → GitHub → VPS

This guide sets up a CI/CD pipeline so that pushes to `main` run tests (existing CI), build the container image, push it to GitHub Container Registry (GHCR), and deploy to your VPS.

## Pipeline overview

| Stage | Where | What |
|-------|--------|------|
| **Local** | Your machine | Develop, run `./scripts/verify.sh`, push/PR to GitHub |
| **CI** | GitHub Actions | On every push/PR: lint, test, frontend build (`.github/workflows/ci.yml`) |
| **CD** | GitHub Actions | After **CI - Lint and Test** succeeds on `main`: build image → push to GHCR → SSH to VPS → pull & restart (`.github/workflows/deploy.yml`). Also runnable manually. |
| **VPS** | EC2 / your server | Podman runs `meme-stocks:latest` from GHCR; data in volume `meme-stocks-data` |

## One-time setup

### 1. GitHub repository secrets

In the repo: **Settings → Secrets and variables → Actions**, add:

| Secret | Description |
|--------|-------------|
| `VPS_SSH_PRIVATE_KEY` | Your SSH **private** key, **base64-encoded** so newlines are preserved. From your machine run: `base64 -w0 ~/.ssh/aws-meme-stocks` (Linux) or `base64 -i ~/.ssh/aws-meme-stocks` (macOS), then paste the single line into the secret. Must be the key whose public half is on the VPS (e.g. the EC2 key pair you chose at launch). |
| `VPS_HOST` | VPS hostname or IP (e.g. `18.118.189.110` or `meme-stocks-vps` if you use `/etc/hosts`). |
| `VPS_USER` | (Optional.) SSH user; default is `ec2-user`. Set if your image uses a different user (e.g. `ubuntu`). |

Do **not** commit these; they are only in GitHub Secrets.

### 2. VPS preparation

On the VPS (one-time):

1. **Install Podman** (and optionally podman-compose for manual use):

   ```bash
   # Amazon Linux 2023
   sudo dnf install -y podman

   # Optional: podman-compose for manual restarts using compose.prod.yaml
   # pip install podman-compose   or use the image from the repo
   ```

2. **Create app directory and env file** (for Reddit and other secrets):

   ```bash
   sudo mkdir -p /opt/meme-stocks
   sudo touch /opt/meme-stocks/.env
   sudo chown -R ec2-user:ec2-user /opt/meme-stocks
   ```

   Edit `/opt/meme-stocks/.env` with at least (see `backend/app/config.py` and `docs/GETTING_STARTED.md`):

   ```bash
   REDDIT_CLIENT_ID=your-client-id
   REDDIT_CLIENT_SECRET=your-client-secret
   REDDIT_USER_AGENT=meme-stocks-app/0.1
   # DATABASE_URL, LOG_LEVEL, etc. optional
   ```

   The deploy workflow uses this file when starting the container (`--env-file /opt/meme-stocks/.env`). If the file is missing, the app still starts but Reddit collection will fail until you add it.

3. **Allow GitHub Actions to SSH**
   Use the same key you use locally (e.g. the one you added to the EC2 key pair when creating the instance). Put that key’s **private** part in `VPS_SSH_PRIVATE_KEY`. No extra user is needed on the VPS for GitHub.

4. **Open port 8000**
   In the VPS security group / firewall, allow TCP 8000 from the internet (or from your IP only) so you can reach `http://<VPS>:8000`.

### 3. GitHub Container Registry (GHCR)

- The workflow uses `GITHUB_TOKEN` to push to `ghcr.io/<owner>/meme-stocks`.
- If the repo is **private**, the image is private by default. To pull from the VPS you must either:
  - Make the package **public**: repo → **Packages** → open the `meme-stocks` package → **Package settings** → **Change visibility** → Public, or
  - Log in on the VPS with a Personal Access Token (PAT) with `read:packages` and use it in the deploy step (e.g. `podman login -u USER -p PAT ghcr.io` before `podman pull`). For simplicity, making the package public is easiest for a single-user app.

## Workflow behavior

- **Deploy workflow** (`.github/workflows/deploy.yml`):
  - **Triggers:** When the **CI - Lint and Test** workflow completes successfully on `main` (so deploy runs only if tests pass), or manual **Run workflow** from the Actions tab.
  - **Build:** Builds the image from the repo `Containerfile`, tags it `ghcr.io/<owner>/meme-stocks:<sha>` and `:latest`, pushes to GHCR.
  - **Deploy:** SSHs to the VPS, runs `podman pull`, stops/removes the existing `meme-stocks-backend` container (if any), starts a new one with the same name, port 8000, and volume `meme-stocks-data`. Uses `/opt/meme-stocks/.env` if present.

- **Existing CI** (`.github/workflows/ci.yml`) continues to run on every push/PR; it does not deploy.

## Local development flow

1. Work on a branch, run `./scripts/verify.sh` and push.
2. Open a PR; CI runs (lint, tests, frontend build).
3. Merge to `main`; CI runs, then the deploy workflow runs (only if CI succeeded) and updates the VPS.
4. Check the app at `http://<VPS_HOST>:8000` and API docs at `http://<VPS_HOST>:8000/docs`.

## Manual deploy / rollback on VPS

To pull and restart without GitHub:

```bash
ssh ec2-user@<VPS_HOST>
podman pull ghcr.io/<your-github-owner>/meme-stocks:latest
podman stop meme-stocks-backend
podman rm meme-stocks-backend
podman run -d --name meme-stocks-backend -p 8000:8000 \
  -v meme-stocks-data:/app/data --restart unless-stopped \
  --env-file /opt/meme-stocks/.env \
  ghcr.io/<your-github-owner>/meme-stocks:latest
```

Or use `compose.prod.yaml`: replace `REPLACE_OWNER` with your GitHub username/org, copy the file to the VPS, and run `podman-compose -f compose.prod.yaml up -d` (if you have podman-compose installed).

## Troubleshooting

- **Deploy job fails at SSH (Permission denied (publickey,...)):** Usually the private key lost its newlines when pasted. Store it **base64-encoded**: run `base64 -w0 ~/.ssh/aws-meme-stocks` (Linux) or `base64 -i ~/.ssh/aws-meme-stocks` (macOS), paste that single line into `VPS_SSH_PRIVATE_KEY`, and update the secret. Also confirm the key is the one on the VPS (EC2 key pair or `authorized_keys`).
- **Deploy fails at `podman pull`:** If the image is private, make the package public or log in to GHCR on the VPS (see “GitHub Container Registry” above).
- **App 500 or Reddit errors:** Ensure `/opt/meme-stocks/.env` exists and has valid `REDDIT_*` (and any other required) variables.
- **Port 8000 not reachable:** Check the VPS security group and OS firewall (e.g. `sudo firewall-cmd` or iptables).

## References

- `docs/GETTING_STARTED.md` – Configuration and env vars
- `.github/workflows/ci.yml` – Lint and test
- `.github/workflows/deploy.yml` – Build, push, and VPS deploy
