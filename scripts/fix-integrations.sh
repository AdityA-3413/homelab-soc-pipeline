#!/bin/bash
# Fix Wazuh integrations permissions on startup
echo "Fixing integration permissions..."
chown -R root:999 /var/lib/docker/volumes/single-node_wazuh_integrations/_data/
chmod 750 /var/lib/docker/volumes/single-node_wazuh_integrations/_data/
chmod 750 /var/lib/docker/volumes/single-node_wazuh_integrations/_data/*
echo "Integration permissions fixed!"
