# Docker Setup Guide — Wazuh + n8n + Supporting Services

**Author:** Aditya Suresh Acharya

---

## What's In This Folder

| File | Purpose |
|---|---|
| `wazuh-docker-compose.yml` | Runs Wazuh Manager, Indexer, and Dashboard |
| `n8n-docker-compose.yml` | Runs n8n, InfluxDB, Grafana, and TheHive |

---

## Containers Overview

| Container | Image | Port | Purpose |
|---|---|---|---|
| wazuh.manager | wazuh/wazuh-manager:4.14.2 | 1514, 1515, 55000 | Core SIEM engine |
| wazuh.indexer | wazuh/wazuh-indexer:4.14.2 | 9200 | Alert storage (OpenSearch) |
| wazuh.dashboard | wazuh/wazuh-dashboard:4.14.2 | 443 | Web UI |
| n8n | n8nio/n8n:latest | 5678 | Automation pipeline |
| influxdb | influxdb:2.7 | 8086 | Metrics storage |
| grafana | grafana/grafana:latest | 3000 | Metrics visualization |
| thehive | strangebee/thehive:5 | 9000 | Case management |

---

## Prerequisites

**Install Docker and Docker Compose on Ubuntu:**
```bash
sudo apt update
sudo apt install docker.io docker-compose-v2 -y
sudo usermod -aG docker $USER
newgrp docker
```

Verify:
```bash
docker --version
docker compose version
```

---

## Step 1 — Configure Environment Variables

Before starting anything, copy and fill in your `.env` file:

```bash
cp .env.example .env
nano .env
```

Fill in all `<CHANGE_ME_...>` values. See `.env.example` for what each one means.

---

## Step 2 — Generate Wazuh SSL Certificates (First Time Only)

```bash
cd docker/
docker compose -f wazuh-docker-compose.yml run --rm generator
```

This creates the SSL certificates Wazuh needs. Only do this once — if you run it again it overwrites existing certs.

---

## Step 3 — Start Wazuh Stack

```bash
docker compose -f wazuh-docker-compose.yml up -d
```

Wait about 2–3 minutes for everything to initialize, then check:
```bash
docker ps
```

All 3 Wazuh containers should show `Up`:
- `single-node-wazuh.manager-1`
- `single-node-wazuh.indexer-1`
- `single-node-wazuh.dashboard-1`

Access Wazuh dashboard at: `https://<YOUR_VM_IP>`  
Default login: `admin` / `<YOUR_INDEXER_PASSWORD>`

---

## Step 4 — Start n8n Stack

```bash
docker compose -f n8n-docker-compose.yml up -d
```

Check all containers are up:
```bash
docker ps
```

Should see: `n8n`, `influxdb`, `grafana`, `thehive`

Access n8n at: `http://<YOUR_VM_IP>:5678`

---

## Step 5 — Fix Integration Persistence

Wazuh's integration files live inside the container and get wiped on restart. Fix this:

```bash
sudo bash scripts/fix-integrations.sh
sudo systemctl enable wazuh-integrations-fix.service
```

This ensures your custom-webhook.py integration survives container restarts.

---

## Correct Startup Order

Always start services in this order:

```
1. Wazuh stack (docker compose)
        ↓
2. n8n stack (docker compose)
        ↓
3. Ollama on GPU machine (ollama serve)
        ↓
4. blocker.py (python3 scripts/blocker.py)
        ↓
5. Activate n8n workflow (in n8n UI)
```

---

## Useful Commands

```bash
# Check all running containers
docker ps

# Check logs for a specific container
docker logs n8n
docker logs single-node-wazuh.manager-1

# Restart a specific container
docker restart n8n

# Stop everything
docker compose -f wazuh-docker-compose.yml down
docker compose -f n8n-docker-compose.yml down

# Check resource usage
docker stats
```

---

## Networks

The project uses two Docker networks:

| Network | Subnet | Used By |
|---|---|---|
| soc_network | 172.19.0.0/16 | n8n, InfluxDB, Grafana, TheHive |
| single-node_default | 172.18.0.0/16 | Wazuh Manager, Indexer, Dashboard |

These networks are created automatically by docker compose.

---

## Troubleshooting

**Wazuh dashboard shows "Server not ready"**
- Wait 2–3 more minutes — indexer takes time to initialize
- Check indexer logs: `docker logs single-node-wazuh.indexer-1`

**n8n can't connect to InfluxDB**
- Both must be on the same Docker network (`soc_network`)
- Check: `docker network inspect soc_network`

**Port conflicts**
- If port 443 is taken: `sudo lsof -i :443`
- Kill the conflicting process or change the port in wazuh-docker-compose.yml

**Container keeps restarting**
- Check logs: `docker logs <container_name> --tail 50`
- Usually a misconfigured environment variable

---

*Author: Aditya Suresh Acharya · AI-assisted development using Claude (Anthropic)*
