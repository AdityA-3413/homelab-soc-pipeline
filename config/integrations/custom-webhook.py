#!/usr/bin/env python3
import sys
import json
import requests

def main():
    alert_file = sys.argv[1]
    webhook_url = sys.argv[3]  # Wazuh passes: alert_file, api_key, hook_url
    
    with open(alert_file) as f:
        alert_data = json.load(f)
    
    response = requests.post(webhook_url, json=alert_data)
    sys.exit(0)

if __name__ == "__main__":
    main()
