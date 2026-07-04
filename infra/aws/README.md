# infra/aws

Actual AWS deployment bits, separate from the root `docker-compose.yml`
(which is local-dev only). This is plain scripts + JSON configs, not
Terraform/CDK — intentional for a 10-week MVP timeline. If the
project continues past the capstone, this is the folder to replace with
real IaC.

## Deployment: single EC2 instance + docker compose

The whole stack (Postgres, Redis, backend, dashboard) runs as containers
on one EC2 instance via the root `docker-compose.yml`, pointed at a real
`.env`. This is a demo-appropriate setup, not how you'd run this in
production long-term.

1. Launch an EC2 instance (Ubuntu 22.04, t3.small or larger) in a VPC
   with a security group allowing inbound 22, 80/443, and 8000.
2. Attach an IAM instance role with S3 read/write on the media bucket
   (see `s3/bucket-policy.json`).
3. Run `ec2/setup.sh` on the instance (as user-data on launch, or SSH in
   and run it manually) — it installs Docker, pulls the repo, and brings
   the stack up.
4. Point the WhatsApp Business API webhook (Twilio) at the instance's
   public URL.

## Files

| Path | Purpose |
|------|---------|
| `.env.aws.example` | Placeholder list of AWS resource names/ARNs you provision once, copy to `.env.aws` (gitignored) and fill in |
| `ec2/setup.sh` | Bootstrap script for the single-instance path |
| `s3/bucket-policy.json` | Bucket policy for the media bucket (private; EC2 instance role only) |
| `s3/cors.json` | CORS rules so the dashboard can load presigned photo/voice-note URLs |

## Secrets

Real credentials (DB password, Twilio auth token, API keys) never go in
this folder as plaintext beyond `.env.aws.example` placeholders. They
live in the instance's `.env` (not committed).
