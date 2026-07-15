# 🤝 Contributing Guidelines

Thank you for considering contributing to `free-vps-n8n-pipeline`! We welcome contributions from developers, automation engineers, and open-source maintainers of all skill levels.

---

## 🏗️ Repository Architecture & Workflow Taxonomies

To ensure the repository remains scalable as a workflow library, all workflow submissions must follow our standardized directory layout:

```text
workflows/
└── <category>/
    └── <workflow-slug>/
        ├── README.md           ← Detailed setup guide & documentation
        ├── workflow.json       ← Production n8n workflow definition
        ├── sample.env          ← Required environment variables template
        └── screenshots/        ← Execution screenshots & node graph
```

### Supported Categories:
- `ai-intelligence/` (LLM summaries, research crawlers, model benchmarks)
- `business-ops/` (Invoice parsing, CRM syncing, email triage)
- `devops-monitoring/` (Uptime monitoring, backup automation, VPS metrics)
- `content-marketing/` (Social media scheduling, blog synthesis)

---

## 🛠️ Step-by-Step Contribution Process

1. **Fork the Repository**:
   Click **Fork** at the top right of the GitHub repository.

2. **Clone Your Fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/free-vps-n8n-pipeline.git
   cd free-vps-n8n-pipeline
   ```

3. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/my-new-workflow
   ```

4. **Add Your Contribution**:
   - Ensure your workflow `.json` file contains **zero hardcoded credentials or API keys**. Use `$env.VARIABLE_NAME` or n8n Credential pointers.
   - Test your workflow using `sandbox_test.mjs` or a live n8n instance.
   - Include high-resolution screenshots in your workflow's `screenshots/` directory.

5. **Submit a Pull Request**:
   - Push your branch to GitHub: `git push origin feature/my-new-workflow`
   - Open a Pull Request against the `master` branch of `mdsohail99/free-vps-n8n-pipeline`.

---

## 🛡️ Security Guidelines for Contributions

- ❌ **NEVER commit real API keys, tokens, SSH keys, or private webhook URLs.**
- Use `__n8n_BLANK_VALUE_<uuid>` or `$env` placeholders for all secrets.
- Verify that screenshots do not expose personal IP addresses, email addresses, or secret parameters.
