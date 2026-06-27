# Deploy SEOOptimizer on Hetzner Cloud

## Prerequisites

- Hetzner Cloud account
- SSH key pair added to your Hetzner project

---

## Step 1: Create a VM

| Setting | Value |
|---|---|
| **Location** | Choose closest to your users (e.g. `nbg1` Nuremberg, `hel1` Helsinki, `fsn1` Falkenstein) |
| **Image** | Ubuntu 24.04 LTS |
| **Type** | CX22 (2 vCPU, 4 GB RAM) — minimum for newspaper4k + ChromaDB |
| **Firewall** | Allow TCP ports `22`, `8501` (optionally `80` + `443` if you add a proxy later) |
| **SSH Keys** | Attach your public key |

Boot the VM and note its IP address.

---

## Step 2: Install Docker

SSH into the VM:

```bash
ssh root@<VM_IP>
```

Install Docker Engine and the Compose plugin:

```bash
# Add Docker's official GPG key and repository
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify
docker --version
docker compose version
```

---

## Step 3: Clone the repository

```bash
git clone https://github.com/ckronseder/seooptimizer.git
cd seooptimizer
```

---

## Step 4: Create the `.env` file

```bash
nano .env
```

Paste the following and fill in your real values:

```ini
# Google Gemini API key
GEM_API="your-gemini-api-key"

# DataForSEO credentials
SEO_USERNAME="your-dataforseo-email"
SEO_PASSWORD="your-dataforseo-password"

# App authentication (both username and password)
AUTH_USERNAME="ck"
AUTH_PASSWORD="ck1234"
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

> **Security:** This file is read by `docker compose` and passed into the container as environment variables. Keep it safe — never commit it.

---

## Step 5: Build and start the container

```bash
docker compose build --no-cache
docker compose up -d
```

- `--no-cache` is only needed on first build or when `requirements.txt` changes
- The `-d` flag runs the container in the background

Check that it started:

```bash
docker compose ps
docker compose logs -f  # Ctrl+C to detach
```

---

## Step 6: Access the app

Open your browser at:

```
http://<VM_IP>:8501
```

Log in with the credentials from your `.env` file (e.g. `ck` / `ck1234`).

---

## Maintenance

### Stop / start

```bash
docker compose down     # stop
docker compose up -d    # start again
```

### Update to latest code

```bash
git pull
docker compose build --no-cache
docker compose up -d
```

### View logs

```bash
docker compose logs -f --tail 100
```

### Backup persistent data

```bash
# Stop the container first
docker compose down

# Backup
tar -czf seooptimizer-backup-$(date +%Y%m%d).tar.gz \
  /var/lib/docker/volumes/seooptimizer_chroma_data/ \
  /var/lib/docker/volumes/seooptimizer_search_history/

# Start again
docker compose up -d
```

### Remove everything (keep images)

```bash
docker compose down -v  # -v removes volumes (deletes ChromaDB + history!)
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Connection refused` on port 8501 | Container not running, or firewall blocking | `docker compose ps`, check Hetzner firewall rules |
| `ValueError: required secret(s) not set` | Missing env vars | Check `.env` file, run `docker compose down && docker compose up -d` |
| ChromaDB errors on restart | Stale embedding data | `docker compose down -v && docker compose up -d` (deletes vector store) |
| Container exits immediately | Port already in use | `lsof -i :8501` and kill the process, or change the host port in `docker-compose.yml` |
