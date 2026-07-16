# Scripts Setup Guide — blocker.py & iptables Auto-Block

**Author:** Aditya Suresh Acharya

---

## What's In This Folder

| File | Purpose |
|---|---|
| `blocker.py` | Listens on port 9999, receives block/isolate commands from n8n, applies iptables rules |
| `custom-webhook.py` | Receives alerts from Wazuh integratord and forwards them to n8n |
| `fix-integrations.sh` | Fixes Wazuh integration persistence after container restarts |
| `init-integration.sh` | Initial setup script for Wazuh integrations |

---

## blocker.py — How It Works

blocker.py is a lightweight HTTP server running on port 9999 on your Ubuntu VM.

When n8n decides to `BLOCK_IP` or `ISOLATE_HOST`:
1. n8n sends a POST request to `http://<VM_IP>:9999/block`
2. blocker.py receives it
3. Runs `iptables -I INPUT 1 -s <attacker_ip> -j DROP`
4. Saves the blocked IP to `/etc/iptables/blocked-ips`
5. Returns success/failure back to n8n

**Key detail:** The rule is inserted at position 1 (`-I INPUT 1`) — meaning it goes BEFORE the Tailscale rules. This ensures the block actually works even in complex iptables setups.

---

## Step 1 — Install Dependencies

```bash
pip3 install flask --break-system-packages
```

---

## Step 2 — Run blocker.py

```bash
python3 /home/soc/scripts/blocker.py &
```

Verify it's listening:
```bash
curl http://localhost:9999/status
```

Should return: `{"status": "running"}`

---

## Step 3 — Make It Persist After Reboot

Create a systemd service so blocker.py starts automatically:

```bash
sudo nano /etc/systemd/system/blocker.service
```

Paste this:
```ini
[Unit]
Description=SOC IP Blocker Service
After=network.target

[Service]
Type=simple
User=soc
ExecStart=/usr/bin/python3 /home/soc/scripts/blocker.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable blocker.service
sudo systemctl start blocker.service
sudo systemctl status blocker.service
```

---

## Step 4 — Make iptables Rules Persist After Reboot

By default iptables rules are wiped on reboot. Fix this:

```bash
sudo apt install iptables-persistent -y
sudo netfilter-persistent save
```

Blocked IPs are also saved to `/etc/iptables/blocked-ips` by blocker.py — this file is read on startup to restore previous blocks.

---

## Step 5 — Fix Wazuh Integration Persistence

After every Wazuh container restart, the integration files get wiped. The fix-integrations.sh script and its systemd service handle this automatically:

```bash
sudo bash scripts/fix-integrations.sh
sudo systemctl enable wazuh-integrations-fix.service
sudo systemctl start wazuh-integrations-fix.service
```

---

## Important: Self-Isolation Guard

blocker.py has a built-in guard that **prevents the Wazuh server from blocking itself.**

If n8n sends a block command for an alert originating from `wazuh-lab` (the VM itself), blocker.py ignores it. This was a real bug we hit — the server was blocking its own Tailscale traffic and going offline.

If your VM has a different hostname, update this line in `blocker.py`:
```python
PROTECTED_AGENTS = ['wazuh-lab']
```

Add your VM's hostname to this list.

---

## Viewing Blocked IPs

```bash
# See all currently blocked IPs in iptables
sudo iptables -L INPUT -n | grep DROP

# See the persistent blocked IPs list
cat /etc/iptables/blocked-ips
```

## Unblocking an IP

```bash
sudo iptables -D INPUT -s <ip_address> -j DROP
```

---

## custom-webhook.py — How It Works

This script sits between Wazuh's integratord and n8n.

Wazuh calls it when an alert fires → it forwards the alert JSON to n8n's webhook URL.

**After importing, update this line in custom-webhook.py:**
```python
N8N_WEBHOOK_URL = "http://<YOUR_WAZUH_SERVER_IP>:5678/webhook/wazuh-alerts"
```

Replace `<YOUR_WAZUH_SERVER_IP>` with your Ubuntu VM's IP.

---

## Troubleshooting

**blocker.py not receiving commands from n8n**
- Check blocker.py is running: `ps aux | grep blocker`
- Check port 9999 is open: `sudo netstat -tlnp | grep 9999`
- Check firewall: `sudo iptables -L INPUT -n`

**iptables rules not persisting after reboot**
- Run: `sudo netfilter-persistent save`
- Verify: `sudo systemctl status netfilter-persistent`

**Wazuh alerts not reaching n8n**
- Check integratord is running inside container: `docker exec single-node-wazuh.manager-1 ps aux | grep integratord`
- Run fix-integrations.sh again: `sudo bash scripts/fix-integrations.sh`
- Check integration file exists: `ls /var/lib/docker/volumes/single-node_wazuh_integrations/_data/`

---

*Author: Aditya Suresh Acharya · AI-assisted development using Claude (Anthropic)*
