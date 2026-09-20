"""Independent contract checks for constant-corpus-cost warm cache reads."""

from examples.company_brains.durable.engine import CompanyBrain
from examples.company_brains.durable.store import SQLiteBrainStore
from tests.test_brain2_integration import SCOPE, apply, doc, prediction


def test_warm_answer_does_not_iterate_the_authorized_corpus(tmp_path):
    class IterationForbidden(tuple):
        def __iter__(self):
            raise AssertionError("A warm cache read scanned authorized documents")

    with SQLiteBrainStore(tmp_path / "brain.sqlite") as store:
        policy = doc()
        apply(store, policy)
        brain = CompanyBrain(store, SCOPE)
        question = "Refund window?"
        brain.answer(question, user_id="alice", generate=lambda *_: prediction(policy))
        view = next(iter(brain._views.values()))
        view.documents = IterationForbidden(view.documents)
        result = brain.answer(question, user_id="alice")
        assert result["cache_hit"]
        assert result["answer"] == policy.body
