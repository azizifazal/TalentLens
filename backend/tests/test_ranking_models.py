from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from backend.models.ranking import RankingWeights, RankRequest


class TestRankingWeights:
    def test_default_weights_sum_to_one(self):
        weights = RankingWeights()
        assert weights.validate_sum() is True

    def test_default_weight_values_match_spec(self):
        weights = RankingWeights()
        assert weights.semantic == 0.30
        assert weights.skills == 0.25
        assert weights.trajectory == 0.25
        assert weights.behavioral == 0.20

    def test_custom_weights_summing_to_one_are_valid(self):
        weights = RankingWeights(semantic=0.40, skills=0.20, trajectory=0.20, behavioral=0.20)
        assert weights.validate_sum() is True

    def test_weights_not_summing_to_one_fail_validation(self):
        weights = RankingWeights(semantic=0.50, skills=0.50, trajectory=0.50, behavioral=0.50)
        assert weights.validate_sum() is False

    def test_weight_above_one_raises_validation_error(self):
        with pytest.raises(PydanticValidationError):
            RankingWeights(semantic=1.5)

    def test_negative_weight_raises_validation_error(self):
        with pytest.raises(PydanticValidationError):
            RankingWeights(semantic=-0.1)


class TestRankRequest:
    def test_default_top_n(self):
        req = RankRequest()
        assert req.top_n == 20

    def test_top_n_below_minimum_raises_error(self):
        with pytest.raises(PydanticValidationError):
            RankRequest(top_n=2)

    def test_top_n_above_maximum_raises_error(self):
        with pytest.raises(PydanticValidationError):
            RankRequest(top_n=100)

    def test_valid_top_n_accepted(self):
        req = RankRequest(top_n=30)
        assert req.top_n == 30
