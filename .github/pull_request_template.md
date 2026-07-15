## 📋 Proposed Workflow / Code Changes

*Briefly describe what this PR changes, adds, or resolves.*

---

## 🏗️ Submission Checklist

Please verify that your Pull Request adheres to the repository contribution guidelines:
- [ ] **Secrets Checked**: I have verified that no production API keys, SSH keys, passwords, or Slack webhooks are hardcoded in code, JSON files, or screenshots.
- [ ] **Category Taxonomy**: If adding a new workflow, it is placed inside `workflows/<category>/<workflow-name>/` with a clean `workflow.json` and a setup `README.md` conforming to the `WORKFLOW_TEMPLATE.md`.
- [ ] **No Unnecessary Root Files**: I have placed script configurations inside `/infrastructure` and crawler sources inside `research-engine/`.
- [ ] **Tested Successfully**: I have successfully run validation tests (e.g., using `sandbox_test.mjs` or a live self-hosted n8n runtime).
- [ ] **Standard Code Conventions**: All Python code conforms to clean-code principles and uses standard library modules where possible.
