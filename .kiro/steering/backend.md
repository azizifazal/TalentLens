# TalentLens Backend — Coding Standards & Patterns

## Language & Runtime

- Python 3.12
- FastAPI with Mangum adapter: `handler = Mangum(app, lifespan="off", api_gateway_base_path=None)`
  - `api_gateway_base_path=None` is required for Lambda Function URL event format support
- Pydantic v2 for all models and settings
- structlog for all logging (structured JSON)
- ruff for linting and formatting

## Bedrock Client

The `BedrockClient` uses the **Bedrock Converse API** (not `invoke_model`):
- Text model: `amazon.nova-pro-v1:0` (Amazon Nova Pro)
- Embedding model: `amazon.titan-embed-text-v2:0` (1024 dimensions)
- Method `invoke_claude()` internally uses `client.converse()` — named `invoke_claude` for backwards compatibility with callers

## OpenSearch Serverless Rules

OpenSearch Serverless (AOSS) has restrictions compared to standard OpenSearch:

| Feature | AOSS Behavior |
|---|---|
| Document IDs | NOT supported in index/create operations — must be auto-generated |
| `refresh=True` | NOT supported — raises `status_exception` |
| `index.knn.space_type` in settings | NOT supported — raises `illegal_argument_exception` |
| `engine: nmslib` | NOT supported — use `engine: faiss` |
| Eventual consistency | Writes are NOT immediately searchable — use retry with backoff |

Correct index body pattern:
```python
{
    "settings": {"index": {"knn": True}},  # NO knn.space_type here
    "mappings": {
        "properties": {
            "embedding": {
                "type": "knn_vector",
                "dimension": 1024,
                "method": {
                    "name": "hnsw",
                    "engine": "faiss",         # faiss, not nmslib
                    "space_type": "innerproduct",  # goes here, not in settings
                    "parameters": {"ef_construction": 128, "m": 16},
                },
            }
        }
    }
}
```

Always retry `get_jd_embedding` with exponential backoff (5 attempts, starting at 2s) due to AOSS eventual consistency.

## Auth Pattern

All protected endpoints use `Depends(verify_token)` which returns `CurrentUser` dict with `user_id`.

```python
@router.get("/sessions")
async def list_sessions(current_user: CurrentUser = Depends(verify_token)):
    ...
```

JWT tokens come from Cognito. The JWKS is cached for 1 hour.

## Null-Safe AI Response Handling

Amazon Nova Pro may return `null` for numeric fields. Always use null-safe helpers:

```python
def _safe_float(val, default):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default

def _safe_list(val):
    return val if isinstance(val, list) else []
```

## DynamoDB Patterns

- All floats must be converted to `Decimal` before writing: use `floats_to_decimal()` from `dynamo_utils.py`
- All reads must convert back: use `decimals_to_float()` from `dynamo_utils.py`
- Single-table design: PK = `SESSION#{session_id}`, SK varies by entity type
- TTL attribute: `expires_at` (epoch seconds)

## Error Handling

- Domain errors extend `TalentLensError` (has `message` + `status_code`)
- FastAPI exception handlers in `main.py` convert them to JSON responses
- Never let OpenSearch/DynamoDB errors propagate as 500 — catch and wrap in domain exceptions

## Running Tests

```powershell
# Backend tests (from project root)
python -m pytest backend/tests/ -v

# Infra tests
cd infra
python -m pytest tests/ -v
```

## Deployment (Backend only)

```powershell
cd infra
.\.venv\Scripts\Activate.ps1
$env:CDK_DEFAULT_ACCOUNT="022784798053"; $env:CDK_DEFAULT_REGION="us-east-1"
cdk deploy TalentLensComputeStack --require-approval never -c "allowed_origins=https://d2ky0iqvbzxus.cloudfront.net" -c "environment=poc"
```
