"""Self-check for the AI-relevance filter. Run: python test_relevance.py"""

from sources.relevance import is_ai_relevant

# Titles that leaked into the 21/11 report and must now be rejected.
NOISE = [
    "NINLIVE: The Nine Inch Nails live archive",
    "Why the Airbus A321XLR often gets stuck climbing for first few hours of flight",
    "Surprisingly Adorable Insect Portraits",
    "Microsoft's SideWinder Strategic Commander was a failed attempt",
    "If you can't explain something in simple terms, you don't understand it (2017)",
]
# Real AI stories that must survive.
AI = [
    "TML releases Inkling 2 Mini, an open-weights 26.4B transformer",
    "Language Models Can Rewrite Their Own Weights",
    "Cursor tells lawmakers it is considering phasing out Chinese open-weight AI models",
    "Anthropic's Levent Alpoge publishes an AI-aided proof of Navier-Stokes blowup",
    "llama.cpp v1.0.0: A stronger foundation for the local AI ecosystem",
]

for title in NOISE:
    assert not is_ai_relevant(title), f"should be filtered: {title}"
for title in AI:
    assert is_ai_relevant(title), f"should be kept: {title}"

print(f"ok: {len(NOISE)} noise titles filtered, {len(AI)} AI titles kept")
