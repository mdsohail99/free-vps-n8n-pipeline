# 📊 Launch Intelligence Report (Sample)

**Launch ID**: `2026-07-v1-launch`  
**Report Generated**: `2026-07-16`

---

## 📈 High-Level Metrics

| Metric | Value | Details |
| :--- | :--- | :--- |
| **Total Comments** | 58 | Across all tracked platforms |
| **Sentiment Index** | 89% Positive | Highly favorable launch response |
| **Top Platform** | Reddit (r/selfhosted) | Highest comment engagement |
| **Bug Reports Detected** | 3 | Grouped in `recommendations.md` |
| **Roadmap Candidates** | 4 | Feature request suggestions |

---

## 📊 Platform Distribution & Sentiment

```text
Reddit (r/selfhosted): ████████████████████ 32 comments (92% positive)
Hacker News:          █████████████ 18 comments (85% positive)
Twitter / X:          ████ 6 comments (90% positive)
LinkedIn:             ██ 2 comments (100% positive)
```

---

## 💬 Highlight Testimonials (Praise Quotes)

> "This is exactly what I wanted. A completely free self-hosted daily news summary that writes into my Notion board without paying monthly SaaS fees. Stellar setup guide!"  
> — **u/dev_enthusiast** (*Reddit*)

> "The iptables documentation is gold. I spent three days troubleshooting the same outbound silent drop issue. Thanks for sharing the Docker network config!"  
> — **@infra_guy** (*Twitter/X*)

---

## 💡 Documentation Gaps & FAQ Candidates

1. **How to run n8n behind an existing Nginx reverse proxy?**
   * *Evidence*: 4 users on Reddit asked if they can replace the Caddy service with their existing Nginx proxy.
   * *Recommendation*: Add a `docs/reverse-proxy/nginx.md` guide explaining how to forward ports 5678 to the n8n Docker container.
2. **What is the CPU usage on Oracle ARM 1-Core VPS?**
   * *Evidence*: 3 users on HN questioned if Python SSH scraper causes high CPU utilization.
   * *Recommendation*: Document that the research scraper script consumes <5% CPU and runs in less than 30 seconds.
