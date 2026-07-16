# Config Setup Guide — Wazuh Configuration Files

**Author:** Aditya Suresh Acharya

---

## Folder Structure

```
config/
├── certs.yml                          # SSL cert generation config
├── integrations/                      # Wazuh integration scripts
│   ├── custom-webhook.py              # Main webhook (Wazuh → n8n)
│   ├── custom-webhook                 # Shell wrapper for above
│   ├── n8n-webhook                    # n8n webhook config
│   ├── maltiverse.py                  # Threat intel (optional)
│   ├── pagerduty.py                   # PagerDuty (optional)
│   ├── virustotal.py                  # VirusTotal (optional)
│   └── slack.py                       # Slack (optional)
├── wazuh_cluster/
│   ├── local_rules.xml                # YOUR custom detection rules
│   └── wazuh_manager.conf             # Main Wazuh manager config
├── wazuh_dashboard/
│   ├── wazuh.yml                      # Dashboard → API connection
│   └── opensearch_dashboards.yml      # OpenSearch dashboard config
└── wazuh_indexer/
    ├── internal_users.yml             # Indexer user accounts
    └── wazuh.indexer.yml              # Indexer node config
```

---

## Files You MUST Update

### 1. `wazuh_dashboard/wazuh.yml`

This connects the Wazuh dashboard to the Wazuh API.

```yaml
hosts:
  - <your_host_id>:
      url: "https://wazuh.manager"
      port: 55000
      username: wazuh-wui
      password: "<CHANGE_ME_WAZUH_API_PASSWORD>"   # ← Set this
      run_as: false
enrollment.dns: "<YOUR_SERVER_IP>"                  # ← Set this
```

**`password`** → Same as `WAZUH_API_PASSWORD` in your `.env` file  
**`enrollment.dns`** → Your Ubuntu VM's IP address

---

### 2. `wazuh_cluster/local_rules.xml`

This is the most important file — your **custom detection rules** that trigger the AI pipeline.

The rules we built cover:
- SSH brute force (threshold-based)
- FIM (File Integrity Monitoring) alerts on critical paths
- Ransomware-like behavior (mass file modifications)
- Repeated authentication failures

**After deploying, restart Wazuh manager to apply rules:**
```bash
docker restart single-node-wazuh.manager-1
```

Verify rules loaded:
```bash
docker exec single-node-wazuh.manager-1 /var/ossec/bin/ossec-logtest
```

---

### 3. `wazuh_cluster/wazuh_manager.conf`

This is the main Wazuh configuration. Key section to check — the integration block:

```xml
<integration>
  <name>custom-webhook</name>
  <hook_url>http://<YOUR_SERVER_IP>:5678/webhook/wazuh-alerts</hook_url>
  <alert_format>json</alert_format>
</integration>
```

**`hook_url`** → Replace `<YOUR_SERVER_IP>` with your Ubuntu VM's IP

This tells Wazuh where to send alerts (to n8n's webhook).

---

## Files You Do NOT Need to Change

| File | Why |
|---|---|
| `opensearch_dashboards.yml` | Internal OpenSearch config, auto-handled |
| `wazuh.indexer.yml` | Indexer node config, works as-is |
| `internal_users.yml` | Default Wazuh demo users — fine for homelab |
| `certs.yml` | SSL cert template — used during initial setup only |
| `integrations/*.py` (except custom-webhook) | Stock Wazuh integrations, not used in this pipeline |

---

## How Custom Rules Work

Wazuh rules work in layers:

```
Raw log arrives at Wazuh
        ↓
Wazuh decodes it (what kind of log is this?)
        ↓
Wazuh matches it against rules (does this match a known pattern?)
        ↓
If rule matches → Alert generated
        ↓
If alert level >= threshold → Integration fires (custom-webhook.py)
        ↓
custom-webhook.py → n8n → AI analysis
```

Your `local_rules.xml` adds rules ON TOP of Wazuh's 3000+ built-in rules. You don't replace the built-in ones — you extend them.

---

## Adding Your Own Rules

Edit `local_rules.xml` and add rules inside the `<group>` tag:

```xml
<group name="local,custom">

  <!-- Example: Alert on 5+ failed SSH logins from same IP in 2 minutes -->
  <rule id="100001" level="10" frequency="5" timeframe="120">
    <if_matched_sid>5760</if_matched_sid>
    <same_source_ip />
    <description>SSH brute force attack detected</description>
    <group>authentication_failures,</group>
  </rule>

</group>
```

Rule IDs must be between `100000` and `199999` for custom rules.

After editing, restart Wazuh manager:
```bash
docker restart single-node-wazuh.manager-1
```

---

## Troubleshooting

**Alerts not triggering integrations**
- Check integration is loaded: `docker exec single-node-wazuh.manager-1 cat /var/ossec/etc/ossec.conf | grep integration`
- Run fix-integrations.sh if the integration block is missing

**Custom rules not working**
- Validate XML syntax: `docker exec single-node-wazuh.manager-1 /var/ossec/bin/ossec-logtest`
- Check for XML errors in manager logs: `docker logs single-node-wazuh.manager-1 | grep ERROR`

**Dashboard can't connect to API**
- Verify wazuh.yml has correct password and IP
- Test API directly: `curl -k -u wazuh-wui:<password> https://localhost:55000`

---

*Author: Aditya Suresh Acharya · AI-assisted development using Claude (Anthropic)*
