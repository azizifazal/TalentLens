from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from backend.models.session import JDRequirements, SessionStatus


def _create_table(dynamodb):
    return dynamodb.create_table(
        TableName="talentlens-main",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture
def dynamodb_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)
        table.meta.client.get_waiter("table_exists").wait(TableName="talentlens-main")
        yield table


class TestSessionRepository:
    def test_create_and_get_session(self, dynamodb_table):
        from backend.repositories.sessions import SessionRepository

        repo = SessionRepository()
        session = repo.create(user_id="user-1", job_title="Backend Engineer", session_id="sess-1")

        assert session.session_id == "sess-1"
        assert session.user_id == "user-1"
        assert session.status == SessionStatus.CREATED

        fetched = repo.get("sess-1", "user-1")
        assert fetched.session_id == "sess-1"
        assert fetched.job_title == "Backend Engineer"

    def test_get_nonexistent_session_raises(self, dynamodb_table):
        from backend.core.exceptions import SessionNotFoundError
        from backend.repositories.sessions import SessionRepository

        repo = SessionRepository()
        with pytest.raises(SessionNotFoundError):
            repo.get("nonexistent-id")

    def test_get_with_wrong_user_raises_unauthorized(self, dynamodb_table):
        from backend.core.exceptions import UnauthorizedError
        from backend.repositories.sessions import SessionRepository

        repo = SessionRepository()
        repo.create(user_id="user-1", job_title="Engineer", session_id="sess-2")

        with pytest.raises(UnauthorizedError):
            repo.get("sess-2", "user-2")

    def test_update_jd_persists_requirements(self, dynamodb_table):
        from backend.repositories.sessions import SessionRepository

        repo = SessionRepository()
        repo.create(user_id="user-1", job_title="Engineer", session_id="sess-3")

        req = JDRequirements(
            required_skills=["Python", "AWS"],
            success_traits=["self-starter"],
        )
        repo.update_jd("sess-3", "Full JD text here", req, "jd_sess-3")

        updated = repo.get("sess-3")
        assert updated.status == SessionStatus.JD_ANALYZED
        assert updated.jd_requirements is not None
        assert updated.jd_requirements.required_skills == ["Python", "AWS"]

    def test_increment_candidate_count(self, dynamodb_table):
        from backend.repositories.sessions import SessionRepository

        repo = SessionRepository()
        repo.create(user_id="user-1", job_title="Engineer", session_id="sess-4")
        repo.increment_candidate_count("sess-4")
        repo.increment_candidate_count("sess-4")

        updated = repo.get("sess-4")
        assert updated.candidate_count == 2
        assert updated.status == SessionStatus.INGESTING

    def test_list_by_user_returns_only_their_sessions(self, dynamodb_table):
        from backend.repositories.sessions import SessionRepository

        repo = SessionRepository()
        repo.create(user_id="user-A", job_title="Job 1", session_id="sess-a1")
        repo.create(user_id="user-A", job_title="Job 2", session_id="sess-a2")
        repo.create(user_id="user-B", job_title="Job 3", session_id="sess-b1")

        results = repo.list_by_user("user-A")
        assert len(results) == 2
        session_ids = {s.session_id for s in results}
        assert session_ids == {"sess-a1", "sess-a2"}


class TestCandidateRepository:
    def test_create_and_get_candidate(self, dynamodb_table):
        from backend.repositories.candidates import CandidateRepository
        from backend.models.candidate import ParseStatus

        repo = CandidateRepository()
        candidate = repo.create(
            session_id="sess-1",
            candidate_id="cand-1",
            file_name="resume.pdf",
            s3_key="uploads/sess-1/cand-1/original.pdf",
        )
        assert candidate.parse_status == ParseStatus.QUEUED

        fetched = repo.get("sess-1", "cand-1")
        assert fetched.candidate_id == "cand-1"
        assert fetched.file_name == "resume.pdf"

    def test_update_status_to_error(self, dynamodb_table):
        from backend.repositories.candidates import CandidateRepository
        from backend.models.candidate import ParseStatus

        repo = CandidateRepository()
        repo.create("sess-1", "cand-2", "bad.pdf", "uploads/sess-1/cand-2/original.pdf")
        repo.update_status("sess-1", "cand-2", ParseStatus.ERROR, error="Corrupt file")

        fetched = repo.get("sess-1", "cand-2")
        assert fetched.parse_status == ParseStatus.ERROR
        assert fetched.parse_error == "Corrupt file"

    def test_list_by_session_returns_all_candidates(self, dynamodb_table):
        from backend.repositories.candidates import CandidateRepository

        repo = CandidateRepository()
        repo.create("sess-5", "cand-a", "a.pdf", "uploads/sess-5/cand-a/original.pdf")
        repo.create("sess-5", "cand-b", "b.pdf", "uploads/sess-5/cand-b/original.pdf")

        results = repo.list_by_session("sess-5")
        assert len(results) == 2

    def test_get_nonexistent_candidate_raises(self, dynamodb_table):
        from backend.core.exceptions import CandidateNotFoundError
        from backend.repositories.candidates import CandidateRepository

        repo = CandidateRepository()
        with pytest.raises(CandidateNotFoundError):
            repo.get("sess-1", "does-not-exist")
