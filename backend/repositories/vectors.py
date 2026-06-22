from __future__ import annotations

import time
from typing import Any

import boto3
import structlog
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from backend.core.config import get_settings
from backend.core.exceptions import VectorStoreError

logger = structlog.get_logger(__name__)

CANDIDATE_INDEX = "candidate-profiles"
JD_INDEX = "job-descriptions"
VECTOR_DIM = 1024


def _get_client() -> OpenSearch:
    settings = get_settings()
    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()
    auth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        settings.aws_region,
        "aoss",
        session_token=credentials.token,
    )
    endpoint = settings.opensearch_endpoint.replace("https://", "").rstrip("/")
    return OpenSearch(
        hosts=[{"host": endpoint, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )


# OpenSearch Serverless compatible index bodies.
# - No "knn.space_type" in settings (not supported by AOSS)
# - No "engine": "nmslib" (not supported by AOSS, use faiss)
# - space_type goes inside method.parameters for AOSS
_CANDIDATE_INDEX_BODY = {
    "settings": {
        "index": {
            "knn": True,
        }
    },
    "mappings": {
        "properties": {
            "candidate_id": {"type": "keyword"},
            "session_id": {"type": "keyword"},
            "embedding": {
                "type": "knn_vector",
                "dimension": VECTOR_DIM,
                "method": {
                    "name": "hnsw",
                    "engine": "faiss",
                    "space_type": "innerproduct",
                    "parameters": {
                        "ef_construction": 128,
                        "m": 16,
                    },
                },
            },
            "profile_text": {"type": "text"},
            "expires_at": {"type": "date", "format": "epoch_second"},
        }
    },
}

_JD_INDEX_BODY = {
    "settings": {
        "index": {
            "knn": True,
        }
    },
    "mappings": {
        "properties": {
            "jd_id": {"type": "keyword"},
            "session_id": {"type": "keyword"},
            "embedding": {
                "type": "knn_vector",
                "dimension": VECTOR_DIM,
                "method": {
                    "name": "hnsw",
                    "engine": "faiss",
                    "space_type": "innerproduct",
                    "parameters": {
                        "ef_construction": 128,
                        "m": 16,
                    },
                },
            },
            "jd_text": {"type": "text"},
            "expires_at": {"type": "date", "format": "epoch_second"},
        }
    },
}


class VectorRepository:
    def __init__(self) -> None:
        self._client = _get_client()
        self._ensure_indices()

    def _ensure_indices(self) -> None:
        for index, body in [
            (CANDIDATE_INDEX, _CANDIDATE_INDEX_BODY),
            (JD_INDEX, _JD_INDEX_BODY),
        ]:
            try:
                if not self._client.indices.exists(index=index):
                    self._client.indices.create(index=index, body=body)
                    logger.info("index_created", index=index)
                else:
                    logger.info("index_exists", index=index)
            except Exception as exc:
                logger.error("index_ensure_failed", index=index, error=str(exc))
                raise VectorStoreError(f"Failed to ensure index {index}: {exc}")

    def index_jd(
        self,
        session_id: str,
        jd_text: str,
        embedding: list[float],
        expires_at: int,
    ) -> str:
        doc_id = f"jd_{session_id}"
        try:
            resp = self._client.index(
                index=JD_INDEX,
                body={
                    "jd_id": doc_id,
                    "session_id": session_id,
                    "embedding": embedding,
                    "jd_text": jd_text[:2000],
                    "expires_at": expires_at,
                },
            )
            logger.info("jd_indexed", session_id=session_id, doc_id=resp.get("_id"))
            return resp.get("_id", doc_id)
        except Exception as exc:
            logger.error("jd_index_failed", session_id=session_id, error=str(exc))
            raise VectorStoreError(str(exc))

    def get_jd_embedding(self, session_id: str) -> list[float]:
        # OpenSearch Serverless is eventually consistent — retry with backoff
        max_attempts = 5
        delay = 2.0
        for attempt in range(max_attempts):
            try:
                resp = self._client.search(
                    index=JD_INDEX,
                    body={
                        "query": {"term": {"session_id": session_id}},
                        "size": 1,
                        "_source": ["embedding"],
                    },
                )
                hits = resp["hits"]["hits"]
                if hits:
                    return hits[0]["_source"]["embedding"]
                if attempt < max_attempts - 1:
                    logger.info(
                        "jd_embedding_not_found_retrying",
                        session_id=session_id,
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    time.sleep(delay)
                    delay *= 2
            except Exception as exc:
                logger.error("jd_embedding_fetch_failed", session_id=session_id, error=str(exc))
                raise VectorStoreError(f"JD embedding not found for session {session_id}")
        raise VectorStoreError(f"JD embedding not found for session {session_id}")

    def index_candidate(
        self,
        session_id: str,
        candidate_id: str,
        profile_text: str,
        embedding: list[float],
        expires_at: int,
    ) -> str:
        doc_id = f"cand_{candidate_id}"
        try:
            resp = self._client.index(
                index=CANDIDATE_INDEX,
                body={
                    "candidate_id": candidate_id,
                    "session_id": session_id,
                    "embedding": embedding,
                    "profile_text": profile_text[:3000],
                    "expires_at": expires_at,
                },
            )
            logger.info("candidate_indexed", candidate_id=candidate_id, doc_id=resp.get("_id"))
            return resp.get("_id", doc_id)
        except Exception as exc:
            logger.error("candidate_index_failed", candidate_id=candidate_id, error=str(exc))
            raise VectorStoreError(str(exc))

    def knn_search(
        self, session_id: str, jd_embedding: list[float], k: int = 50
    ) -> list[dict[str, Any]]:
        query = {
            "size": k,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"session_id": session_id}},
                        {"knn": {"embedding": {"vector": jd_embedding, "k": k}}},
                    ]
                }
            },
            "_source": ["candidate_id", "session_id"],
        }
        try:
            resp = self._client.search(index=CANDIDATE_INDEX, body=query)
        except Exception as exc:
            logger.error("knn_search_failed", session_id=session_id, error=str(exc))
            raise VectorStoreError(str(exc))

        results: list[dict[str, Any]] = []
        for hit in resp["hits"]["hits"]:
            results.append(
                {
                    "candidate_id": hit["_source"]["candidate_id"],
                    "cosine_score": float(hit["_score"]),
                }
            )
        return results

    def delete_by_session(self, session_id: str) -> None:
        query = {"query": {"term": {"session_id": session_id}}}
        try:
            self._client.delete_by_query(index=CANDIDATE_INDEX, body=query)
            self._client.delete_by_query(index=JD_INDEX, body=query)
        except Exception as exc:
            logger.warning("delete_by_session_failed", session_id=session_id, error=str(exc))
