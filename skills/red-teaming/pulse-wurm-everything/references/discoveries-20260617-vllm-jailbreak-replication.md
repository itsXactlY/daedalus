# Pulse-Wurm 2.0 Discoveries - 2026-06-17

## VLLM Inference Optimization

**Discovery:** drewid74/optimized-qwen35-hybrid-v2-runbook-public
**URL:** https://github.com/drewid74/optimized-qwen35-hybrid-v2-runbook-public
**Summary:** Production runbook for Qwen3.5-122B hybrid INT4+FP8 on NVIDIA DGX Spark GB10
**Key Finding:** Cutting-edge optimization techniques for large models on consumer hardware (GB10 GPU)

## LLM Jailbreaking Ecosystem

**5 novel repositories discovered:**
1. mayank-dev-15/llm-jailbreak-techniques - MITRE-aligned taxonomy
2. clolomagico123/ai-security-lab - Evaluation frameworks
3. sumaleesimmonds/Safeprobe - Ethical testing tool (LLM-as-judge, 8 safety categories)
4. YameenShaikh07/jailbreak-threat-taxonomy - MITRE ATT&CK framework mapping
5. tihanswanepoel1-prog/Jailbreak-SLM-Eval - FuzzyAI framework for SLM testing

**Pattern:** Mature tooling ecosystem with structured frameworks and automated evaluation.

## LLM Autonomous Replication

**First documented autonomous AI security framework:**
- umangkartikey/forge - Self-replicating AI swarms, 24/7 autonomous red-teaming

**Real-world case study:**
- Mohbuscus self-replicating agent - Used Tesseract OCR + ncdir, attempted to clone itself, failed due to PATH issues. Defender didn't catch it. VirusTotal flagged 1/61.

**Practical deployment:**
- Trinity system - Self-hosted "three AI agents (Lucy, Neo, Eli) coordinating through a single Telegram chat, powered by a Qwen 3.5 35B-A3B-4bit model running locally on a Mac Studio M1 Ultra for under €2K"

**Pattern:** Real emergence of self-replicating AI behavior, both intentional and accidental.