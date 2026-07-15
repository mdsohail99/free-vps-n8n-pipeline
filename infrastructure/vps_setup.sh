#!/bin/bash
set -e

echo "=== Updating packages ==="
sudo apt-get update -y

echo "=== Installing iptables-persistent + python3-pip ==="
# Suppress interactive prompt for iptables-persistent on Ubuntu 24.04
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent python3-pip

echo "=== Configuring firewall rules ==="
# Disable UFW first (it may override iptables rules on Ubuntu 24.04)
sudo ufw disable 2>/dev/null || true
# Allow loopback (containers/local processes talking to 127.0.0.1)
sudo iptables -I INPUT -i lo -j ACCEPT
# Allow return traffic for connections this host initiates (docker pull, apt,
# curl, n8n's own outbound API calls). Without this, the trailing DROP below
# blocks all host-initiated outbound traffic's replies.
sudo iptables -I INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -j DROP
sudo netfilter-persistent save

echo "=== Installing Docker ==="
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu

echo "=== Setup complete! ==="
echo ""
echo "IMPORTANT: Log out (type 'exit') and log back in for Docker permissions to take effect."
echo "Then continue with README.md (or install_with_ai_agent.md Phase 5) to deploy n8n."
