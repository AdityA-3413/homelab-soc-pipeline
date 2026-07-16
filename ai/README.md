# AI Engine Setup Guide — Foundation-Sec-8B via Ollama

**Model:** Foundation-Sec-8B-Instruct (Q4_K_M quantization)  
**Runtime:** Ollama  
**Author:** Aditya Suresh Acharya  

---

## Why This Model?

Most AI-powered SOC projects use OpenAI or another cloud API — which means:
- Every alert costs money per API call
- Your security data leaves your network
- No internet = no AI

**Foundation-Sec-8B-Instruct** runs 100% locally on your GPU via Ollama:
- Zero per-query cost
- Your alerts never leave your machine
- Works offline on your internal network
- Purpose-built for cybersecurity classification tasks

---

## Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| GPU VRAM | 6GB | 8GB+ |
| RAM | 16GB | 32GB |
| Storage | 10GB free | 20GB free |
| OS | Windows 10/11 or Linux | Ubuntu 22.04 |

> ⚠️ This model runs on your **GPU machine** (Windows/Linux with NVIDIA GPU) — NOT on the Ubuntu VM running Wazuh. The VM just calls it over the network.

> The project was built and tested on an **NVIDIA RTX 5060 with 8GB VRAM**.

---

## The Two-Model Approach (Important — Read This)

This is how the model was set up in this project, and it's different from what most tutorials show.

**The problem:** Foundation-Sec-8B at full precision (Q8_0) is ~9GB — too large for 8GB VRAM GPUs.

**The solution used here:**
1. Download the **Q8_0 base model** from Hugging Face (higher quality weights)
2. Use the **Modelfile** in this repo to create a custom Ollama model on top of it
3. Ollama serves it using **Q4_K_M quantization** internally, reducing VRAM usage to ~5-6GB

This gives better output quality than pulling a pre-quantized Q4 model directly, because the base weights are higher quality before quantization is applied at inference time.

---

## Step 1 — Install Ollama

**Windows:**
1. Go to [https://ollama.com/download](https://ollama.com/download)
2. Download the Windows installer
3. Run it — Ollama installs as a background service
4. Open PowerShell and verify:
```powershell
ollama --version
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

---

## Step 2 — Pull the Base Model

```bash
ollama pull hf.co/fdtn-ai/Foundation-Sec-8B-Instruct-Q8_0-GGUF
```

> This downloads ~9GB. Takes 10–20 minutes depending on your connection. This is the high-quality base model.

Verify it downloaded:
```bash
ollama list
```

You should see `hf.co/fdtn-ai/Foundation-Sec-8B-Instruct-Q8_0-GGUF` in the list.

---

## Step 3 — Create the Custom Model Using the Modelfile

The `Modelfile` in this repo (`ai/Modelfile`) sets up:
- The system prompt that makes the model behave as a SOC analyst API
- Response format (JSON only)
- Temperature = 0 (deterministic, no hallucination)
- Max context and prediction limits tuned for alert classification

```bash
# Navigate to where you cloned the repo
cd homelab-soc-pipeline

# Create the custom model
ollama create foundation-sec-8b -f ai/Modelfile
```

Verify it was created:
```bash
ollama list
```

You should now see `foundation-sec-8b` in the list alongside the base model.

---

## Step 4 — Start Ollama Server

**Windows** — Ollama runs automatically as a background service after installation. Check it's running:
```powershell
ollama serve
```

If it's already running you'll see: `Error: listen tcp 127.0.0.1:11434: bind: address already in use` — that's fine, it means it's already up.

**Linux:**
```bash
ollama serve &
```

---

## Step 5 — Make Ollama Accessible From the Ubuntu VM

By default Ollama only listens on `localhost` (127.0.0.1). The Ubuntu VM needs to reach it over the network, so you need to bind it to all interfaces.

**Windows — set environment variable:**
1. Search "Environment Variables" in Start menu
2. Under System Variables → New:
   - Name: `OLLAMA_HOST`
   - Value: `0.0.0.0:11434`
3. Restart Ollama (kill it from Task Manager, reopen)

**Linux:**
```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

Or add to systemd service:
```bash
sudo systemctl edit ollama.service
# Add under [Service]:
# Environment="OLLAMA_HOST=0.0.0.0:11434"
sudo systemctl restart ollama
```

---

## Step 6 — Test the Model Directly

Before connecting to n8n, verify the model responds correctly:

```bash
curl http://localhost:11434/api/generate \
  -d '{
    "model": "foundation-sec-8b",
    "prompt": "Alert: SSH brute force detected. Source IP: 1.2.3.4. 47 attempts in 5 minutes.",
    "stream": false
  }'
```

You should get a JSON response like:
```json
{
  "threat_type": "brute_force_ssh",
  "severity": 8,
  "mitre_id": "T1110",
  "confidence": 0.95,
  "action": "block_ip"
}
```

If you get this — the model is working correctly.

---

## Step 7 — Verify n8n Can Reach Ollama

From your **Ubuntu VM**, test connectivity to your GPU machine:

```bash
curl http://<YOUR_OLLAMA_HOST_IP>:11434/api/tags
```

You should see a JSON list of your installed models including `foundation-sec-8b`.

If this fails, check:
1. Is Ollama bound to `0.0.0.0` (not just localhost)?
2. Is your firewall allowing port 11434?
3. Are both machines on the same Tailscale network?

**Windows Firewall fix (if needed):**
```powershell
New-NetFirewallRule -DisplayName "Ollama" -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow
```

---

## How n8n Connects to This Model

In the n8n workflow, the **"Build Ollama Prompt"** node sends a POST request to:

```
http://<YOUR_OLLAMA_HOST_IP>:11434/api/generate
```

With body:
```json
{
  "model": "foundation-sec-8b",
  "prompt": "<constructed from alert data>",
  "stream": false
}
```

The model responds with JSON that n8n then parses for the decision, MITRE ID, severity, confidence, and reason.

> See `n8n-workflows/README.md` for where to update this IP in the workflow.

---

## Troubleshooting

**Model responds slowly (>30 seconds)**
- Check GPU is being used: `nvidia-smi` — look for ollama process using VRAM
- If VRAM is 0, Ollama is running on CPU — check GPU drivers and CUDA installation

**"Model not found" error**
- Run `ollama list` and confirm `foundation-sec-8b` appears
- If not, re-run Step 3

**n8n gets timeout from Ollama**
- Increase the HTTP Request timeout in n8n to 60 seconds
- First inference after idle can take 10–15 seconds (model loading into VRAM)

**JSON parse errors in n8n**
- The model occasionally wraps output in backticks — the "Build Ollama Prompt" node strips these
- If errors persist, check the system prompt in the Modelfile matches exactly

**Out of VRAM error**
- Close other GPU applications (games, other models)
- Try pulling a lighter quant: `ollama pull foundation-sec-8b:q4_0` (lower quality but less VRAM)

---

## Model Performance (From Testing)

| Metric | Score |
|---|---|
| Overall accuracy | 74% (31/42 fields correct) |
| MITRE ID mapping | 86% → 100% after prompt fix |
| Action recommendation | 71% (10/14 correct) |
| Avg response time | 3–7 seconds on RTX 5060 8GB |
| Threat type accuracy | 64% (9/14 correct) |

> Full evaluation report available in `docs/Foundation_Sec_8B_Accuracy_Report.html`

---

*Author: Aditya Suresh Acharya · AI-assisted development using Claude (Anthropic)*
