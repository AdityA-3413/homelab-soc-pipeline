# Web — SOC Agent Onboarding Assistant

**Author:** Aditya Suresh Acharya

---

## What This Is

The `soc_onboarding.html` page is an AI-powered onboarding assistant for new Wazuh agents.

Instead of reading documentation, a new employee or sysadmin can:
- Open this page in their browser
- Ask questions like "How do I add a Linux agent?" or "Why is my agent showing as disconnected?"
- Get step-by-step guidance specific to THIS project's architecture

The assistant knows your full SOC setup — Tailscale network, blocker.py, iptables rules, and everything else.

---

## How It Works

```
User types question in browser
        ↓
HTML page sends request to Foundation-Sec-8B via Ollama
        ↓
Model answers based on the system prompt (which describes your full SOC)
        ↓
Answer appears in the chat interface
```

It runs entirely on your local network — no internet required, no data leaves your infrastructure.

---

## Setup

### Step 1 — Update the Ollama endpoint

Open `soc_onboarding.html` in a text editor and find:

```javascript
const OLLAMA_URL = 'http://<YOUR_WAZUH_SERVER_IP>:11434/api/generate';
```

Replace `<YOUR_WAZUH_SERVER_IP>` with your actual Ollama host IP (the GPU machine).

### Step 2 — Serve the page

The page needs to be served over HTTP, not opened as a local file (browsers block API calls from `file://`).

**Simple Python server on Ubuntu VM:**
```bash
cd /home/soc/
python3 -m http.server 8888
```

Access it at: `http://<YOUR_VM_IP>:8888/soc_onboarding.html`

**Make it persistent:**
```bash
sudo nano /etc/systemd/system/soc-onboarding.service
```

```ini
[Unit]
Description=SOC Onboarding Web Server
After=network.target

[Service]
Type=simple
User=soc
WorkingDirectory=/home/soc
ExecStart=/usr/bin/python3 -m http.server 8888
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable soc-onboarding.service
sudo systemctl start soc-onboarding.service
```

---

## Sidebar Features

The page includes a sidebar with quick-start buttons for common tasks:

| Button | What It Guides Through |
|---|---|
| Add Linux Agent | Tailscale install → Wazuh agent → blocker.py |
| Add Windows Agent | Same flow for Windows machines |
| Verify Agent | How to confirm agent shows active in Wazuh |
| Fix Disconnected | Troubleshooting disconnected agents |
| Blocker.py Setup | Installing and running the auto-block script |
| Ports & Network | Tailscale mesh, required ports, firewall rules |
| Alerts Not Reaching n8n | Integration troubleshooting |
| Employee Telegram Setup | Getting Telegram Chat ID, adding to phonebook |

---

## Onboarding Checklist

The page also shows a step-by-step checklist for new agents:

1. Install Tailscale
2. Install Wazuh Agent
3. Connect to Manager
4. Deploy blocker.py
5. Install netfilter-persistent
6. Setup ip-blocker service
7. Setup iptables-fix service
8. Add Employee Telegram

---

## For Public Repo Users

Since this page calls YOUR local Ollama instance, it won't work out of the box for others. To use it:

1. Make sure Ollama is running with Foundation-Sec-8B installed (see `ai/README.md`)
2. Update the `OLLAMA_URL` to point to your Ollama host
3. Make sure CORS is allowed — Ollama by default allows all origins

**Ollama CORS fix if needed:**
```bash
OLLAMA_ORIGINS="*" ollama serve
```

---

*Author: Aditya Suresh Acharya · AI-assisted development using Claude (Anthropic)*
