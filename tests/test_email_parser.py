from mari_kit.documents.email import (
    FragmentKind,
    classify_lines,
    normalize_address,
    parse_email,
    split_fragments,
    subject_key,
)

OUTLOOK_REPLY = "\n".join(
    [
        "Sounds good, I will send the file.",
        "",
        "Pat Example",
        "Risk Analyst",
        "555-010-0100",
        "",
        "-----Original Message-----",
        "From: Lee, Sam [mailto:sam.lee@example.com]",
        "Sent: Friday, August 10, 2001 10:53 AM",
        "To: Example, Pat; Chen, Alex",
        "Cc: Kim, Jordan",
        "Subject: RE: Budget review",
        "",
        "Can you send the file today?",
        "",
    ]
)

LOTUS_DOUBLE_FORWARD = "\n".join(
    [
        "Please handle.",
        "",
        "---------------------- Forwarded by Pat Example/HOU/EES on 08/10/2001 11:03 AM ---------------------------",
        "",
        "From:\tAlex Chen/HOU/EES on 08/10/2001 10:55 AM",
        "To:\tPat Example/HOU/EES@EES, Sam Lee/HOU/ECT@ECT",
        "cc:\t",
        "Subject:\tRe: Budget review",
        "",
        "Forwarding the thread below.",
        "-------------- Forwarded by Alex Chen/HOU/EES on 08/10/2001 03:41 PM ---------------------------",
        "",
        "Sam Lee/ENRON@enronXgate on 08/10/2001 10:53 AM",
        "To:\tAlex Chen/HOU/EES@EES",
        "cc:\t",
        "Subject:\tBudget review",
        "",
        "Numbers attached.",
        "",
    ]
)

QUOTED_REPLY = "\n".join(
    [
        "Agreed, see inline.",
        "",
        "On Fri, Aug 10, 2001 at 10:53 AM, Sam Lee <sam.lee@example.com> wrote:",
        "> Can we move the meeting?",
        "> It conflicts with the audit.",
        ">> earlier note",
        "",
        "Yes we can.",
        "",
        "-- ",
        "Pat",
        "",
    ]
)


WRAPPED_FORWARD = "\n".join(
    [
        "Please see below.",
        "",
        "---------------------- Forwarded by Mira Okafor/DUB/AUDIT/Acme on",
        "07/11/2001 14:37 ---------------------------",
        "",
        "Nadia Example",
        "07/11/2001 09:12",
        "To:\tMira Okafor/DUB/AUDIT/Acme@Acme-EU",
        "cc:\t",
        "Subject:\tDraft numbers",
        "",
        "Attached is the draft.",
        "",
    ]
)

NOTES_REPLY = "\n".join(
    [
        "Thanks, will do.",
        "",
        "David W Example",
        "08/10/2001 11:06 AM",
        "To:\tDana Leff/HOU/OPS@OPS",
        "cc:\tRick Example/Acme@AcmeGate, Janet Example/HOU/OPS@OPS",
        "Subject:\tRemote Offices- Suggestions",
        "",
        "body text...",
        "",
    ]
)

INDENTED_OUTLOOK = "\n".join(
    [
        "Yes.",
        "",
        "\t-----Original Message----- ",
        "\tFrom: Example, Karl K SE-SE ",
        "\tSent: Thu 11/22/2001 10:25 AM ",
        "\tTo: Example, Rick ",
        "\tCc: ",
        "\tSubject: FW: Status ??",
        "\t",
        "\tOlder text.",
        "",
    ]
)


def raw_of(body, fragment):
    return body[fragment.start : fragment.end]


# subject_key


def test_subject_key_strips_nested_prefixes_and_tags():
    assert subject_key("RE: Fwd: [ext] re: Budget  review") == "budget review"
    assert subject_key("AW: [list] [x] Hallo") == "hallo"
    assert subject_key("TR: SV: WG: FW: plan") == "plan"
    assert subject_key("Re[2]: plan") == "plan"
    assert subject_key("Reply: plan") == "reply: plan"


def test_subject_key_is_idempotent_and_handles_empty():
    for subject in ("Re: Re: [tag] x", "", "Re:", "   ", "(no subject)"):
        key = subject_key(subject)
        assert subject_key(key) == key
    assert subject_key("Re:") == "(no subject)"
    assert subject_key("") == "(no subject)"


# normalize_address


def test_normalize_address_display_name_forms():
    assert (
        normalize_address('"Lee, Sam" <Sam.Lee@Example.com>') == "sam.lee@example.com"
    )
    assert (
        normalize_address("Sam Lee [mailto:Sam.Lee@example.com]")
        == "sam.lee@example.com"
    )
    assert normalize_address("  SAM.LEE@EXAMPLE.COM ") == "sam.lee@example.com"


def test_normalize_address_lotus_notes_forms_never_empty():
    assert normalize_address("Sam  Lee/HOU/ECT@ECT") == "sam lee/hou/ect@ect"
    assert (
        normalize_address("Lee, Sam </O=CORP/OU=NA/CN=RECIPIENTS/CN=Slee>")
        == "/o=corp/ou=na/cn=recipients/cn=slee"
    )
    assert normalize_address("Sam Lee") == "sam lee"


def test_normalize_address_empty_and_placeholder():
    assert normalize_address("") == ""
    assert normalize_address("   ") == ""
    assert normalize_address("<>") == ""


# classify_lines


def test_classify_outlook_original_message():
    body = "hi\n\n--Original Message--\nFrom: a@example.com\nSent:\tMon\nTo: b\ncc: c\nSubject: x\nDate: y\n\nbody"
    assert classify_lines(body) == "tesh" + "hhhhh" + "et"
    assert classify_lines("-----Original Appointment-----") == "s"
    assert classify_lines("--- original message ---") == "s"


def test_classify_lotus_forward_and_reply_header():
    assert classify_lines(LOTUS_DOUBLE_FORWARD) == "tesehhhhetsehhhhete"
    assert (
        classify_lines("From:\tSam Lee/ENRON@enronXgate on 08/10/2001 10:53 AM") == "h"
    )
    assert classify_lines("Sam Lee/ENRON@enronXgate on 08/10/2001 10:53 AM") == "h"
    assert classify_lines("We met Sam on the 10th.") == "t"


def test_classify_attribution_variants():
    assert classify_lines("On Fri, Aug 10, 2001, Sam Lee wrote:") == "s"
    assert classify_lines("Sam Lee <sam@example.com> wrote:") == "s"
    assert classify_lines("Sam Lee wrote:") == "s"
    assert classify_lines("Am 10.08.2001 um 10:53 schrieb Sam Lee:") == "s"
    assert classify_lines("Le 10 août 2001 à 10:53, Sam Lee a écrit :") == "s"
    assert classify_lines("El 10 ago 2001, Sam Lee escribió:") == "s"
    wrapped = (
        "On Fri, Aug 10, 2001 at 10:53 AM, Sam Lee\n<sam@example.com> wrote:\n> hi"
    )
    assert classify_lines(wrapped) == "ssq"
    assert classify_lines("On Friday we ship.\nThanks.") == "tt"


def test_classify_generic_forward_and_signature_markers():
    assert classify_lines("---------- Forwarded message ----------") == "s"
    assert classify_lines("Begin forwarded message:") == "s"
    assert classify_lines("-- \nPat") == "gt"
    assert classify_lines("--") == "g"
    assert classify_lines("Sent from my iPhone") == "g"
    assert classify_lines("  > quoted\n\n \t\nplain") == "qeet"


# split_fragments


def test_split_outlook_reply_offsets_and_headers():
    fragments = split_fragments(OUTLOOK_REPLY)
    kinds = [f.kind for f in fragments]
    assert kinds == [FragmentKind.OWN, FragmentKind.SIGNATURE, FragmentKind.QUOTED]
    own, signature, quoted = fragments
    assert own.text == "Sounds good, I will send the file."
    assert own.start == 0 and own.depth == 0
    assert signature.text == "Pat Example\nRisk Analyst\n555-010-0100"
    assert raw_of(OUTLOOK_REPLY, signature).startswith("Pat Example")
    assert quoted.start == OUTLOOK_REPLY.index("-----Original")
    assert quoted.end == len(OUTLOOK_REPLY)
    assert quoted.depth == 1
    assert quoted.sender == "sam.lee@example.com"
    assert quoted.timestamp == 997440780.0
    assert quoted.subject == "RE: Budget review"
    assert quoted.recipients == ("example, pat", "chen, alex", "kim, jordan")
    assert quoted.text == "Can you send the file today?"


def test_split_lotus_double_forward_nested_depths():
    fragments = split_fragments(LOTUS_DOUBLE_FORWARD)
    assert [f.kind for f in fragments] == [
        FragmentKind.OWN,
        FragmentKind.FORWARDED,
        FragmentKind.FORWARDED,
    ]
    own, first, second = fragments
    assert own.text == "Please handle."
    assert (first.depth, second.depth) == (1, 2)
    assert first.start == LOTUS_DOUBLE_FORWARD.index("---------------------- Forwarded")
    inner = LOTUS_DOUBLE_FORWARD.index("\n-------------- Forwarded") + 1
    assert first.end == second.start == inner
    assert second.end == len(LOTUS_DOUBLE_FORWARD)
    assert first.sender == "alex chen/hou/ees"
    assert first.timestamp == 997440900.0
    assert first.subject == "Re: Budget review"
    assert first.recipients == ("pat example/hou/ees@ees", "sam lee/hou/ect@ect")
    assert first.text == "Forwarding the thread below."
    assert second.sender == "sam lee/enron@enronxgate"
    assert second.timestamp == 997440780.0
    assert second.subject == "Budget review"
    assert second.recipients == ("alex chen/hou/ees@ees",)
    assert second.text == "Numbers attached."


def test_split_quoted_reply_keeps_own_text_around_the_quote():
    fragments = split_fragments(QUOTED_REPLY)
    assert [(f.kind, f.depth) for f in fragments] == [
        (FragmentKind.OWN, 0),
        (FragmentKind.QUOTED, 1),
        (FragmentKind.QUOTED, 2),
        (FragmentKind.OWN, 0),
        (FragmentKind.SIGNATURE, 0),
    ]
    top, quoted, nested, bottom, signature = fragments
    assert top.text == "Agreed, see inline."
    assert quoted.start == QUOTED_REPLY.index("On Fri")
    assert quoted.sender == "sam.lee@example.com"
    assert quoted.text == "Can we move the meeting?\nIt conflicts with the audit."
    assert raw_of(QUOTED_REPLY, nested) == ">> earlier note\n"
    assert nested.text == "earlier note"
    assert bottom.text == "Yes we can."
    assert raw_of(QUOTED_REPLY, signature) == "-- \nPat\n"
    assert signature.text == "Pat"


def test_split_wrapped_attribution_owns_the_quote_run():
    body = "hi\n\nOn Fri, Aug 10, 2001 at 10:53 AM, Sam Lee\n<sam@example.com> wrote:\n> yo\n"
    fragments = split_fragments(body)
    assert [f.kind for f in fragments] == [FragmentKind.OWN, FragmentKind.QUOTED]
    assert fragments[1].sender == "sam@example.com"
    assert fragments[1].text == "yo"
    assert fragments[1].end == len(body)


def test_split_signature_marker_line():
    body = "Thanks\n\nSent from my iPhone"
    own, signature = split_fragments(body)
    assert (own.kind, own.text) == (FragmentKind.OWN, "Thanks")
    assert (signature.kind, signature.text) == (
        FragmentKind.SIGNATURE,
        "Sent from my iPhone",
    )
    assert raw_of(body, signature) == "Sent from my iPhone"


def test_split_trailing_name_block_is_a_signature():
    body = "Please see the attached file.\n\nPat Example\nRisk Analyst\n"
    own, signature = split_fragments(body)
    assert own.text == "Please see the attached file."
    assert signature.kind is FragmentKind.SIGNATURE
    assert signature.text == "Pat Example\nRisk Analyst"
    assert own.end == signature.start
    assert signature.end == len(body)


def test_split_phone_number_in_prose_is_not_a_signature():
    body = "Call this number:\n\nThe service desk is 555-010-0100.\n"
    fragments = split_fragments(body)
    assert [f.kind for f in fragments] == [FragmentKind.OWN]
    assert fragments[0].text == "Call this number:\n\nThe service desk is 555-010-0100."
    body = "See attached.\n\nRegards,\nJane Doe\nDirector\n555-010-0100\n"
    own, signature = split_fragments(body)
    assert own.text == "See attached."
    assert signature.kind is FragmentKind.SIGNATURE
    assert signature.text == "Regards,\nJane Doe\nDirector\n555-010-0100"


def test_split_attribution_with_blank_line_before_quote_run():
    body = "Reply\n\nOn Monday, a@x.test wrote:\n\n> Earlier question\n\nMy inline answer.\n"
    fragments = split_fragments(body)
    assert [(f.kind, f.text) for f in fragments] == [
        (FragmentKind.OWN, "Reply"),
        (FragmentKind.QUOTED, "Earlier question"),
        (FragmentKind.OWN, "My inline answer."),
    ]
    assert fragments[1].sender == "a@x.test"
    assert fragments[1].start == body.index("On Monday")
    assert fragments[1].end == fragments[2].start
    assert fragments[2].end == len(body)


def test_split_sent_line_meridiem_and_offset():
    head = "hi\n\n-----Original Message-----\nFrom: a@example.com\nSent: "
    assert (
        split_fragments(head + "Friday, August 10, 2001 10:53 PM\n\nold\n")[1].timestamp
        == 997483980.0
    )
    assert (
        split_fragments(head + "08/10/2001 10:53 AM -0500\n\nold\n")[1].timestamp
        == 997458780.0
    )
    # A bare zone token is ignored, so the time is read as UTC.
    assert (
        split_fragments(head + "08/21/2001 01:48 PM CDT\n\nold\n")[1].timestamp
        == 998401680.0
    )


def test_split_is_conservative_about_signatures():
    body = "Please bring:\n\napples\noranges\nbananas\n"
    fragments = split_fragments(body)
    assert [f.kind for f in fragments] == [FragmentKind.OWN]
    assert fragments[0].text == "Please bring:\n\napples\noranges\nbananas"
    body = "Pat Example\nRisk Analyst\n"
    assert [f.kind for f in split_fragments(body)] == [FragmentKind.OWN]


def test_split_plain_message_is_one_own_fragment():
    body = "Just a plain note.\nSecond line.\n"
    fragments = split_fragments(body)
    assert len(fragments) == 1
    fragment = fragments[0]
    assert fragment.kind is FragmentKind.OWN
    assert (fragment.start, fragment.end, fragment.depth) == (0, len(body), 0)
    assert fragment.text == "Just a plain note.\nSecond line."
    assert split_fragments("") == ()
    assert split_fragments("\n\n  \n") == ()


def test_classify_wrapped_forward_marker_is_one_separator():
    assert classify_lines(WRAPPED_FORWARD) == "tessehhhhhete"
    wrapped = (
        "----- Forwarded by Jo Example/Hou-MidOffice/Trading/PEC on\n"
        "10/31/2001 09:51 AM -----"
    )
    assert classify_lines(wrapped) == "ss"
    assert (
        classify_lines(
            "----- Forwarded by Jo Example/HOU/OPS on 07/11/2001 14:37 -----"
        )
        == "s"
    )
    # Any dashed "Forwarded by" line is a separator, but it only absorbs a wrapped
    # remainder; a bare date line on its own is text.
    assert classify_lines("----- Forwarded by Jo Example/HOU/OPS on\nthanks") == "st"
    assert classify_lines("07/11/2001 14:37 -----") == "t"


def test_classify_forward_marker_absorbs_wrapped_tail_variants():
    dashes_only = (
        "---------------------- Forwarded by Steve W Example/LON/OPS on 13/01/2000 11:22 \n"
        "---------------------------"
    )
    meridiem_only = (
        "---------------------- Forwarded by Sheila Example/HOU/OPS on 12/19/2000 11:35 \n"
        "AM ---------------------------"
    )
    time_wrapped = (
        "---------------------- Forwarded by Sheila Example/HOU/OPS on 12/19/2000\n"
        "11:35 AM ---------------------------"
    )
    for marker in (dashes_only, meridiem_only, time_wrapped):
        assert classify_lines(marker) == "ss", marker
    no_closing = (
        "----- Forwarded by Steve W Example/LON/OPS on 13/01/2000 11:22 \n\nOlder"
    )
    assert classify_lines(no_closing) == "set"


def test_split_wrapped_tail_forward_markers_keep_sender_and_day_first_date():
    cases = [
        (
            "---------------------- Forwarded by Steve W Example/LON/OPS on 13/01/2000 11:22 \n"
            "---------------------------",
            "steve w example/lon/ops",
            947762520.0,
        ),
        (
            "---------------------- Forwarded by Sheila Example/HOU/OPS on 12/19/2000 11:35 \n"
            "AM ---------------------------",
            "sheila example/hou/ops",
            977225700.0,
        ),
        (
            "---------------------- Forwarded by Sheila Example/HOU/OPS on 12/19/2000\n"
            "11:35 AM ---------------------------",
            "sheila example/hou/ops",
            977225700.0,
        ),
        (
            "----- Forwarded by Steve W Example/LON/OPS on 13/01/2000 11:22 ",
            "steve w example/lon/ops",
            947762520.0,
        ),
    ]
    for marker, sender, timestamp in cases:
        body = f"FYI\n\n{marker}\n\nOlder text.\n"
        own, forwarded = split_fragments(body)
        assert own.text == "FYI"
        assert forwarded.kind is FragmentKind.FORWARDED
        assert (forwarded.sender, forwarded.timestamp) == (sender, timestamp), marker
        assert forwarded.text == "Older text."
        assert forwarded.start == body.index("---")
        assert forwarded.end == len(body)


def test_split_tab_indented_from_line_with_blank_lines_inside_header():
    body = "\n".join(
        [
            "ok",
            "",
            "\t",
            "\tFrom:  Tim Example                           10/31/2000 01:54 PM",
            "\t",
            "To: David W Example/HOU/OPS@OPS",
            "cc:  ",
            "Subject: Commodity / Embedded Finance Deals",
            "",
            "body here",
            "",
        ]
    )
    assert classify_lines(body) == "teehehhhete"
    own, quoted = split_fragments(body)
    assert own.text == "ok"
    assert quoted.kind is FragmentKind.QUOTED
    assert quoted.sender == "tim example"
    assert quoted.timestamp == 973000440.0
    assert quoted.recipients == ("david w example/hou/ops@ops",)
    assert quoted.subject == "Commodity / Embedded Finance Deals"
    assert quoted.text == "body here"


def test_split_notes_name_with_at_suffix_and_day_first_date():
    body = "ok\n\nJerald Example@EES\n08/10/2001 11:06 AM\nTo: x@example.com\nSubject: s\n\nolder\n"
    own, quoted = split_fragments(body)
    assert own.text == "ok"
    assert quoted.sender == "jerald example@ees"
    assert quoted.timestamp == 997441560.0
    assert quoted.text == "older"
    body = "ok\n\nJames M Example@ACME_DEVELOPMENT\n19/12/2000 15:06\nTo: x@example.com\n\nolder\n"
    own, quoted = split_fragments(body)
    assert quoted.sender == "james m example@acme_development"
    assert quoted.timestamp == 977238360.0
    assert quoted.recipients == ("x@example.com",)
    assert quoted.text == "older"


def test_split_day_first_dates_only_when_unambiguous():
    head = "hi\n\n-----Original Message-----\nFrom: a@example.com\nSent: "
    # 13/01 can only be 13 January; 08/10 keeps the month-first default.
    assert (
        split_fragments(head + "13/01/2000 11:22\n\nold\n")[1].timestamp == 947762520.0
    )
    assert (
        split_fragments(head + "08/10/2001 10:53 AM\n\nold\n")[1].timestamp
        == 997440780.0
    )


def test_split_wrapped_forward_marker_starts_forwarded_fragment():
    fragments = split_fragments(WRAPPED_FORWARD)
    assert [f.kind for f in fragments] == [FragmentKind.OWN, FragmentKind.FORWARDED]
    own, forwarded = fragments
    assert own.text == "Please see below."
    assert forwarded.start == WRAPPED_FORWARD.index("---------------------- Forwarded")
    assert forwarded.end == len(WRAPPED_FORWARD)
    assert forwarded.depth == 1
    # The header block below the marker wins over the marker's own name and date.
    assert forwarded.sender == "nadia example"
    assert forwarded.timestamp == 994842720.0
    assert forwarded.subject == "Draft numbers"
    assert forwarded.recipients == ("mira okafor/dub/audit/acme@acme-eu",)
    assert forwarded.text == "Attached is the draft."


def test_split_forward_marker_supplies_sender_and_timestamp_without_headers():
    body = (
        "FYI\n\n----- Forwarded by Jo Example/Hou-MidOffice/Trading/PEC on\n"
        "10/31/2001 09:51 AM -----\n\nOlder text.\n"
    )
    own, forwarded = split_fragments(body)
    assert own.text == "FYI"
    assert forwarded.kind is FragmentKind.FORWARDED
    assert forwarded.sender == "jo example/hou-midoffice/trading/pec"
    assert forwarded.timestamp == 1004521860.0
    assert forwarded.text == "Older text."
    single = "FYI\n\n----- Forwarded by Jo Example/HOU/OPS on 07/11/2001 14:37 -----\n\nOlder text.\n"
    _, forwarded = split_fragments(single)
    assert forwarded.kind is FragmentKind.FORWARDED
    assert forwarded.sender == "jo example/hou/ops"
    assert forwarded.timestamp == 994862220.0


def test_classify_notes_two_line_reply_header():
    assert classify_lines(NOTES_REPLY) == "tehhhhhete"
    assert classify_lines("Scott Example/HOU/OPS@OPS\n08/21/2001 01:48 PM CDT") == "hh"
    assert classify_lines("Nadia Example\n07/11/2001 09:12") == "hh"
    # Two consecutive short lines are not a header unless the second is exactly a date.
    assert classify_lines("David Example\nSee you at 10:00") == "tt"
    assert classify_lines("Two short lines\nAnother line") == "tt"
    # And the first must look like a name: capitalized tokens, no sentence punctuation.
    assert classify_lines("Meeting notes\n08/10/2001 11:06 AM") == "tt"
    assert classify_lines("David Example.\n08/10/2001 11:06 AM") == "tt"
    assert classify_lines("Call me\n08/10/2001 11:06 AM") == "tt"


def test_split_notes_two_line_reply_header_is_a_quoted_fragment():
    fragments = split_fragments(NOTES_REPLY)
    assert [f.kind for f in fragments] == [FragmentKind.OWN, FragmentKind.QUOTED]
    own, quoted = fragments
    assert own.text == "Thanks, will do."
    assert quoted.start == NOTES_REPLY.index("David W Example")
    assert quoted.end == len(NOTES_REPLY)
    assert quoted.depth == 1
    assert quoted.sender == "david w example"
    assert quoted.timestamp == 997441560.0
    assert quoted.subject == "Remote Offices- Suggestions"
    assert quoted.recipients == (
        "dana leff/hou/ops@ops",
        "rick example/acme@acmegate",
        "janet example/hou/ops@ops",
    )
    assert quoted.text == "body text..."


def test_split_notes_header_with_org_path_and_timezone():
    body = "\n".join(
        [
            "ok",
            "",
            "Scott Example/HOU/OPS@OPS",
            "08/21/2001 01:48 PM CDT",
            "To:\tPat Example/HOU/OPS@OPS",
            "Subject:\tSites",
            "",
            "older",
            "",
        ]
    )
    own, quoted = split_fragments(body)
    assert own.text == "ok"
    assert quoted.kind is FragmentKind.QUOTED
    assert quoted.sender == "scott example/hou/ops@ops"
    assert quoted.timestamp == 998401680.0
    assert quoted.subject == "Sites"
    assert quoted.recipients == ("pat example/hou/ops@ops",)
    assert quoted.text == "older"


def test_split_from_line_ending_in_date_splits_sender_and_timestamp():
    cases = [
        (
            "From:\tRick Example/ACME@acmeXgate on 08/10/2001 10:53 AM",
            "rick example/acme@acmexgate",
            997440780.0,
        ),
        ("From: Ed Example on 09/26/2001 10:00 AM", "ed example", 1001498400.0),
        (
            "From:\tMonique Example/ACME@acmeXgate on 08/21/2001 01:48 PM CDT",
            "monique example/acme@acmexgate",
            998401680.0,
        ),
        (
            "From:\tJohn Example                           07/28/2000 10:06 AM",
            "john example",
            964778760.0,
        ),
    ]
    for line, sender, timestamp in cases:
        body = f"hi\n\n{line}\nTo:\tPat Example/HOU/OPS@OPS\nSubject:\tSites\n\nolder\n"
        own, quoted = split_fragments(body)
        assert own.text == "hi"
        assert quoted.kind is FragmentKind.QUOTED
        assert (quoted.sender, quoted.timestamp) == (sender, timestamp), line
        assert quoted.recipients == ("pat example/hou/ops@ops",)
        assert quoted.text == "older"


def test_split_indented_outlook_block_with_weekday_sent_line():
    assert classify_lines(INDENTED_OUTLOOK) == "teshhhhhete"
    own, quoted = split_fragments(INDENTED_OUTLOOK)
    assert own.text == "Yes."
    assert quoted.kind is FragmentKind.QUOTED
    assert quoted.start == INDENTED_OUTLOOK.index("\t-----Original")
    assert quoted.sender == "example, karl k se-se"
    assert quoted.timestamp == 1006424700.0
    assert quoted.recipients == ("example, rick",)
    assert quoted.subject == "FW: Status ??"
    assert quoted.text == "Older text."


def test_split_fragments_never_overlap_and_match_raw_regions():
    for body in (
        OUTLOOK_REPLY,
        LOTUS_DOUBLE_FORWARD,
        QUOTED_REPLY,
        WRAPPED_FORWARD,
        NOTES_REPLY,
        INDENTED_OUTLOOK,
    ):
        fragments = split_fragments(body)
        previous = 0
        for fragment in fragments:
            assert fragment.start >= previous
            assert fragment.end <= len(body)
            raw = raw_of(body, fragment)
            for line in fragment.text.splitlines():
                assert line in raw
            previous = fragment.end
        assert split_fragments(body) == fragments


# parse_email


def multipart(plain, html, *, extra_headers="", attachment=False):
    parts = [
        'From: "Lee, Sam" <Sam.Lee@example.com>',
        "To: Chen, Alex <alex@example.com>; pat@example.com",
        "Cc: jordan@example.com, alex@example.com",
        "Subject: Re: Budget   review",
        "Date: Fri, 10 Aug 2001 10:53:00 -0500",
        "Message-ID: <abc@example.com>",
        "In-Reply-To: <parent@example.com>",
        "References: <root@example.com> <parent@example.com>",
        "X-From: Sam Lee",
        "X-Folder: \\Sam_Lee\\Sent",
        "MIME-Version: 1.0",
        'Content-Type: multipart/mixed; boundary="outer"',
        "",
        "--outer",
        'Content-Type: multipart/alternative; boundary="inner"',
        "",
        "--inner",
        'Content-Type: text/plain; charset="utf-8"',
        "",
        plain,
        "--inner",
        'Content-Type: text/html; charset="utf-8"',
        "",
        html,
        "--inner--",
    ]
    if attachment:
        parts += [
            "--outer",
            'Content-Type: application/pdf; name="budget.pdf"',
            'Content-Disposition: attachment; filename="budget.pdf"',
            "Content-Transfer-Encoding: base64",
            "",
            "JVBERi0=",
        ]
    parts += ["--outer--", ""]
    text = "\r\n".join(parts)
    if extra_headers:
        text = extra_headers + "\r\n" + text
    return text.encode()


def test_parse_multipart_prefers_plain_text_over_html():
    plain = "Plain body here.\r\n\r\n-----Original Message-----\r\nFrom: Alex <alex@example.com>\r\nSubject: Budget review\r\n\r\nOlder text."
    message = parse_email(multipart(plain, "<p>HTML body here.</p>"), source="box/1")
    assert message.message_id == "<abc@example.com>"
    assert message.in_reply_to == "<parent@example.com>"
    assert message.references == ("<root@example.com>", "<parent@example.com>")
    assert message.timestamp == 997458780.0
    assert message.sender == "sam.lee@example.com"
    assert message.sender_name == "Lee, Sam"
    assert message.to == ("alex@example.com", "pat@example.com")
    assert message.cc == ("jordan@example.com", "alex@example.com")
    assert message.subject == "Re: Budget review"
    assert message.subject_key == "budget review"
    assert "\r" not in message.raw_body
    assert message.raw_body.startswith("Plain body here.\n\n-----Original")
    assert message.own_text == "Plain body here."
    assert [f.kind for f in message.fragments] == [
        FragmentKind.OWN,
        FragmentKind.QUOTED,
    ]
    assert message.fragments[1].sender == "alex@example.com"
    assert message.attachments == ()
    assert message.source == "box/1"
    assert message.headers["X-From"] == "Sam Lee"
    assert message.headers["X-Folder"] == "\\Sam_Lee\\Sent"
    assert message.headers["Subject"] == "Re: Budget   review"
    assert message.participants == frozenset(
        {
            "sam.lee@example.com",
            "alex@example.com",
            "pat@example.com",
            "jordan@example.com",
        }
    )
    assert message.bulk.recipient_count == 4
    assert not message.bulk.is_bulk


def test_parse_html_only_message_strips_tags_and_keeps_blockquotes():
    raw = (
        b"From: pat@example.com\nTo: alex@example.com\nMessage-ID: <h@example.com>\n"
        b"Content-Type: text/html; charset=utf-8\n\n"
        b"<html><head><style>p{color:red}</style><title>t</title></head><body>"
        b"<div>Hello <b>there</b> &amp; welcome</div><p>Second para</p>"
        b"<blockquote><p>quoted words</p></blockquote></body></html>"
    )
    message = parse_email(raw)
    assert message.raw_body == "Hello there & welcome\nSecond para\n> quoted words"
    assert message.own_text == "Hello there & welcome\nSecond para"
    assert [(f.kind, f.text) for f in message.fragments] == [
        (FragmentKind.OWN, "Hello there & welcome\nSecond para"),
        (FragmentKind.QUOTED, "quoted words"),
    ]


def test_parse_missing_message_id_is_deterministic():
    raw = b"From: pat@example.com\nTo: alex@example.com\nSubject: hi\nDate: Fri, 10 Aug 2001 10:53:00 +0000\n\nA short note.\n"
    first = parse_email(raw)
    second = parse_email(raw)
    assert first.message_id == second.message_id
    assert first.message_id.startswith("synthetic:")
    assert len(first.message_id) == len("synthetic:") + 24
    assert first == second
    different = parse_email(raw.replace(b"A short note.", b"Another note."))
    assert different.message_id != first.message_id
    assert parse_email(b"Message-ID:   \n\nx").message_id.startswith("synthetic:")
    # The whole body feeds the id, not just its first 200 characters.
    prefix = "x" * 200
    approved = parse_email(raw.replace(b"A short note.", f"{prefix} approved".encode()))
    denied = parse_email(raw.replace(b"A short note.", f"{prefix} denied".encode()))
    assert approved.message_id != denied.message_id


def test_parse_skips_attached_message_bodies():
    raw = "\r\n".join(
        [
            "From: pat@example.com",
            "To: alex@example.com",
            "Message-ID: <outer@example.com>",
            "MIME-Version: 1.0",
            'Content-Type: multipart/mixed; boundary="outer"',
            "",
            "--outer",
            'Content-Type: text/html; charset="utf-8"',
            "",
            "<p>Outer HTML words</p>",
            "--outer",
            "Content-Type: message/rfc822",
            'Content-Disposition: attachment; filename="old.eml"',
            "",
            "From: inner@example.com",
            "Subject: old",
            "Content-Type: text/plain",
            "",
            "Inner author words",
            "--outer--",
            "",
        ]
    ).encode()
    message = parse_email(raw)
    assert message.own_text == "Outer HTML words"
    assert message.attachments == ("old.eml",)
    assert "Inner author words" not in message.raw_body


def test_parse_date_header_keeps_meridiem_and_offset():
    head = b"From: pat@example.com\nMessage-ID: <d@example.com>\nDate: "
    late = parse_email(head + b"Friday, August 10, 2001 10:53 PM\n\nhi\n")
    assert late.timestamp == 997483980.0
    offset = parse_email(head + b"08/10/2001 10:53 AM -0500\n\nhi\n")
    assert offset.timestamp == 997458780.0
    rfc = parse_email(head + b"Fri, 10 Aug 2001 10:53:00 -0500\n\nhi\n")
    assert rfc.timestamp == 997458780.0


def test_parse_attachment_names():
    message = parse_email(multipart("Body.", "<p>Body.</p>", attachment=True))
    assert message.attachments == ("budget.pdf",)
    assert message.own_text == "Body."


def test_parse_bulk_signals():
    raw = (
        b"From: Alerts <no-reply@example.com>\nTo: pat@example.com\nCc: alex@example.com\n"
        b"List-Id: Dev list <dev.example.com>\nPrecedence: bulk\nMessage-ID: <b@example.com>\n\n"
        b"Build 4821 finished in 12 minutes.\n"
    )
    message = parse_email(raw)
    assert message.bulk.list_id == "Dev list <dev.example.com>"
    assert message.bulk.precedence == "bulk"
    assert message.bulk.noreply_sender is True
    assert message.bulk.recipient_count == 2
    assert message.bulk.is_bulk
    assert len(message.bulk.body_digest) == 24
    # Digits are part of the digest: different amounts or accounts are different mail.
    other_numbers = parse_email(raw.replace(b"4821", b"4822").replace(b"12", b"9"))
    assert other_numbers.bulk.body_digest != message.bulk.body_digest
    respaced = parse_email(raw.replace(b"Build 4821", b"BUILD   4821"))
    assert respaced.bulk.body_digest == message.bulk.body_digest
    person = parse_email(b"From: pat@example.com\nMessage-ID: <p@example.com>\n\nhi")
    assert person.bulk.noreply_sender is False
    assert not person.bulk.is_bulk


def test_parse_charset_fallback_decodes_with_replacement():
    raw = (
        b"From: pat@example.com\nMessage-ID: <c@example.com>\n"
        b'Content-Type: text/plain; charset="utf-8"\n\nCaf\xe9 note\n'
    )
    assert parse_email(raw).raw_body == "Caf� note\n"
    unknown = (
        b"From: pat@example.com\nMessage-ID: <c@example.com>\n"
        b'Content-Type: text/plain; charset="x-no-such-charset"\n\nCaf\xc3\xa9 note\n'
    )
    assert parse_email(unknown).raw_body == "Café note\n"


def test_parse_accepts_str_input_and_tolerates_bad_headers():
    text = "From: pat@example.com\nDate: not a date\nTo: <>\nSubject: =?utf-8?q?h=C3=A9llo?=\n\nhi\n"
    message = parse_email(text, source="inbox/9")
    assert message.timestamp == 0.0
    assert message.to == ()
    assert message.subject == "héllo"
    assert message.own_text == "hi"
    assert message.source == "inbox/9"
    assert parse_email(text, source="inbox/9") == message
    assert parse_email(text.encode(), source="inbox/9") == message
    empty = parse_email(b"")
    assert empty.message_id.startswith("synthetic:")
    assert empty.own_text == "" and empty.fragments == ()


def test_parse_decodes_undeclared_quoted_printable_leftovers():
    raw = (
        b"From: pat@example.com\nMessage-ID: <q@example.com>\n"
        b"Content-Type: text/plain; charset=utf-8\n\n"
        b"To:=09Someone@example.com=20\nline one=\n continues\n"
    )
    assert (
        parse_email(raw).raw_body == "To:\tSomeone@example.com \nline one continues\n"
    )
    # A declared transfer encoding means the library already handled it; leave it alone.
    declared = raw.replace(
        b"Message-ID", b"Content-Transfer-Encoding: 7bit\nMessage-ID"
    )
    assert (
        parse_email(declared).raw_body
        == "To:=09Someone@example.com=20\nline one=\n continues\n"
    )
    # A lone ``=`` before a newline is ordinary text, not encoding.
    sparse = b"From: pat@example.com\nMessage-ID: <s@example.com>\n\nx =\n y\n"
    assert parse_email(sparse).raw_body == "x =\n y\n"
