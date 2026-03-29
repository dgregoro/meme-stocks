# Deployment: Local → GitHub → VPS

This guide sets up a CI/CD pipeline so that pushes to `main` run tests (existing CI), build the container image, push it to GitHub Container Registry (GHCR), and deploy to your VPS.

## Pipeline overview

| Stage | Where | What |
|-------|--------|------|
| **Local** | Your machine | Develop, run `./scripts/verify.sh`, push/PR to GitHub |
| **CI** | GitHub Actions | On every push/PR: lint, test, frontend build (`.github/workflows/ci.yml`) |
| **CD** | GitHub Actions | After **CI - Lint and Test** succeeds on `main`: build image → push to GHCR → SSH to VPS → pull & restart (`.github/workflows/deploy.yml`). Also runnable manually. |
| **VPS** | EC2 / your server (CentOS 9) | Podman runs `meme-stocks:latest` from GHCR; data in volume `meme-stocks-data` |

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

   The VPS runs **CentOS 9**. Use `dnf` and `firewall-cmd` (firewalld) as below.

   ```bash
   # CentOS 9 (or Amazon Linux 2023)
   sudo dnf install -y podman

   # Optional: podman-compose for manual restarts using compose.prod.yaml
   # pip install podman-compose   or use the image from the repo
   ```

2. **Create app directory and env file** (optional overrides and provider keys):

   ```bash
   sudo mkdir -p /opt/meme-stocks
   sudo touch /opt/meme-stocks/.env
   sudo chown -R ec2-user:ec2-user /opt/meme-stocks
   ```

   Edit `/opt/meme-stocks/.env` only if you need non-default paths, logging, **Alpaca** keys for intraday, etc. **Reddit credentials are not used**—the application no longer ingests Reddit. See `backend/app/config.py` and `docs/GETTING_STARTED.md`.

   The deploy workflow uses this file when starting the container (`--env-file /opt/meme-stocks/.env`). If the file is missing or empty, the app still starts with defaults.

3. **Allow GitHub Actions to SSH**
   Use the same key you use locally (e.g. the one you added to the EC2 key pair when creating the instance). Put that key’s **private** part in `VPS_SSH_PRIVATE_KEY`. No extra user is needed on the VPS for GitHub.

4. **Open port 8000**
   In the VPS security group (e.g. AWS) allow inbound TCP 8000. On CentOS 9, also open the OS firewall: `sudo firewall-cmd --permanent --add-port=8000/tcp` then `sudo firewall-cmd --reload`. Restrict source to your IP in production if desired.

### 3. GitHub Container Registry (GHCR)

- The workflow uses `GITHUB_TOKEN` to push to `ghcr.io/<owner>/meme-stocks`.
- If the repo is **private**, the image is private by default. To pull from the VPS you must either:
  - Make the package **public**: repo → **Packages** → open the `meme-stocks` package → **Package settings** → **Change visibility** → Public, or
  - Log in on the VPS with a Personal Access Token (PAT) with `read:packages` and use it in the deploy step (e.g. `podman login -u USER -p PAT ghcr.io` before `podman pull`). For simplicity, making the package public is easiest for a single-user app.

## Workflow behavior

- **Deploy workflow** (`.github/workflows/deploy.yml`):
  - **Triggers:** When the **CI - Lint and Test** workflow completes successfully on `main` (so deploy runs only if tests pass), or manual **Run workflow** from the Actions tab.
  - **Build:** Builds the image from the repo `Containerfile`, tags it `ghcr.io/<owner>/meme-stocks:<sha>` and `:latest`, pushes to GHCR.
  - **Deploy:** SSHs to the VPS, runs `podman pull`, stops/removes the existing `meme-stocks-backend` container (if any), starts a new one with the same name, port 8000, and volume `meme-stocks-data`. Uses `/opt/meme-stocks/.env` if present. After starting, the workflow waits ~12s and runs a health check (`curl http://localhost:8000/health` on the VPS); if the app does not respond, the deploy job **fails** and the run log includes container status and the last 30 log lines so the failure is visible in GitHub Actions (no silent shutdown).

- **Existing CI** (`.github/workflows/ci.yml`) continues to run on every push/PR; it does not deploy.

## Local development flow

1. Work on a branch, run `./scripts/verify.sh` and push.
2. Open a PR; CI runs (lint, tests, frontend build).
3. Merge to `main`; CI runs, then the deploy workflow runs (only if CI succeeded) and updates the VPS.
4. Check the app at `http://<VPS_HOST>:8000` and API docs at `http://<VPS_HOST>:8000/docs`.

## Viewing activity

- **Container logs** (on the VPS): `podman logs meme-stocks-backend` (add `-f` to follow). Shows scheduler runs, price collection, notification checks, daily analysis, and errors.
- **API docs**: `http://<VPS_HOST>:8000/docs` — try endpoints from the browser.
- **Job run history** (when each scheduled job last ran):
  `GET /api/jobs/{job_name}/runs` with `job_name` one of: `price-collection`, `notification-check`, `daily-analysis`, `leader-follower-detection` (when that feature is enabled).
  Example: `curl -s http://<VPS_HOST>:8000/api/jobs/price-collection/runs`
- **Notifications**: `GET /api/notifications` — alerts generated by the app.
- **CLI** (from your machine, with backend on VPS): set `MEME_STOCKS_API_URL=http://<VPS_HOST>:8000`, then e.g. `python -m backend.cli.main jobs prices`, `jobs notifications`, `notifications`.

## Daily email digest

To get a daily email summary of app activity (job runs, top analysis, unread notifications), run the digest script on the VPS via cron.

### 1. Copy the script to the VPS

From your repo, copy `scripts/daily_digest_email.py` to the VPS (e.g. `/opt/meme-stocks/daily_digest_email.py`). It uses only the Python standard library.

### 2. Configure email (SMTP)

Set environment variables for sending mail. Using a Gmail app password or another SMTP relay is typical. Example for a cron job:

Create `/opt/meme-stocks/digest.env` (chmod 600, do not commit):

```bash
BASE_URL=http://127.0.0.1:8000
EMAIL_TO=you@example.com
EMAIL_FROM=you@example.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password
```

(For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833), not your normal password.)

### 3. Schedule with cron

On the VPS:

```bash
crontab -e
```

Add a line to run the script once per day (e.g. 8:00 AM server time):

```cron
0 8 * * * /usr/bin/python3 /opt/meme-stocks/daily_digest_email.py < /dev/null >> /opt/meme-stocks/digest.log 2>&1
```

To load the env file before running:

```cron
0 8 * * * set -a && . /opt/meme-stocks/digest.env && set +a && /usr/bin/python3 /opt/meme-stocks/daily_digest_email.py >> /opt/meme-stocks/digest.log 2>&1
```

If `EMAIL_TO` or SMTP vars are not set, the script prints the digest to stdout only (and logs to `digest.log`), so you can test without email first.

### 4. Optional: include container logs

To append the last 100 lines of container logs to the digest, run from a wrapper script that fetches the digest output and `podman logs --tail 100 meme-stocks-backend`, then mails the combined body. The Python script itself does not read podman logs; it only calls the HTTP API.

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

### Why did the app shut down on the VPS?

SSH to the VPS and run these in order to find the cause.

1. **Is the container running?**

   ```bash
   podman ps -a --filter name=meme-stocks-backend
   ```

   - **STATUS "Up"**: Container is running; if the app is unreachable, check firewall/security group and `podman logs meme-stocks-backend`.
   - **STATUS "Exited"**: Container stopped. Check exit code and logs (steps 2–3).

2. **Why did the container exit?**

   ```bash
   podman inspect meme-stocks-backend --format '{{.State.Status}} {{.State.ExitCode}} {{.State.Error}}'
   podman logs meme-stocks-backend --tail 200
   ```

   - **ExitCode 0**: Usually intentional stop (e.g. `podman stop`).
   - **ExitCode 137**: Often OOM killed (out of memory). Check `dmesg | tail -50` or `journalctl -k -n 50` for OOM messages.
   - **ExitCode 1 or 255**: App or runtime crash. The last lines of `podman logs` usually show the error.

3. **Host and resources**

   ```bash
   # Disk full? (SQLite and logs live in the volume)
   df -h
   du -sh ~/.local/share/containers/storage/volumes/meme-stocks-data 2>/dev/null || podman volume inspect meme-stocks-data

   # Recent OOM or reboots
   dmesg | tail -30
   uptime
   ```

   If the disk is full, free space or move the volume; then start the container again.

4. **Restart the app**

   ```bash
   podman start meme-stocks-backend
   # Or full recreate (same as deploy workflow):
   podman stop meme-stocks-backend 2>/dev/null; podman rm meme-stocks-backend 2>/dev/null
   podman run -d --name meme-stocks-backend -p 8000:8000 -v meme-stocks-data:/app/data \
     --restart unless-stopped --env-file /opt/meme-stocks/.env \
     ghcr.io/<your-github-owner>/meme-stocks:latest
   ```

5. **After a host reboot**

   With `--restart unless-stopped`, Podman usually restarts the container when the host boots. If it did not, start the container manually (step 4) and ensure Podman (and socket) are enabled: `systemctl --user enable --now podman.socket` (rootless) or `systemctl enable --now podman` (root).

**Common causes**

| Cause | What to check |
|-------|----------------|
| OOM kill | Exit code 137; `dmesg` / `journalctl -k`; add swap or larger instance |
| App crash | Non-zero exit code; last lines of `podman logs` |
| Disk full | `df -h`; clear logs or resize volume |
| Deploy left container stopped | Re-run deploy or run the `podman run` command above |
| Reboot and no auto-start | Start container manually; enable podman (see step 5) |

**If you suspect the latest GitHub deploy:** A deploy stops the old container and starts a new one. If the new container exits soon after start (e.g. crash or OOM), the app stays down and the workflow used to still report success. The workflow now runs a **post-deploy health check**; if the app does not respond within ~12s, the deploy job fails and the Actions log shows container status and recent logs. After merging this change, a bad deploy will show as a failed run instead of a quiet shutdown.

---

- **Deploy job fails at SSH (Permission denied (publickey,...)):** Usually the private key lost its newlines when pasted. Store it **base64-encoded**: run `base64 -w0 ~/.ssh/aws-meme-stocks` (Linux) or `base64 -i ~/.ssh/aws-meme-stocks` (macOS), paste that single line into `VPS_SSH_PRIVATE_KEY`, and update the secret. Also confirm the key is the one on the VPS (EC2 key pair or `authorized_keys`).
- **Deploy fails at `podman pull`:** If the image is private, make the package public or log in to GHCR on the VPS (see “GitHub Container Registry” above).
- **App 500 or external API errors:** Check `podman logs` for the failing provider (e.g. Yahoo Finance, Alpaca). Ensure optional keys in `.env` match features you enabled (e.g. intraday requires Alpaca credentials).
- **Port 8000 not reachable:** Check the VPS security group (e.g. AWS inbound rules) and, on CentOS 9, the OS firewall: `sudo firewall-cmd --permanent --add-port=8000/tcp` then `sudo firewall-cmd --reload`.

## References

- `docs/GETTING_STARTED.md` – Configuration and env vars
- `.github/workflows/ci.yml` – Lint and test
- `.github/workflows/deploy.yml` – Build, push, and VPS deploy
