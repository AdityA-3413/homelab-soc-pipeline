# 🛡️ AI-Driven Cyber Threat Detection with Automated Threat Response

> A free, open-source SOC pipeline for small startups — AI makes the call, the system blocks the threat, your analyst sleeps through it.

**By Aditya Suresh Acharya** · AI-assisted development using Claude (Anthropic)

---

## ⚡ What This Does

An attacker launches a brute-force SSH attack against your server.

Within **3–6 seconds**:
1. **Wazuh** detects the attack and fires an alert
2. **n8n** picks it up and sends it to the AI engine
3. **Foundation-Sec-8B** (local LLM) classifies the threat, maps it to MITRE ATT&CK, and decides: `MONITOR / INVESTIGATE / BLOCK_IP / ISOLATE_HOST`
4. If threshold is met → **blocker.py** drops the attacker's IP via iptables — automatically, no analyst needed
5. **Telegram** notifies your team instantly
6. **InfluxDB** logs everything for trend analysis

No cloud dependency. No per-alert cost. Runs on a homelab laptop.

---

## 🎯 Built For

Small startups (≤50 employees) that need real security monitoring but can't afford enterprise SOC tools costing thousands per month. This stack runs **completely free**, on hardware you already own.

---

## 🏗️ Architecture

```
Wazuh SIEM (Docker)
      │
      ▼
custom-webhook.py  ←── Wazuh integratord
      │
      ▼
n8n Automation (42-node pipeline)
      │
      ├──► Foundation-Sec-8B via Ollama (local LLM)
      │         └── Decision: MONITOR / INVESTIGATE / BLOCK_IP / ISOLATE_HOST
      │
      ├──► blocker.py (iptables auto-block, port 9999)
      ├──► Telegram (real-time analyst alerts)
      ├──► InfluxDB (metrics + logging)
      └──► TheHive (case management)
```

**Network:** All components communicate over Tailscale mesh — no public ports exposed.

---

## 🧰 Tech Stack

| Component | Tool | Version |
|---|---|---|
| SIEM | Wazuh | 4.14.2 |
| Automation | n8n | v12.9.3 |
| AI Engine | Foundation-Sec-8B-Instruct (Q4_K_M) | via Ollama |
| Metrics | InfluxDB | 2.7 |
| Case Management | TheHive | 5 |
| Notifications | Telegram Bot API | — |
| Network | Tailscale | mesh VPN |
| Auto-block | blocker.py + iptables | v3.0 |

---

## ✅ Verified Attack Coverage

Tested end-to-end with real attacks:

| Attack | Tool Used | Detection Time | Response |
|---|---|---|---|
| SSH Brute Force | Hydra (THM AttackBox) | ~3–6 seconds | Auto IP block |
| File Integrity Monitoring | Custom FIM trigger | Real-time | Telegram alert |
| Simulated Ransomware | ART framework | Real-time | INVESTIGATE alert |

---

## 🤖 AI Decision Engine

Foundation-Sec-8B-Instruct runs **locally on your GPU via Ollama** — no OpenAI API, no cloud, no per-query cost.

Every alert gets classified with:
- `decision` — MONITOR / INVESTIGATE / BLOCK_IP / ISOLATE_HOST
- `mitre_id` — MITRE ATT&CK technique ID
- `threat_type` — what kind of attack
- `confidence` — 0.0 to 1.0
- `severity` — 1 to 10
- `reason` — plain English explanation

**Auto-block logic:** `effectiveCount = 24h_count + 5min_velocity_bonus` → if ≥ 15, IP is blocked automatically.

---

## 📋 Prerequisites

- Ubuntu 22.04 VM (minimum 4GB RAM, 40GB disk)
- Windows/Linux machine with NVIDIA GPU (8GB VRAM minimum) for Ollama
- Tailscale account (free tier works)
- Telegram Bot token
- Docker + Docker Compose

---

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/AdityA-3413/homelab-soc-pipeline.git
cd homelab-soc-pipeline
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your values:
# - TELEGRAM_BOT_TOKEN
# - INFLUXDB_TOKEN
# - Wazuh passwords
# - Your Tailscale/server IPs
```

### 3. Start Wazuh
```bash
cd docker/
docker compose -f wazuh-docker-compose.yml up -d
```

### 4. Start n8n + InfluxDB
```bash
docker compose -f n8n-docker-compose.yml up -d
```

### 5. Set up the AI engine (on your GPU machine)
```bash
ollama create foundation-sec-8b -f ai/Modelfile
ollama serve
```

### 6. Import n8n workflow
- Open n8n at `http://<your-server>:5678`
- Go to Settings → Import workflow
- Import `n8n-workflows/workflows.json`

### 7. Start blocker.py
```bash
python3 scripts/blocker.py &
```

### 8. Fix integration persistence
```bash
sudo bash scripts/fix-integrations.sh
sudo systemctl enable wazuh-integrations-fix.service
```

---

## 📁 Repo Structure

```
homelab-soc-pipeline/
├── README.md
├── LICENSE
├── .env.example
├── .gitignore
├── docker/
│   ├── wazuh-docker-compose.yml
│   └── n8n-docker-compose.yml
├── config/
│   ├── wazuh_cluster/         # Wazuh manager config + custom rules
│   ├── wazuh_dashboard/       # Dashboard config
│   ├── wazuh_indexer/         # Indexer config
│   └── integrations/          # Wazuh integration scripts
├── scripts/
│   ├── blocker.py             # Auto IP block engine (v3.0)
│   ├── custom-webhook.py      # Wazuh → n8n bridge
│   ├── fix-integrations.sh    # Integration persistence fix
│   └── init-integration.sh
├── ai/
│   └── Modelfile              # Foundation-Sec-8B Ollama config
├── n8n-workflows/
│   └── workflows.json         # Full 42-node n8n pipeline export
└── docs/
    ├── Foundation_Sec_8B_Accuracy_Report.html
    ├── SOC_Architecture_Diagram.html
    ├── Project_Technical_Brief.html
    └── Wazuh_SOC_Attack_Coverage.html
```

---

## 📊 Performance

- **AI accuracy:** 74% overall (86% MITRE mapping, 100% after prompt fix)
- **Detection latency:** 3–6 seconds end-to-end
- **Pipeline:** 42 n8n nodes, maxConcurrency: 1
- **Auto-block threshold:** effectiveCount ≥ 15

---

## 🗺️ Roadmap

- [x] Wazuh SIEM + custom rules
- [x] n8n automation pipeline
- [x] Foundation-Sec-8B local AI integration
- [x] Auto-block via iptables
- [x] Telegram notifications
- [x] InfluxDB metrics
- [x] TheHive case management
- [ ] ISOLATE_HOST via Wazuh Active Response (Phase 2)
- [ ] Grafana dashboard
- [ ] Analyst feedback loop (L2 AI upgrade)
- [ ] ML anomaly detection (L3 — needs 2–3 months data)

---

## ⚠️ Known Limitations

- Requires a GPU machine for local LLM inference (CPU inference is very slow)
- TheHive integration is deployed but analyst feedback loop not yet wired into n8n
- Grafana is running but dashboards are not configured
- Auto-block excludes the Wazuh server itself (self-isolation guard)

---

## 📄 License

MIT License — free to use, modify, and deploy. Attribution appreciated.

---

## 👤 Author

**Aditya Suresh Acharya**
Final Year B.Tech CSE · Cybersecurity Specialization
GitHub: [@AdityA-3413](https://github.com/AdityA-3413)

*AI-assisted development using Claude (Anthropic) as pair-programmer and architecture collaborator throughout the build.*

---

> *"Built because enterprise SOC tools cost more per month than a startup's entire IT budget."*
