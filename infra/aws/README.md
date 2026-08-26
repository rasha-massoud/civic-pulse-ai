# infra/aws

Actual AWS deployment bits. This is plain scripts + JSON configs, not
Terraform/CDK — intentional for a 10-week MVP timeline. If the
project continues past the capstone, this is the folder to replace with
real IaC.

## Deployment: single EC2 instance, native installs + systemd

The whole stack (Postgres, Redis, backend, dashboard) runs natively on
one EC2 instance. Postgres and Redis are installed via apt;
the backend runs via `uvicorn` and the dashboard's production build is
served as a static site, each wired up as its own systemd service so
they start on boot and restart on crash. This is a demo-appropriate
setup, not how you'd run this in production long-term.

1. Launch an EC2 instance (Ubuntu 22.04, t3.small or larger) in a VPC
   with a security group allowing inbound 22, 80/443, 8000, and 5173.
2. Attach an IAM instance role with S3 read/write on the media bucket
   (see `s3/bucket-policy.json`).
3. Run `ec2/setup.sh` on the instance (as user-data on launch, or SSH in
   and run it manually) — it installs Postgres, Redis, Python, and
   Node.js directly via apt, pulls the repo, installs backend/dashboard
   dependencies, builds the dashboard, and sets up the
   `civicpulse-backend` and `civicpulse-dashboard` systemd services.
4. Point the Meta WhatsApp Cloud API webhook callback URL at the
   instance's public HTTPS endpoint:
   `https://<public-host>/api/whatsapp/webhook`
   (subscribe to the `messages` field; use the same verify token as
   `META_WHATSAPP_WEBHOOK_VERIFY_TOKEN`).

## Local WhatsApp testing with ngrok

For local development the path is:

```text
Citizen WhatsApp
      ↓
Meta WhatsApp Cloud API
      ↓
ngrok HTTPS URL
      ↓
FastAPI  /api/whatsapp/webhook
```

1. Start the backend on port 8000.
2. Run `ngrok http 8000` and copy the HTTPS URL.
3. In Meta Developer → WhatsApp → Configuration, set the callback URL to:
   `https://<ngrok-domain>/api/whatsapp/webhook`
4. Set the verify token to match `META_WHATSAPP_WEBHOOK_VERIFY_TOKEN`.
5. Subscribe to the `messages` webhook field.
6. Fill `META_WHATSAPP_ACCESS_TOKEN` and `META_WHATSAPP_PHONE_NUMBER_ID`
   in `backend/.env` (WABA ID is `META_WHATSAPP_BUSINESS_ACCOUNT_ID` —
   do not confuse it with the Phone Number ID).

## Whisper model preparation (production)

Voice notes use **faster-whisper**. End-user requests must **never** download
model weights. Prepare the cache during deploy, before starting uvicorn:

```bash
cd backend
.venv/bin/python -m app.services.ai.prepare_whisper
```

### CPU deployment (default MVP)

```env
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_LOCAL_FILES_ONLY=true
WHISPER_PRELOAD=true
WHISPER_MAX_CONCURRENT=1
WHISPER_ALLOW_CPU_FALLBACK=false
HF_HOME=.cache/huggingface
```

### NVIDIA GPU deployment (optional)

```env
WHISPER_MODEL=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
WHISPER_LOCAL_FILES_ONLY=true
WHISPER_PRELOAD=true
WHISPER_MAX_CONCURRENT=2
WHISPER_ALLOW_CPU_FALLBACK=false
HF_HOME=.cache/huggingface
```

`prepare_whisper` validates CUDA when `WHISPER_DEVICE=cuda`. If the host has
no NVIDIA driver / CUDA-capable CTranslate2 runtime, preparation **fails**
with a clear error (it does **not** silently fall back to CPU unless
`WHISPER_ALLOW_CPU_FALLBACK=true`).

#### AWS GPU instance / runtime requirements

| Requirement | Recommendation |
|-------------|----------------|
| EC2 instance | `g4dn.xlarge` (NVIDIA T4, 16 GB GPU) is enough for `small`; `g5.xlarge` (A10G) for more headroom |
| AMI (optional) | AWS Deep Learning AMI (Ubuntu) or Ubuntu 22.04 + NVIDIA drivers |
| OS | Ubuntu 22.04 |
| NVIDIA driver | Confirm with `nvidia-smi` (driver 525+ / CUDA 12.x stack recommended) |
| CUDA / cuDNN / CTranslate2 | Linux `pip install -r requirements.txt` normally installs a CUDA-capable `ctranslate2` wheel used by faster-whisper. Verify with `python -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())"` → must be ≥1 |
| GPU memory | `small` + float16 typically needs a few GB VRAM; prefer ≥8 GB GPU RAM (T4 16 GB is comfortable) |
| System RAM | ≥8 GB host RAM (≥16 GB preferred) |
| Disk | Extra space under `HF_HOME` for model cache (~1–3 GB for `small`) |
| Model prep | **Required** before uvicorn: `python -m app.services.ai.prepare_whisper` on the GPU host with `WHISPER_DEVICE=cuda` |

Deploy steps on a GPU host:

1. Launch GPU EC2 + attach NVIDIA drivers.
2. Confirm `nvidia-smi` works.
3. Create venv, `pip install -r requirements.txt`.
4. Set Whisper GPU env vars (above).
5. Run `python -m app.services.ai.prepare_whisper` — must succeed on **cuda**.
6. Start uvicorn.
7. Check `GET /api/v1/health` → `whisper.cuda.available=true`, `whisper.device=cuda`.

Notes:

- `prepare_whisper` downloads/caches the configured model and verifies load.
- `WHISPER_LOCAL_FILES_ONLY=true` blocks runtime Hugging Face downloads.
- `WHISPER_PRELOAD=true` warms the model in a background thread so FastAPI
  readiness is not blocked; check `GET /api/v1/health` → `whisper_ready`.
- Concurrent voice notes are limited by `WHISPER_MAX_CONCURRENT`.
- Cache location: `HF_HOME` (default `.cache/huggingface` under the process CWD,
  typically `backend/.cache/huggingface`).

Health:

```text
GET /api/v1/health
→ api_ready, database, whisper_ready,
  whisper{ requested_device, device, compute_type, cuda{available,device_count,...} }
```

## Files

| Path | Purpose |
|------|---------|
| `.env.aws.example` | Placeholder list of AWS resource names/ARNs you provision once, copy to `.env.aws` (gitignored) and fill in |
| `ec2/setup.sh` | Bootstrap script for the single-instance path |
| `s3/bucket-policy.json` | Bucket policy for the media bucket (private; EC2 instance role only) |
| `s3/cors.json` | CORS rules so the dashboard can load presigned photo/voice-note URLs |

## Secrets

Real credentials (DB password, Meta access token, API keys) never go in
this folder as plaintext beyond `.env.aws.example` placeholders. They
live in the instance's `.env` (not committed).
