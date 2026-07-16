# n8n Workflow — Setup & Configuration Guide

**Workflow:** Wazuh SOC Dashboard STABLE v12.9.12  
**Nodes:** 42  
**Author:** Aditya Suresh Acharya  

---

## What This Workflow Does

This is the brain of the entire SOC pipeline. It:

1. Receives alerts from Wazuh via custom-webhook.py
2. Extracts IP address, agent name, alert rule, and 24h/5min event counts
3. Builds a prompt and sends it to Foundation-Sec-8B (local LLM via Ollama)
4. AI returns: decision, MITRE ID, threat type, confidence, severity, reason
5. Based on decision:
   - `BLOCK_IP` → calls blocker.py on port 9999 → iptables drop rule added
   - `ISOLATE_HOST` → calls blocker.py isolate endpoint
   - `MONITOR` / `INVESTIGATE` → Telegram alert only
6. Writes all results to InfluxDB for metrics
7. Sends formatted Telegram message to the right person based on agent name

---

## How to Import

1. Open n8n at `http://<YOUR_WAZUH_SERVER_IP>:5678`
2. Click **"+"** (New Workflow) → top right
3. Click the **"..."** menu → **Import from file**
4. Select `Wazuh_SOC_Dashboard_STABLE_CPY_v12_9_12.json`
5. Click **Save** then **Activate** (toggle top right)

---

## ⚠️ Fields You MUST Update After Import

After importing, open each node below and replace the placeholder values with your own.

---

### 1. `BLOCKER_URL` — in the "Action Execution" Code node

**What it is:** The URL where blocker.py is listening for block/isolate commands.

**Find:** `http://<YOUR_WAZUH_SERVER_IP>:9999`  
**Replace with:** `http://<YOUR_UBUNTU_VM_IP>:9999`

**Example:** `http://192.168.1.100:9999`

> This must be your Ubuntu VM's IP — the machine running blocker.py. If using Tailscale, use the Tailscale IP of your VM.

---

### 2. Ollama AI Connection — in the "Build Ollama Prompt" / HTTP Request node

**What it is:** The URL where Foundation-Sec-8B is running via Ollama.

**Find:** `http://<YOUR_OLLAMA_HOST_IP>:11434`  
**Replace with:** Your GPU machine's IP on port 11434

**Example:** `http://192.168.1.50:11434`

> This is the machine running `ollama serve` — NOT the Ubuntu VM. This is your Windows/Linux machine with the NVIDIA GPU.

---

### 3. Telegram Bot Token — in Telegram HTTP Request nodes

**Affected nodes:** `Employee Known?`, `HTTP Request1`, `Poll Schedule`, `Process Updates`, `If1`

**What it is:** Your Telegram bot's API token from BotFather.

**Find:** `<YOUR_TELEGRAM_BOT_TOKEN>`  
**Replace with:** Your actual token

**Format:** `1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ`

**How to get it:**
1. Open Telegram → search `@BotFather`
2. Send `/newbot`
3. Follow prompts → BotFather gives you the token
4. Copy it exactly including the number before the colon

---

### 4. InfluxDB Token — in InfluxDB HTTP Request node

**What it is:** The admin token for writing metrics to InfluxDB.

**Find:** `<YOUR_INFLUXDB_TOKEN>`  
**Replace with:** Your InfluxDB admin token

**How to get it:**
1. Open InfluxDB at `http://<YOUR_WAZUH_SERVER_IP>:8086`
2. Login → Data → API Tokens
3. Copy the admin token (or generate a new one with write access to `wazuh_alerts` bucket)

---

### 5. Telegram Phonebook — in the "Extract IP Address" Code node

**What it is:** A mapping of agent names to Telegram chat IDs, so alerts go to the right person.

**Find:**
```javascript
const phonebook = {
  'wazuh-lab': '<YOUR_TELEGRAM_CHAT_ID>',
  'winpulkit': '<EMPLOYEE_TELEGRAM_CHAT_ID>',
  'linux-labratter': '<YOUR_TELEGRAM_CHAT_ID>'
};
```

**Replace with:** Your actual agent names and Telegram chat IDs

**How to get your Telegram Chat ID:**
1. Search `@userinfobot` on Telegram
2. Send it any message
3. It replies with your Chat ID (a number like `1234567890`)

**How to add more employees:**
```javascript
const phonebook = {
  'server-name': 'chat_id_of_person_responsible',
  'laptop-name': 'chat_id_of_another_person'
};
```

> Agent name must match exactly what appears in Wazuh as the agent name.

---

## Auto-Block Logic

The workflow uses this formula to decide whether to auto-block:

```
effectiveCount = 24h_alert_count + (5min_velocity_bonus)
if effectiveCount >= 15 → decision = BLOCK_IP (automatic)
```

You can adjust the threshold `15` in the "AI Decision Engine" Code node if you want to make it more or less aggressive.

---

## Workflow Dependencies

This workflow requires all of the following to be running:

| Service | Where | Port |
|---|---|---|
| Wazuh Manager | Ubuntu VM | 55000 |
| n8n | Ubuntu VM | 5678 |
| Ollama + Foundation-Sec-8B | GPU Machine | 11434 |
| InfluxDB | Ubuntu VM | 8086 |
| blocker.py | Ubuntu VM | 9999 |
| Telegram Bot | Telegram servers | — |

Start them in this order:
1. Wazuh (docker compose)
2. n8n (docker compose)  
3. Ollama (`ollama serve` on GPU machine)
4. blocker.py (`python3 scripts/blocker.py`)

---

## Testing the Pipeline

Once everything is running, test with a simple curl from any machine on your network:

```bash
# Simulate a Wazuh alert hitting n8n
curl -X POST http://<YOUR_WAZUH_SERVER_IP>:5678/webhook/wazuh-alerts \
  -H "Content-Type: application/json" \
  -d '{"rule":{"id":"5763","description":"SSH brute force"},"agent":{"name":"test-agent"},"data":{"srcip":"1.2.3.4"}}'
```

You should see:
1. n8n execution starts
2. Telegram message arrives within 3–6 seconds
3. InfluxDB gets a new data point
4. If effectiveCount ≥ 15, blocker.py drops the IP

---

*Author: Aditya Suresh Acharya · AI-assisted development using Claude (Anthropic)*
