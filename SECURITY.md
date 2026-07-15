# 🛡️ Security Policy

We take the security of `free-vps-n8n-pipeline` and self-hosted automation infrastructure very seriously.

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability or credential exposure risk within this repository or setup scripts:

1. **Do NOT open a public GitHub Issue.**
2. Report the vulnerability privately via email or private security advisory on GitHub.
3. Include detailed steps to reproduce the issue, proof of concept, and affected configurations.

We will review your submission within **48 hours** and provide a resolution timeline.

---

## 🛡️ Best Security Practices for Self-Hosting

When deploying this stack on Oracle Cloud or any VPS host:

- 🔑 **Keep `.env` Non-Committed**: Never check in your `.env` file containing Notion tokens, OpenRouter API keys, or Slack webhooks.
- 🔐 **Use SSH Key Authentication**: Disable password authentication on your VPS host (`PasswordAuthentication no` in `/etc/ssh/sshd_config`).
- 🌐 **Expose Only Caddy Reverse Proxy**: Keep n8n bound to `127.0.0.1:5678` internally so external traffic passes strictly through Caddy's auto-HTTPS reverse proxy (ports 80/443).
