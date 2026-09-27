# lambda-cicd-demo

A standalone learning repo for deploying an AWS Lambda function via GitHub
Actions CI/CD. Not tied to any other project — safe to experiment on,
break, and rebuild.

## What it does

On S3 `ObjectCreated`, the Lambda reads the object's basic metadata
(bucket, key, size, ETag, content type) and upserts a row into a
`s3_uploads` table in PostgreSQL. It's intentionally simple — the point of
this repo is the deploy pipeline, not the business logic.

## Layout

```
src/handler.py               Lambda entry point
sql/001_s3_uploads.sql       Reference schema for the target table
tests/                       Unit tests (moto for S3, mocks for DB)
requirements.txt             Runtime deps (packaged into the zip)
requirements-dev.txt         + test-only deps (boto3, pytest, moto)
.github/workflows/deploy.yml CI: test on PR, deploy on merge to main
```

## How the CI/CD pipeline works

1. **On every PR** — installs deps, runs `pytest`.
2. **On merge to `main`** — packages `src/` + runtime deps into a zip and
   calls `aws lambda update-function-code` to push it to an existing
   function.
3. **Auth** — uses GitHub OIDC to assume an AWS IAM role (no long-lived
   access keys stored as secrets).

## One-time setup (things this workflow does NOT create)

This workflow only updates code on an *existing* Lambda function. Before
the first deploy will succeed, you need to provision, once:

1. **The Lambda function itself** — name it `lambda-cicd-demo` (or change
   `FUNCTION_NAME` in the workflow) with a Python 3.12 runtime.
2. **An execution role** for the function with:
   - `secretsmanager:GetSecretValue` on your DB secret
   - VPC access if your Postgres instance is in a VPC
3. **A Secrets Manager secret** with keys `host`, `port`, `dbname`,
   `username`, `password`, and its ARN set as the Lambda's `DB_SECRET_ARN`
   environment variable.
4. **An S3 bucket notification** wired to invoke the function on
   `s3:ObjectCreated:*`.
5. **A GitHub OIDC IAM role** trusted for
   `token.actions.githubusercontent.com`, scoped to this repo, with
   `lambda:UpdateFunctionCode` + `lambda:GetFunction` on the function. Add
   its ARN as the repo secret `AWS_DEPLOY_ROLE_ARN`.

Steps 1-4 are good candidates for a follow-up exercise in CloudFormation,
SAM, or Terraform once the code-deploy pipeline itself is working.

## Local testing

```bash
pip install -r requirements-dev.txt
pytest -v
```

## Manually testing an end-to-end deploy

Once the function and role exist:
```bash
git push origin main   # triggers test + deploy
aws lambda invoke --function-name lambda-cicd-demo --payload '{}' out.json
```
