# lambda-cicd-demo

A standalone learning repo for deploying an AWS Lambda function entirely
through GitHub Actions CI/CD, using **AWS SAM** (a CloudFormation wrapper) so
the function, its role, and its S3 trigger are all created by the pipeline —
no manual console/CLI creation required. This mirrors setups where direct
resource creation in AWS is restricted and everything must go through CI/CD.

## What it does

On S3 `ObjectCreated`, the Lambda reads the object's basic metadata
(bucket, key, size, ETag, content type) and upserts a row into an
`s3_uploads` table in PostgreSQL. The logic is intentionally simple — the
point of this repo is the deploy pipeline, not the business logic.

## Layout

```
src/handler.py                Lambda entry point
src/requirements.txt          Runtime deps SAM packages into the function (mirror of the root one)
template.yaml                 SAM/CloudFormation template — defines the function, its
                               role, and the S3 bucket + trigger
sql/001_s3_uploads.sql        Reference schema for the target table
tests/                        Unit tests (moto for S3, mocks for DB)
requirements.txt              Runtime deps (used for local dev/tests)
requirements-dev.txt          + test-only deps (boto3, pytest, moto)
.github/workflows/deploy.yml  CI: test on PR, sam build + sam deploy on merge to main
```

## How the pipeline works

1. **On every PR** — installs deps, runs `pytest`.
2. **On merge to `main`**:
   - `sam build` packages `src/` (code + dependencies) into a deployable
     artifact.
   - `sam deploy` applies `template.yaml` as a CloudFormation stack —
     creating the Lambda function, its execution role, the S3 bucket, and
     the event trigger if they don't exist yet, or updating them if they
     do. `--resolve-s3` lets SAM manage its own deployment-artifact bucket,
     so nothing needs to be pre-created by hand.
3. **Auth** — GitHub OIDC assumes an AWS IAM role; no long-lived AWS keys
   stored as GitHub secrets.

Nothing in AWS is created by running a command locally — every resource
this project owns is declared in `template.yaml` and materializes only
through a pipeline run.

## What `template.yaml` declares

- **`UploadBucket`** — the S3 bucket that triggers the function
  (`lambda-cicd-demo-uploads-<account-id>`)
- **`MetadataFunction`** — the Lambda function, its execution role (scoped
  to `secretsmanager:GetSecretValue` on your DB secret + `s3:GetObject` /
  `s3:GetObjectTagging` on the bucket), and the S3 event trigger
- Optional VPC config (subnets/security groups) if your Postgres instance
  is only reachable from inside a VPC

## One-time setup outside the template

A couple of things intentionally stay outside this template because they're
shared/sensitive or owned by a separate process:

1. **The GitHub OIDC IAM role** — trusted for
   `token.actions.githubusercontent.com`, scoped to this repo, with
   permission to run CloudFormation/SAM deploys (`cloudformation:*` on this
   stack, `iam:CreateRole`/`PassRole` scoped appropriately, `lambda:*`,
   `s3:*` on the SAM-managed buckets). Add its ARN as the repo secret
   `AWS_DEPLOY_ROLE_ARN`.
2. **The Secrets Manager secret** holding DB credentials (`host`, `port`,
   `dbname`, `username`, `password`). Add its ARN as the repo secret
   `DB_SECRET_ARN` — the workflow passes it into the stack as a parameter
   rather than baking it into the template.
3. **The Postgres table** — run `sql/001_s3_uploads.sql` against your
   database once.

## Local testing (no AWS calls)

```bash
pip install -r requirements-dev.txt
pytest -v
```

## Validating the template locally (optional, needs AWS SAM CLI)

```bash
pip install aws-sam-cli
sam validate --lint
sam build          # confirms dependencies package correctly
```

`sam build`/`validate` don't require AWS credentials; `sam deploy` does, and
is what the GitHub Actions workflow runs for you.
