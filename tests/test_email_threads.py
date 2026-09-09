from __future__ import annotations

import pytest

from mari_kit.conversation_knowledge import segment_conversations
from mari_kit.documents.email import (
    BulkSignal,
    EmailMessage,
    Fragment,
    FragmentKind,
)
from mari_kit.documents.email_threads import (
    EmailThread,
    LinkReason,
    ThreadLink,
    email_events,
    thread_emails,
)

DAY = 86400.0
ALICE, BOB, CAROL, DAVE = (
    "alice@example.test",
    "bob@example.test",
    "carol@example.test",
    "dave@example.test",
)


def paragraph(seed: str, words: int = 40) -> str:
    """Synthetic body text, comfortably over the 200 character match floor."""
    return f"Note {seed}. " + " ".join(f"token-{seed}-{i}" for i in range(words)) + "."


def key(subject: str) -> str:
    value = subject.strip().lower()
    while value.split(":", 1)[0] in {"re", "fw", "fwd"} and ":" in value:
        value = value.split(":", 1)[1].strip()
    return value or "(no subject)"


def message(
    identifier: str,
    *,
    timestamp: float,
    sender: str,
    to: tuple[str, ...] = (),
    subject: str = "",
    own: str = "",
    fragments: tuple[Fragment, ...] = (),
    raw: str | None = None,
    **extra,
) -> EmailMessage:
    quoted = "\n".join(f.text for f in fragments)
    return EmailMessage(
        message_id=identifier,
        timestamp=timestamp,
        sender=sender,
        to=to,
        subject=subject,
        subject_key=key(subject),
        raw_body=raw if raw is not None else (own + ("\n" + quoted if quoted else "")),
        own_text=own,
        fragments=fragments,
        source=f"mail://{identifier}",
        **extra,
    )


def quoted(
    text: str, *, sender: str = "", timestamp: float = 0.0, subject: str = ""
) -> Fragment:
    return Fragment(
        kind=FragmentKind.QUOTED,
        text=text,
        start=0,
        end=len(text),
        depth=1,
        sender=sender,
        timestamp=timestamp,
        subject=subject,
    )


def forwarded(
    text: str, *, sender: str, timestamp: float = 0.0, subject: str = ""
) -> Fragment:
    return Fragment(
        kind=FragmentKind.FORWARDED,
        text=text,
        start=0,
        end=len(text),
        sender=sender,
        timestamp=timestamp,
        subject=subject,
    )


def ids(thread: EmailThread) -> list[str]:
    return [m.message_id for m in thread.messages]


def reasons(thread: EmailThread) -> set[LinkReason]:
    return {link.reason for link in thread.links}


def test_quoted_fragments_link_reply_chain_without_headers():
    first, second = paragraph("plan"), paragraph("counter")
    chain = [
        message(
            "m1", timestamp=100, sender=ALICE, to=(BOB,), subject="Roadmap", own=first
        ),
        message(
            "m2",
            timestamp=200,
            sender=BOB,
            to=(ALICE,),
            subject="Something else",
            own=second,
            fragments=(quoted(first),),
        ),
        message(
            "m3",
            timestamp=300,
            sender=CAROL,
            to=(DAVE,),
            subject="Unrelated title",
            own="Looping in Dave.",
            fragments=(quoted(second),),
        ),
    ]
    threads = thread_emails(chain)
    assert len(threads) == 1
    assert ids(threads[0]) == ["m1", "m2", "m3"]
    assert reasons(threads[0]) == {LinkReason.QUOTED}
    assert {(link.child_id, link.parent_id) for link in threads[0].links} == {
        ("m2", "m1"),
        ("m3", "m2"),
    }
    assert threads[0].reconstructed == ()


def test_header_chain_links_by_in_reply_to_and_references():
    chain = [
        message(
            "m1", timestamp=10, sender=ALICE, to=(BOB,), subject="Budget", own="First."
        ),
        message(
            "m2",
            timestamp=20,
            sender=BOB,
            subject="Other",
            own="Second.",
            in_reply_to="m1",
        ),
        message(
            "m3",
            timestamp=30,
            sender=CAROL,
            subject="Third topic",
            own="Third.",
            references=("m1", "m2"),
        ),
    ]
    threads = thread_emails(chain)
    assert len(threads) == 1
    assert ids(threads[0]) == ["m1", "m2", "m3"]
    assert reasons(threads[0]) == {LinkReason.HEADER}
    assert threads[0].links == (
        ThreadLink(child_id="m2", parent_id="m1", reason=LinkReason.HEADER),
        ThreadLink(child_id="m3", parent_id="m1", reason=LinkReason.HEADER),
        ThreadLink(child_id="m3", parent_id="m2", reason=LinkReason.HEADER),
    )


def test_forward_of_forward_yields_one_thread_with_reconstructed_original():
    original = paragraph("original")
    relay = paragraph("relay")
    forward_one = message(
        "f1",
        timestamp=1000,
        sender=BOB,
        to=(CAROL,),
        subject="Fwd: Vendor terms",
        own=relay,
        fragments=(
            forwarded(original, sender=ALICE, timestamp=900, subject="Vendor terms"),
        ),
    )
    forward_two = message(
        "f2",
        timestamp=2000,
        sender=CAROL,
        to=(DAVE,),
        subject="Fwd: Fwd: Vendor terms",
        own="See the chain below.",
        fragments=(
            forwarded(relay, sender=BOB, timestamp=1000),
            forwarded(original, sender=ALICE, timestamp=900, subject="Vendor terms"),
        ),
    )
    threads = thread_emails([forward_two, forward_one])
    assert len(threads) == 1
    thread = threads[0]
    assert ids(thread) == ["f1", "f2"]
    assert len(thread.reconstructed) == 1
    recovered = thread.reconstructed[0]
    assert recovered.message_id.startswith("reconstructed:")
    assert recovered.sender == ALICE
    assert recovered.timestamp == 900
    assert recovered.subject == "Vendor terms"
    assert recovered.own_text == original
    assert recovered.source == "mail://f1"
    assert ("f2", "f1", LinkReason.QUOTED) in {
        (link.child_id, link.parent_id, link.reason) for link in thread.links
    }
    assert {
        link.child_id for link in thread.links if link.parent_id == recovered.message_id
    } == {
        "f1",
        "f2",
    }


def test_subject_collision_with_disjoint_participants_stays_two_threads():
    threads = thread_emails(
        [
            message(
                "a1", timestamp=0, sender=ALICE, to=(BOB,), subject="Lunch", own="Noon?"
            ),
            message(
                "a2",
                timestamp=60,
                sender=BOB,
                to=(ALICE,),
                subject="Re: Lunch",
                own="Yes.",
            ),
            message(
                "b1",
                timestamp=120,
                sender=CAROL,
                to=(DAVE,),
                subject="Lunch",
                own="One?",
            ),
            message(
                "b2",
                timestamp=180,
                sender=DAVE,
                to=(CAROL,),
                subject="RE: lunch",
                own="Sure.",
            ),
        ]
    )
    assert [ids(t) for t in threads] == [["a1", "a2"], ["b1", "b2"]]
    assert all(reasons(t) == {LinkReason.SUBJECT} for t in threads)


def test_same_subject_with_shared_participant_inside_gap_merges():
    threads = thread_emails(
        [
            message(
                "m1",
                timestamp=0,
                sender=ALICE,
                to=(BOB,),
                subject="Offsite",
                own="Dates?",
            ),
            message(
                "m2",
                timestamp=3 * DAY,
                sender=BOB,
                to=(ALICE, CAROL),
                subject="Re: Offsite",
                own="June.",
            ),
        ]
    )
    assert len(threads) == 1
    assert threads[0].links == (
        ThreadLink(child_id="m2", parent_id="m1", reason=LinkReason.SUBJECT),
    )


def test_same_subject_with_shared_participant_outside_gap_stays_separate():
    pair = [
        message(
            "m1", timestamp=0, sender=ALICE, to=(BOB,), subject="Offsite", own="Dates?"
        ),
        message(
            "m2",
            timestamp=20 * DAY,
            sender=BOB,
            to=(ALICE,),
            subject="Re: Offsite",
            own="June.",
        ),
    ]
    assert len(thread_emails(pair)) == 2
    assert len(thread_emails(pair, gap_seconds=30 * DAY)) == 1


def test_subject_gap_measures_from_latest_member_of_the_group():
    chain = [
        message(
            "m1", timestamp=0, sender=ALICE, to=(BOB,), subject="Audit", own="Start."
        ),
        message(
            "m2",
            timestamp=10 * DAY,
            sender=BOB,
            to=(ALICE,),
            subject="Re: Audit",
            own="Mid.",
        ),
        message(
            "m3",
            timestamp=20 * DAY,
            sender=ALICE,
            to=(BOB,),
            subject="Re: Audit",
            own="End.",
        ),
    ]
    threads = thread_emails(chain)
    assert len(threads) == 1
    assert [(x.child_id, x.parent_id) for x in threads[0].links] == [
        ("m2", "m1"),
        ("m3", "m2"),
    ]


def test_same_sender_alone_never_counts_as_shared_participant():
    threads = thread_emails(
        [
            message(
                "m1",
                timestamp=0,
                sender=ALICE,
                to=(BOB,),
                subject="Invoice",
                own="Bob, see attached.",
            ),
            message(
                "m2",
                timestamp=60,
                sender=ALICE,
                to=(CAROL,),
                subject="Invoice",
                own="Carol, see attached.",
            ),
        ]
    )
    assert len(threads) == 2


def test_no_subject_key_never_links_by_subject():
    threads = thread_emails(
        [
            message(
                "m1", timestamp=0, sender=ALICE, to=(BOB,), subject="", own="Ping."
            ),
            message(
                "m2", timestamp=60, sender=BOB, to=(ALICE,), subject="", own="Pong."
            ),
        ]
    )
    assert len(threads) == 2
    assert all(t.links == () for t in threads)


def test_message_id_duplicates_are_dropped_and_recorded():
    original = message(
        "m1", timestamp=0, sender=ALICE, to=(BOB,), subject="Dup", own="One."
    )
    repeat = message(
        "m1", timestamp=5, sender=ALICE, to=(BOB,), subject="Dup", own="One again."
    )
    reply = message(
        "m2", timestamp=60, sender=BOB, to=(ALICE,), subject="Re: Dup", own="Two."
    )
    threads = thread_emails([original, repeat, reply])
    assert len(threads) == 1
    assert threads[0].messages[0].own_text == "One."
    assert threads[0].duplicates == ("m1",)


def test_fingerprint_duplicates_are_dropped_and_recorded():
    bulk = BulkSignal(body_digest="abc123")
    first = message(
        "m1",
        timestamp=0,
        sender=ALICE,
        to=(BOB,),
        subject="Blast",
        own="Body.",
        bulk=bulk,
    )
    second = message(
        "m2",
        timestamp=30,
        sender=ALICE,
        to=(CAROL,),
        subject="Blast",
        own="Body.",
        bulk=bulk,
    )
    other = message(
        "m3",
        timestamp=40,
        sender=ALICE,
        to=(DAVE,),
        subject="Blast",
        own="Different.",
        bulk=BulkSignal(body_digest="zzz"),
    )
    threads = thread_emails([first, second, other])
    assert [ids(t) for t in threads] == [["m1"], ["m3"]]
    assert threads[0].duplicates == ("m2",)
    assert threads[1].duplicates == ()


def test_empty_body_digest_never_fingerprints():
    pair = [
        message("m1", timestamp=0, sender=ALICE, to=(BOB,), subject="X", own="Same."),
        message("m2", timestamp=1, sender=ALICE, to=(BOB,), subject="X", own="Same."),
    ]
    assert len(thread_emails(pair)) == 1
    assert thread_emails(pair)[0].duplicates == ()


def test_reconstruction_dedups_the_same_original_quoted_by_two_replies():
    lost = paragraph("lost")
    replies = [
        message(
            "r1",
            timestamp=500,
            sender=BOB,
            to=(ALICE,),
            subject="Re: Kickoff",
            own="Works for me.",
            fragments=(quoted(lost, sender=ALICE, timestamp=400),),
        ),
        message(
            "r2",
            timestamp=600,
            sender=CAROL,
            to=(ALICE,),
            subject="Re: Kickoff",
            own="Same here.",
            fragments=(quoted(lost, sender=ALICE, timestamp=400),),
        ),
    ]
    threads = thread_emails(replies)
    assert len(threads) == 1
    assert ids(threads[0]) == ["r1", "r2"]
    assert len(threads[0].reconstructed) == 1
    recovered = threads[0].reconstructed[0].message_id
    quotes = [x for x in threads[0].links if x.reason is LinkReason.QUOTED]
    assert [(x.child_id, x.parent_id) for x in quotes] == [
        ("r1", recovered),
        ("r2", recovered),
    ]


def test_undated_quotes_still_share_one_reconstructed_message():
    lost = paragraph("undated")
    replies = [
        message(
            "r1",
            timestamp=500,
            sender=BOB,
            to=(ALICE,),
            subject="Re: Q",
            own="Yes.",
            fragments=(quoted(lost, sender=ALICE),),
        ),
        message(
            "r2",
            timestamp=900,
            sender=CAROL,
            to=(ALICE,),
            subject="Re: Q",
            own="No.",
            fragments=(quoted(lost, sender=ALICE),),
        ),
    ]
    threads = thread_emails(replies)
    assert len(threads) == 1
    assert len(threads[0].reconstructed) == 1
    assert threads[0].reconstructed[0].timestamp == 499


def test_reconstruct_false_recovers_nothing():
    reply = message(
        "r1",
        timestamp=500,
        sender=BOB,
        to=(ALICE,),
        subject="Re: Kickoff",
        own="Works for me.",
        fragments=(quoted(paragraph("gone"), sender=ALICE, timestamp=400),),
    )
    threads = thread_emails([reply], reconstruct=False)
    assert threads[0].reconstructed == ()
    assert threads[0].links == ()


def test_fragments_without_sender_or_text_are_not_reconstructed():
    reply = message(
        "r1",
        timestamp=500,
        sender=BOB,
        to=(ALICE,),
        subject="Re: Kickoff",
        own="Works for me.",
        fragments=(quoted(paragraph("anon")), quoted("   ", sender=ALICE)),
    )
    assert thread_emails([reply])[0].reconstructed == ()


def test_thread_id_is_stable_under_input_reordering():
    first = paragraph("stable")
    chain = [
        message(
            "m1", timestamp=0, sender=ALICE, to=(BOB,), subject="Stable", own=first
        ),
        message(
            "m2",
            timestamp=60,
            sender=BOB,
            to=(ALICE,),
            subject="Re: Stable",
            own="Ack.",
            fragments=(quoted(first),),
        ),
        message(
            "m3",
            timestamp=120,
            sender=CAROL,
            to=(BOB,),
            subject="Re: Stable",
            own="Also ack.",
            in_reply_to="m2",
        ),
        message(
            "z1", timestamp=5, sender=DAVE, to=(CAROL,), subject="Elsewhere", own="Hi."
        ),
    ]
    forward = thread_emails(chain)
    backward = thread_emails(reversed(chain))
    assert [t.thread_id for t in forward] == [t.thread_id for t in backward]
    assert [ids(t) for t in forward] == [ids(t) for t in backward]
    assert forward[0].thread_id.startswith("thread:")
    assert len(forward[0].thread_id) == len("thread:") + 24
    assert forward[0].thread_id != forward[1].thread_id


def test_subset_links_inline_copies_without_fragments():
    first = paragraph("inline")
    original = message(
        "m1", timestamp=0, sender=ALICE, to=(BOB,), subject="Inline", own=first
    )
    reply = message(
        "m2",
        timestamp=60,
        sender=BOB,
        to=(CAROL,),
        subject="Totally different",
        own="Replying inline below.",
        raw="Replying inline below.\n\n" + first.upper() + "\n-- Bob",
    )
    threads = thread_emails([original, reply])
    assert len(threads) == 1
    assert threads[0].links == (
        ThreadLink(child_id="m2", parent_id="m1", reason=LinkReason.SUBSET),
    )


def test_short_matches_respect_minimum_match_characters():
    short = "Short text that is well under the floor."
    pair = [
        message("m1", timestamp=0, sender=ALICE, to=(BOB,), subject="A", own=short),
        message(
            "m2",
            timestamp=60,
            sender=CAROL,
            to=(DAVE,),
            subject="B",
            own="Ok.",
            fragments=(quoted(short),),
        ),
    ]
    assert len(thread_emails(pair)) == 2
    assert len(thread_emails(pair, minimum_match_characters=20)) == 1


def test_quoted_match_prefers_candidate_with_matching_sender_and_time():
    shared = paragraph("template")
    candidates = [
        message(
            "alice-copy",
            timestamp=1000,
            sender=ALICE,
            to=(DAVE,),
            subject="Template",
            own=shared,
        ),
        message(
            "carol-copy",
            timestamp=5000,
            sender=CAROL,
            to=(DAVE,),
            subject="Template",
            own=shared,
        ),
    ]
    reply = message(
        "reply",
        timestamp=6000,
        sender=DAVE,
        to=(CAROL,),
        subject="Re: Template",
        own="Thanks Carol.",
        fragments=(quoted(shared, sender=f"Carol <{CAROL}>", timestamp=5030),),
    )
    threads = thread_emails([*candidates, reply])
    links = [x for t in threads for x in t.links if x.reason is LinkReason.QUOTED]
    assert links == [
        ThreadLink(child_id="reply", parent_id="carol-copy", reason=LinkReason.QUOTED)
    ]


def test_thread_subject_and_participants():
    threads = thread_emails(
        [
            message(
                "m2",
                timestamp=60,
                sender=BOB,
                to=(ALICE,),
                cc=(CAROL,),
                subject="Re: Kick",
                own="Two.",
                in_reply_to="m1",
            ),
            message(
                "m1", timestamp=0, sender=ALICE, to=(BOB,), subject="Kick", own="One."
            ),
        ]
    )
    assert threads[0].subject == "Kick"
    assert threads[0].participants == frozenset({ALICE, BOB, CAROL})


def test_invalid_arguments_raise():
    with pytest.raises(ValueError):
        thread_emails([], gap_seconds=-1)
    with pytest.raises(ValueError):
        thread_emails([], minimum_match_characters=0)
    with pytest.raises(ValueError):
        ThreadLink(child_id="x", parent_id="x", reason=LinkReason.HEADER)
    assert thread_emails([]) == ()


def two_threads() -> tuple[EmailThread, ...]:
    first = paragraph("events")
    return thread_emails(
        [
            message(
                "m1", timestamp=0, sender=ALICE, to=(BOB,), subject="Events", own=first
            ),
            message(
                "m2",
                timestamp=60,
                sender=BOB,
                to=(ALICE,),
                subject="Re: Events",
                own="Reply.",
                fragments=(quoted(first),),
            ),
            message(
                "n1",
                timestamp=30,
                sender=CAROL,
                to=(DAVE,),
                subject="Other",
                own="Hello Dave.",
            ),
        ]
    )


def test_email_events_feed_segment_conversations_one_episode_per_thread():
    threads = two_threads()
    events = [e for t in threads for e in email_events(t, scope="company")]
    episodes = segment_conversations(events, gap_seconds=1)
    assert len(episodes) == len(threads) == 2
    assert {e.events[0].thread_id for e in episodes} == {t.thread_id for t in threads}
    assert [[x.event_id for x in e.events] for e in episodes] == [["m1", "m2"], ["n1"]]


def test_email_events_text_format_and_metadata():
    thread = two_threads()[0]
    events = email_events(thread, scope="company")
    first = events[0]
    assert first.event_id == "m1"
    assert first.text == f"Subject: Events\nTo: {BOB}\n\n{paragraph('events')}"
    assert first.author == ALICE
    assert first.role == "message"
    assert first.stream == thread.thread_id
    assert first.thread_id == thread.thread_id
    assert first.url == "mail://m1"
    assert first.timestamp == 0
    assert len(first.revision) == 12
    assert events[1].revision != first.revision
    custom = email_events(thread, scope="company", stream="mailbox")
    assert {e.stream for e in custom} == {"mailbox"}


def test_email_events_omit_to_line_and_default_author():
    thread = thread_emails(
        [message("m1", timestamp=0, sender="", subject="Solo", own="Alone.")]
    )[0]
    event = email_events(thread, scope="company")[0]
    assert event.text == "Subject: Solo\n\nAlone."
    assert event.author == "unknown"


def test_email_events_skip_messages_with_empty_own_text():
    thread = thread_emails(
        [
            message(
                "m1",
                timestamp=0,
                sender=ALICE,
                to=(BOB,),
                subject="Blank",
                own="Real words.",
            ),
            message(
                "m2",
                timestamp=60,
                sender=BOB,
                to=(ALICE,),
                subject="Re: Blank",
                own="  \n ",
                in_reply_to="m1",
            ),
        ]
    )[0]
    assert [e.event_id for e in email_events(thread, scope="company")] == ["m1"]


def test_email_events_url_for_override():
    thread = two_threads()[0]
    events = email_events(
        thread, scope="company", url_for=lambda m: f"https://mail.test/{m.message_id}"
    )
    assert [e.url for e in events] == ["https://mail.test/m1", "https://mail.test/m2"]


def test_email_events_reconstructed_role_and_exclusion():
    lost = paragraph("lost")
    thread = thread_emails(
        [
            message(
                "r1",
                timestamp=500,
                sender=BOB,
                to=(ALICE,),
                subject="Re: Kickoff",
                own="Works for me.",
                fragments=(quoted(lost, sender=ALICE, timestamp=400),),
            )
        ]
    )[0]
    included = email_events(thread, scope="company")
    assert [e.role for e in included] == ["quoted", "message"]
    assert included[0].author == ALICE
    assert included[0].timestamp == 400
    assert included[0].url == "mail://r1"
    excluded = email_events(thread, scope="company", include_reconstructed=False)
    assert [e.event_id for e in excluded] == ["r1"]


def test_repeated_fingerprint_duplicate_does_not_crash():
    bulk = BulkSignal(body_digest="777")
    a = message(
        "a",
        timestamp=0,
        sender=ALICE,
        to=(BOB,),
        subject="Blast",
        own="Body.",
        bulk=bulk,
    )
    b = message(
        "b",
        timestamp=20,
        sender=ALICE,
        to=(BOB,),
        subject="Blast",
        own="Body.",
        bulk=bulk,
    )
    threads = thread_emails([a, b, b])
    assert len(threads) == 1
    assert ids(threads[0]) == ["a"]
    assert threads[0].duplicates == ("b",)


def test_header_reference_to_fingerprint_duplicate_survives_in_any_order():
    bulk = BulkSignal(body_digest="777")
    a = message(
        "a",
        timestamp=0,
        sender=ALICE,
        to=(BOB,),
        subject="Blast",
        own="Body.",
        bulk=bulk,
    )
    b = message(
        "b",
        timestamp=20,
        sender=ALICE,
        to=(CAROL,),
        subject="Blast",
        own="Body.",
        bulk=bulk,
    )
    r = message(
        "r",
        timestamp=60,
        sender=DAVE,
        subject="Unrelated",
        own="Reply.",
        in_reply_to="b",
    )
    for batch in ([a, b, r], [b, a, r]):
        threads = thread_emails(batch)
        assert len(threads) == 1
        assert len(threads[0].messages) == 2
        assert threads[0].duplicates in (("b",), ("a",))
        assert reasons(threads[0]) == {LinkReason.HEADER}


def test_shared_prefix_with_different_endings_never_matches():
    prefix = "x" * 200
    original = message(
        "m1",
        timestamp=0,
        sender=ALICE,
        to=(BOB,),
        subject="Request",
        own=prefix + " approved",
    )
    other = message(
        "m2",
        timestamp=60,
        sender=CAROL,
        to=(DAVE,),
        subject="Other request",
        own="Noted.",
        fragments=(quoted(prefix + " denied", sender=DAVE, timestamp=30),),
    )
    threads = thread_emails([original, other])
    assert [ids(t) for t in threads] == [["m1"], ["m2"]]
    assert threads[0].links == ()
    assert len(threads[1].reconstructed) == 1
    assert threads[1].reconstructed[0].own_text == prefix + " denied"


def test_reconstructed_ids_hash_the_full_quoted_text():
    prefix = paragraph("same-start")
    replies = [
        message(
            "r1",
            timestamp=500,
            sender=BOB,
            to=(ALICE,),
            subject="Re: Q",
            own="Yes.",
            fragments=(quoted(prefix + " ending one", sender=ALICE, timestamp=400),),
        ),
        message(
            "r2",
            timestamp=600,
            sender=BOB,
            to=(ALICE,),
            subject="Re: Q",
            own="No.",
            fragments=(quoted(prefix + " ending two", sender=ALICE, timestamp=400),),
        ),
    ]
    threads = thread_emails(replies)
    recovered = [m for t in threads for m in t.reconstructed]
    assert len({m.message_id for m in recovered}) == 2


def test_hundreds_of_same_prefix_messages_stay_bounded_and_correct():
    prefix = paragraph("shared", words=50)
    batch: list[EmailMessage] = []
    for i in range(300):
        sender, recipient = f"s{i}@example.test", f"t{i}@example.test"
        own = f"{prefix} closing line {i}."
        batch.append(
            message(
                f"o{i}",
                timestamp=i * 1000.0,
                sender=sender,
                to=(recipient,),
                subject="Batch",
                own=own,
            )
        )
        batch.append(
            message(
                f"r{i}",
                timestamp=i * 1000.0 + 1,
                sender=recipient,
                to=(sender,),
                subject="Re: Batch",
                own=f"Reply {i}.",
                fragments=(quoted(own, sender=sender, timestamp=i * 1000.0),),
            )
        )
    threads = thread_emails(batch)
    assert len(threads) == 300
    assert [ids(t) for t in threads] == [[f"o{i}", f"r{i}"] for i in range(300)]
    assert all(t.reconstructed == () for t in threads)
    assert all(LinkReason.QUOTED in reasons(t) for t in threads)
