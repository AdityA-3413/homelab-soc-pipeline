# AI Setup Assistant — Project Context Prompt

**How to use this file:**
Upload this file to Claude (claude.ai) and say:
"You are a setup assistant for this SOC project. Help me with [your question]."

Claude will use this context to give you accurate, project-specific answers instead of generic ones.

---

## PROJECT OVERVIEW

**Name:** AI-Driven Cyber Threat Detection with Automated Threat Response  
**Author:** Aditya Suresh Acharya  
**Purpose:** Free, open-source SOC pipeline for small startups (≤50 employees)  
**GitHub:** https://github.com/AdityA-3413/homelab-soc-pipeline

---

## FULL STACK

| Component | Tool | Version | Location |
|---|---|---|---|
| SIEM | Wazuh | 4.14.2 | Ubuntu VM (Docker) |
| Automation | n8n | v12.9.3 | Ubuntu VM (Docker) |
| AI Engine | Foundation-Sec-8B-Instruct Q4_K_M | via Ollama | Windows/Linux GPU machine |
| Metrics | InfluxDB | 2.7 | Ubuntu VM (Docker) |
| Case Management | TheHive | 5 | Ubuntu VM (Docker) |
| Notifications | Telegram Bot API | — | Cloud |
| Network | Tailscale | mesh VPN | All machines |
| Auto-block | blocker.py + iptables | v3.0 | Ubuntu VM |
| Visualization | Grafana | latest | Ubuntu VM (Docker) |

---

## NETWORK ARCHITECTURE

All machines communicate over Tailscale mesh VPN.

| Machine | Role | Tailscale IP (replace with yours) |
|---|---|---|
| Ubuntu VM | Wazuh + n8n + all Docker | `<YOUR_WAZUH_SERVER_IP>` |
| Windows/Linux GPU | Ollama AI engine | `<YOUR_OLLAMA_HOST_IP>` |
| Agent machines | Monitored endpoints | `<AGENT_IP_1>`, `<AGENT_IP_2>` etc. |

---

## PIPELINE FLOW

```
1. Attack happens on monitored machine
2. Wazuh agent detects it → sends to Wazuh Manager
3. Wazuh Manager → integratord → custom-webhook.py
4. custom-webhook.py → n8n webhook (port 5678)
5. n8n extracts: source IP, agent name, rule ID, 24h count, 5min velocity
6. n8n builds prompt → sends to Foundation-Sec-8B via Ollama (port 11434)
7. AI returns JSON: decision, mitre_id, threat_type, confidence, severity, reason
8. effectiveCount = 24h_count + velocity_bonus
9. If effectiveCount >= 15 AND decision = BLOCK_IP:
   → n8n calls blocker.py (port 9999) → iptables DROP rule added
10. Telegram notification sent to responsible person (based on agent name phonebook)
11. InfluxDB gets metrics written
12. TheHive case created (if configured)
```

---

## AI DECISION ENGINE

**Model:** Foundation-Sec-8B-Instruct (Q4_K_M quantization via Ollama)  
**Temperature:** 0 (deterministic)  
**Context window:** 4096 tokens  
**Max prediction:** 200 tokens

**Output format (JSON):**
```json
{
  "decision": "BLOCK_IP",
  "mitre_id": "T1110",
  "threat_type": "brute_force_ssh",
  "confidence": 0.95,
  "severity": 8,
  "reason": "47 failed SSH attempts in 5 minutes from single source IP"
}
```

**Decisions:**
- `MONITOR` → Log only, Telegram low-priority alert
- `INVESTIGATE` → Telegram alert, analyst should check
- `BLOCK_IP` → Auto-block via iptables if effectiveCount >= 15
- `ISOLATE_HOST` → Full host isolation (Phase 2, not yet implemented)

**Auto-block formula:**
```
effectiveCount = 24h_alert_count + (5min_velocity_bonus)
if effectiveCount >= 15 → auto-block triggers
```

---

## KEY FILE PATHS (on Ubuntu VM)

```
/home/soc/wazuh-docker/single-node/          # Main Wazuh project dir
/home/soc/wazuh-docker/single-node/docker-compose.yml
/home/soc/wazuh-docker/single-node/config/wazuh_cluster/local_rules.xml
/home/soc/wazuh-docker/single-node/config/wazuh_cluster/wazuh_manager.conf
/home/soc/wazuh-docker/single-node/host-scripts/custom-webhook.py
/home/soc/n8n/docker-compose.yml
/home/soc/blocker.py
/etc/iptables/blocked-ips                    # Persistent blocked IP list
/var/lib/docker/volumes/single-node_wazuh_integrations/_data/   # Integration volume
```

---

## DOCKER CONTAINERS

```bash
# Check all containers
docker ps -a

# Container names:
single-node-wazuh.manager-1    # Wazuh Manager (ports 1514, 1515, 55000)
single-node-wazuh.indexer-1    # Wazuh Indexer (port 9200)
single-node-wazuh.dashboard-1  # Wazuh Dashboard (port 443)
n8n                            # n8n automation (port 5678)
influxdb                       # InfluxDB metrics (port 8086)
grafana                        # Grafana (port 3000)
thehive                        # TheHive case mgmt (port 9000)
```

---

## COMMON ERRORS AND FIXES

**1. Wazuh agent shows as disconnected**
- Root cause: stale client key OR iptables blocking port 1514
- Fix: re-register agent, check `iptables -L INPUT -n | grep 1514`

**2. n8n not receiving alerts from Wazuh**
- Root cause: integration files wiped after container restart
- Fix: `sudo bash scripts/fix-integrations.sh`

**3. Ollama not reachable from VM**
- Root cause: Ollama bound to localhost only
- Fix: Set `OLLAMA_HOST=0.0.0.0:11434` on GPU machine

**4. blocker.py blocking the Wazuh server itself**
- Root cause: Alert originated from wazuh-lab agent
- Fix: `PROTECTED_AGENTS = ['wazuh-lab']` in blocker.py (already included)

**5. FIM realtime alerts flooding and causing kernel lockup**
- Root cause: realtime monitoring on /tmp and /home caused too many inotify events
- Fix: Restrict realtime to `/home/soc` and `/etc/iptables` only in local_rules.xml

**6. Telegram duplicate alerts**
- Root cause: filtering on sourceIP caused dedup failures
- Fix: Key dedup on decision + agent name, not sourceIP

**7. n8n Ollama template variables not rendering**
- Root cause: Variables not being passed to HTTP Request node correctly
- Fix: Use dedicated "Build Ollama Prompt" Code node before HTTP Request

**8. Docker volume vs bind mount conflict**
- Root cause: Mixed volume types causing permission errors
- Fix: Standardize on Docker named volumes for Wazuh integrations

---

## STARTUP ORDER

Always start in this order:
1. `docker compose -f docker/wazuh-docker-compose.yml up -d`
2. `docker compose -f docker/n8n-docker-compose.yml up -d`
3. Start Ollama on GPU machine: `ollama serve`
4. `python3 scripts/blocker.py &`
5. Activate n8n workflow in UI

---

## TESTED ATTACKS

| Attack | Tool | Result |
|---|---|---|
| SSH Brute Force | Hydra from THM AttackBox | Detected + auto-blocked in 3–6s |
| File Integrity Monitoring | Custom trigger | Detected, Telegram alert sent |
| Simulated Ransomware | Atomic Red Team (ART) | Detected, INVESTIGATE decision |

---

## WHAT IS NOT YET IMPLEMENTED

- ISOLATE_HOST via Wazuh Active Response (Phase 2)
- Grafana dashboards (container running, not configured)
- TheHive ↔ n8n feedback loop (TheHive deployed, not wired)
- ML anomaly detection (needs 2–3 months of data first)

---

## HOW TO HELP A USER WITH THIS PROJECT

When someone uploads this file and asks for help:
1. Use the architecture above to give accurate, specific answers
2. Reference actual file paths, container names, and port numbers from this document
3. When troubleshooting, check the Common Errors section first
4. Always remind users to check startup order if multiple things seem broken
5. For AI/Ollama issues, refer to ai/README.md steps
6. For n8n workflow issues, refer to n8n-workflows/README.md

---

*Author: Aditya Suresh Acharya · AI-assisted development using Claude (Anthropic)*
