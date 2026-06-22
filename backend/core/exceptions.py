from __future__ import annotations


class TalentLensError(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class SessionNotFoundError(TalentLensError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session {session_id} not found", 404)


class CandidateNotFoundError(TalentLensError):
    def __init__(self, candidate_id: str) -> None:
        super().__init__(f"Candidate {candidate_id} not found", 404)


class RankingNotFoundError(TalentLensError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Ranking job {job_id} not found", 404)


class UnauthorizedError(TalentLensError):
    def __init__(self) -> None:
        super().__init__("Access denied to this resource", 403)


class ValidationError(TalentLensError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 422)


class BedrockError(TalentLensError):
    def __init__(self, message: str) -> None:
        super().__init__(f"AI service error: {message}", 502)


class ParseError(TalentLensError):
    def __init__(self, message: str) -> None:
        super().__init__(f"Resume parse error: {message}", 422)


class VectorStoreError(TalentLensError):
    def __init__(self, message: str) -> None:
        super().__init__(f"Vector store error: {message}", 502)
