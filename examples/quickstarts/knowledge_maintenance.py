"""Complete fixture-only host: messages -> episodes -> topics -> search.

Run with python -m examples.quickstarts.knowledge_maintenance. The host owns
selection, grouping policy, model callbacks, atomic storage and authorization.
No conversation_topics dependency: that optional work remains independent.
"""

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from mari_components import (
    CountReducer,
    DeltaAggregate,
    DependencyIndex,
    DependencyKey,
    DependencyStamp,
    DerivationSpec,
    GroupIdentity,
    LexicalStatisticsReducer,
    MembershipReducer,
    ObjectRef,
    ScopeRef,
    SelectionSpec,
    UpdateAction,
    WeightedVectorReducer,
    complete_selection,
    dependency_fingerprint,
    materialization_receipt,
    plan_selection,
    reconcile_groups,
)
from mari_components.conversation_knowledge import (
    EpisodeKnowledge,
    KnowledgeEvent,
    evidence_context,
    parse_episode_knowledge,
    segment_conversations,
)
from mari_components.knowledge import ArtifactRef
from mari_components.retrieval import RetrievalUnit, RevisionBM25Index

SCOPE = ScopeRef(tenant="acme", space="support")


def object_ref(name: str, namespace: str) -> ObjectRef:
    return ObjectRef(scope=SCOPE, namespace=namespace, object_id=name)


def event_ref(event: KnowledgeEvent) -> ObjectRef:
    return object_ref(dependency_fingerprint([event.stream, event.event_id]), "message")


@dataclass(frozen=True)
class TopicMaterial:
    text: str
    episodes: tuple[EpisodeKnowledge, ...]


class Maintenance:
    """Example single-writer host, not a production executor or storage adapter."""

    def __init__(self) -> None:
        self.index = DependencyIndex()
        self.sources: dict[DependencyKey, DependencyStamp] = {}
        self.specs: dict[DependencyKey, DerivationSpec] = {}
        self.values: dict[DependencyKey, Any] = {}
        self.receipts = {}
        self.previous_episodes: tuple[GroupIdentity, ...] = ()
        self.previous_topics: tuple[GroupIdentity, ...] = ()
        self.selection = None
        self.lexical = DeltaAggregate(LexicalStatisticsReducer(), scope=SCOPE)
        self.count = DeltaAggregate(CountReducer(), scope=SCOPE)
        self.centroid = DeltaAggregate(WeightedVectorReducer(), scope=SCOPE)
        self.membership = DeltaAggregate(MembershipReducer(), scope=SCOPE)
        self.projection = DependencyKey(object=object_ref("search", "projection"))
        self.events: tuple[KnowledgeEvent, ...] = ()
        self.denied: frozenset[str] = frozenset()

    def refresh(
        self,
        events: tuple[KnowledgeEvent, ...],
        *,
        generation: str,
        denied: frozenset[str] = frozenset(),
        model: str = "fixture:v1",
        extraction: str = "extract:v1",
        merge_topics: bool = False,
        fail_aspect: str = "",
    ) -> dict[str, Any]:
        if any(e.scope != SCOPE.tenant for e in events):
            raise ValueError("example operates on one authorized application partition")
        self.events, self.denied = events, denied
        candidates = tuple(
            DependencyStamp(
                dependency=DependencyKey(object=event_ref(e)),
                fingerprint=dependency_fingerprint(e),
            )
            for e in events
        )
        policy = DependencyStamp(
            dependency=DependencyKey(object=object_ref("access", "policy")),
            fingerprint=dependency_fingerprint(sorted(denied)),
        )
        selection_plan = plan_selection(
            SelectionSpec(
                object=object_ref("messages", "selection"),
                implementation="authorized:v1",
            ),
            candidates,
            dependencies=(policy,),
            previous=self.selection,
        )
        selected = tuple(e for e in events if e.event_id not in denied)
        selection = complete_selection(
            selection_plan,
            (
                DependencyKey(object=event_ref(e))
                for e in sorted(selected, key=lambda e: event_ref(e).key)
            ),
        )
        episodes = segment_conversations(selected)
        episode_matches = reconcile_groups(
            self.previous_episodes,
            (
                GroupIdentity(
                    object=object_ref(e.episode_id, "episode"),
                    members=tuple(event_ref(v) for v in e.events),
                )
                for e in episodes
            ),
            scope=SCOPE,
            namespace="episode",
            generation=generation,
        )
        original = {e.episode_id: e for e in episodes}
        stable = {
            a.group.object: replace(
                original[a.candidate_id], episode_id=a.group.object.object_id
            )
            for a in episode_matches.assignments
        }
        labels: dict[str, list[ObjectRef]] = defaultdict(list)
        for ref, episode in stable.items():
            labels[
                "all" if merge_topics else episode.events[0].topic or "general"
            ].append(ref)
        topic_matches = reconcile_groups(
            self.previous_topics,
            (
                GroupIdentity(object=object_ref(label, "topic"), members=tuple(members))
                for label, members in labels.items()
            ),
            scope=SCOPE,
            namespace="topic",
            generation=generation,
        )
        sources = {s.dependency: s for s in (*candidates, *selection_plan.sources)}
        specs = {selection_plan.derivation.output: selection_plan.derivation}
        builders: dict[DependencyKey, Callable[[Mapping[DependencyKey, Any]], Any]] = {}

        def add(output, inputs, implementation, builder):
            specs[output] = DerivationSpec(
                output=output, inputs=tuple(inputs), implementation=implementation
            )
            builders[output] = builder

        def membership(ref, members):
            stamp = DependencyStamp(
                dependency=DependencyKey(object=ref, aspect="membership"),
                fingerprint=dependency_fingerprint(members),
            )
            sources[stamp.dependency] = stamp
            return stamp.dependency

        for ref, episode in stable.items():
            inputs = tuple(DependencyKey(object=event_ref(e)) for e in episode.events)

            def extract(values, episode=episode):
                # A deterministic fixture callback, not a semantic quality claim.
                output = {
                    "title": "Conversation",
                    "topics": [episode.events[0].topic or "general"],
                    "questions": [],
                    "claims": [
                        {
                            "text": e.text,
                            "kind": "summary",
                            "status": "explicit",
                            "evidence": [
                                {
                                    "event_id": e.event_id,
                                    "revision": e.revision,
                                    "start": 0,
                                    "end": len(e.text),
                                    "quote": e.text,
                                }
                            ],
                        }
                        for e in episode.events
                    ],
                }
                return parse_episode_knowledge(episode, output, recipe=extraction)

            add(
                DependencyKey(object=ref),
                (membership(ref, inputs), *inputs),
                extraction,
                extract,
            )

        topics = tuple(a.group for a in topic_matches.assignments)
        vectors = []
        for group in topics:
            topic_key = DependencyKey(object=group.object)
            inputs = tuple(DependencyKey(object=m) for m in group.members)

            def summarize(values, inputs=inputs):
                artifacts = tuple(values[key] for key in inputs)
                for artifact in artifacts:
                    evidence_context(
                        artifact,
                        current_events=events,
                        allowed=lambda e: e.event_id not in denied,
                    )
                return TopicMaterial(
                    "\n".join(c.text for a in artifacts for c in a.claims), artifacts
                )

            add(
                topic_key,
                (membership(group.object, inputs), *inputs),
                "brief:v1",
                summarize,
            )
            text_key = DependencyKey(object=group.object, aspect="text")
            add(
                text_key,
                (topic_key,),
                "text:v1",
                lambda values, k=topic_key: values[k].text,
            )
            vector_key = DependencyKey(object=group.object, aspect="vector")
            add(
                vector_key,
                (text_key,),
                model,
                lambda values, k=text_key: [
                    len(values[k]),
                    values[k].lower().count("refund"),
                ],
            )
            vectors.append(vector_key)

        def project(values):
            result = []
            for group in topics:
                material = values[DependencyKey(object=group.object)]
                result.append(
                    RetrievalUnit(
                        ref=ArtifactRef(
                            artifact_id=group.object.object_id,
                            namespace="topic",
                            scope=SCOPE,
                            revision=dependency_fingerprint(material),
                        ),
                        text=material.text,
                    )
                )
            return tuple(result)

        add(
            self.projection,
            (
                selection.materialization.output.dependency,
                policy.dependency,
                *(DependencyKey(object=g.object) for g in topics),
                *vectors,
            ),
            "projection:v1",
            project,
        )
        self.index.apply(
            sources=tuple(s for k, s in sources.items() if self.sources.get(k) != s),
            removed_sources=self.sources.keys() - sources.keys(),
            derivations=tuple(s for k, s in specs.items() if self.specs.get(k) != s),
            removed_derivations=self.specs.keys() - specs.keys(),
            materializations=(selection.materialization,),
        )
        self.sources, self.specs = sources, specs
        self.receipts[selection.materialization.output.dependency] = (
            selection.materialization
        )
        self.values[selection.materialization.output.dependency] = selection.selected

        def drain(index, values, receipts, fail=""):
            rebuilt = []
            while index.plan().ready:
                for task in index.plan().ready:
                    if fail and task.output.aspect == fail:
                        raise RuntimeError("fixture build failure")
                    value = builders[task.output](values)
                    receipt = materialization_receipt(
                        specs[task.output],
                        task.inputs,
                        output_fingerprint=dependency_fingerprint(value),
                    )
                    # Production: atomically commit both, conditional on this input snapshot.
                    values[task.output], receipts[task.output] = value, receipt
                    index.apply(materializations=(receipt,))
                    rebuilt.append(task.output)
            assert all(u.action is UpdateAction.REUSE for u in index.plan().updates)
            return rebuilt

        rebuilt = drain(self.index, self.values, self.receipts, fail_aspect)
        clean = DependencyIndex(
            sources=sources.values(),
            derivations=specs.values(),
            materializations=(selection.materialization,),
        )
        clean_values = {selection.materialization.output.dependency: selection.selected}
        clean_receipts = {
            selection.materialization.output.dependency: selection.materialization
        }
        drain(clean, clean_values, clean_receipts)
        assert clean.plan() == replace(self.index.plan(), retired=())
        assert all(clean_receipts[k] == self.receipts[k] for k in specs)
        assert all(clean_values[k] == self.values[k] for k in specs)
        self.previous_episodes = tuple(a.group for a in episode_matches.assignments)
        self.previous_topics = topics
        self.selection = selection

        # Keyed aggregate replacement/removal preserves surviving contributions.
        lexical = {
            DependencyKey(object=g.object): dict(
                Counter(
                    self.values[DependencyKey(object=g.object)].text.lower().split()
                )
            )
            for g in topics
        }
        self.lexical.apply(
            lexical.items(), removed=self.lexical.contributions.keys() - lexical.keys()
        )
        self.count.apply(
            lexical.items(), removed=self.count.contributions.keys() - lexical.keys()
        )
        vector_values = {k: {"vector": self.values[k]} for k in vectors}
        self.centroid.apply(
            vector_values.items(),
            removed=self.centroid.contributions.keys() - vector_values.keys(),
        )
        projections: dict[DependencyKey, list[str]] = defaultdict(list)
        for group in topics:
            for member in group.members:
                for e in stable[member].events:
                    projections[DependencyKey(object=event_ref(e))].append(
                        group.object.object_id
                    )
        self.membership.apply(
            projections.items(),
            removed=self.membership.contributions.keys() - projections.keys(),
        )
        return {
            "incremental_equals_rebuild": True,
            "vectors_rebuilt": sum(k.aspect == "vector" for k in rebuilt),
            "topics": len(topics),
            "topic_transitions": [a.transitions for a in topic_matches.assignments],
            "retired_topics": len(topic_matches.retired),
        }

    def query(self, text: str):
        if self.projection not in self.index.plan(targets=(self.projection,)).reusable:
            raise ValueError("projection is unavailable")
        for group in self.previous_topics:
            for artifact in self.values[DependencyKey(object=group.object)].episodes:
                evidence_context(
                    artifact,
                    current_events=self.events,
                    allowed=lambda e: e.event_id not in self.denied,
                )
        units = self.values[self.projection]
        index = RevisionBM25Index({u.ref.to_revision_ref(): u.text for u in units})
        return tuple(
            hit
            for hit in index.search(
                text, limit=10, allowed_refs={u.ref.to_revision_ref() for u in units}
            )
            if hit.score > 0
        )


def messages() -> tuple[KnowledgeEvent, ...]:
    return (
        KnowledgeEvent(
            event_id="a",
            scope="acme",
            stream="support",
            revision="1",
            timestamp=1,
            author="A",
            text="Refunds close after 30 days.",
            topic="refunds",
        ),
        KnowledgeEvent(
            event_id="b",
            scope="acme",
            stream="support",
            revision="1",
            timestamp=2,
            author="B",
            text="Deploy on Tuesday.",
            topic="deployment",
        ),
    )


def run() -> dict[str, Any]:
    host = Maintenance()
    rows = messages()
    host.refresh(rows, generation="initial")
    result = host.refresh(
        (replace(rows[0], text="Refunds close after 14 days.", revision="2"), rows[1]),
        generation="edit",
    )
    assert result["vectors_rebuilt"] == 1
    assert host.query("refunds")
    return result


if __name__ == "__main__":
    print(run())
