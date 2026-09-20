# Source and authoring identity decisions

Read this guide before authoring when the caller has complete source text; a recommendation whose Place identity may be unclear; a movement or return statement with a missing endpoint; an unconfirmed entrance; or a Route segment with an explicit clock, service fact, or movement label. It selects among existing public methods; it does not add a parser, inferred identity, automatic synchronization, or a new conflict protocol. Use the linked topic guides for complete method signatures. If those guides do not resolve a question, use the public guide index and live `read_workspace(state)["capabilities"]`; do not inspect runtime source, Schema, tests, or historical payloads to invent a protocol.

## Preserve the supplied source and continuation state

When complete source text is available, define the Trip, then call `source.register` with the complete text and a stable `document_key` before interpreting it into structured objects. This stores an immutable snapshot in the authoring state so a later session can recover the original wording, calculate exact citation ranges, and compare a later revision. Do not replace the full text with selected paraphrases or fragments.

The snapshot remains authoring metadata in the complete state; it is not copied in full into the canonical handbook package. If wording must remain visible in that package, preserve the necessary passage as a GuideNote, with an exact snapshot citation when available. Follow [the source guide](SOURCE_GUIDE.md) for immutable snapshots and [the note and citation guide](GUIDE_NOTE_GUIDE.md) for citation input.

If the supplied material explicitly identifies itself as synthetic or fictional, preserve that attribution on every Source cited by the GuideNote paragraph. A parallel `synthetic_fixture` citation does not change a generic snapshot Source. For an exact snapshot citation, include the literal label `synthetic` in the registered snapshot title, while retaining any supplied `fictional` wording; otherwise cite only the `synthetic_fixture` Source. Each exported citation must be safe to read on its own.

Save the complete state after each committed batch. When checking an idempotent replay or resumed write, compare the complete state and revision with the expected result. Object counts alone cannot prove that snapshots, handles, receipts, bindings, decisions, or Issue resolution metadata survived.

## Keep an exact successful-request journal

The complete state preserves runtime receipts, but it is not the caller's copy of the request payload. After every successful public write, save the exact original request object in a caller-owned `request-journal.json` alongside the other work products:

```json
{
  "format_version": 1,
  "requests": [
    {
      "request_id": "caller-chosen-stable-id",
      "expected_revision": 0,
      "operations": []
    }
  ]
}
```

The example shows the journal shape; a real entry retains the complete submitted request, including every operation and optional field. Add an entry only after `apply` or CLI `apply` succeeds. A failed request and a preview are not successful writes. Keep one copy of an already journaled request when an exact replay returns the original receipt.

In the first authoring round, write `output/request-journal.json`. In a continuation round, load `input/request-journal.json`, preserve every prior entry unchanged, append each newly successful request in commit order, and write the merged journal to `output/request-journal.json`. Store it outside the installed skill directory. This journal is caller persistence metadata, not travel-domain data: do not insert it into private state fields, `source_imports`, GuideNotes, or the canonical package.

To test a same-request replay, select the original object from the journal and submit it unchanged. Do not change its `request_id`, `expected_revision`, operations, ordering, or optional fields, even when the current workspace revision has advanced. Do not reconstruct the payload from a receipt, a read result, reconciliation prose, or remembered intent. A successful historical replay may return `historical_receipt=true`; verify that the complete state and current revision remain unchanged.

If the journal or original entry is missing, report that exact replay cannot be demonstrated. Submitting a reconstructed payload under an old request ID may correctly return `REQUEST_ID_REUSED`; that rejection proves payload protection, not a successful same-request replay.

## Decide whether a suggestion identifies a Place

`recommendation.add` represents a recommendation for a specific existing Place. A Place is identified when the source supplies a stable, distinguishable real-world place or feature identity. A formal category, roles, address, coordinates, and location are not required for identity; omit those fields when they are unknown.

If the source names a specific feature, or uniquely scopes one within its stated parent or context, create or reuse that Place and add the Recommendation. Preserve the source's recommendation wording and do not attach it to a nearby but different Place. The source must supply the distinguishing identity; do not invent a name, scope, or parent.

If the source recommends only a generic category, facility, experience, or other idea and does not distinguish one Place:

- Do not create a placeholder Place, attach the statement to a nearby Place, or create an Item just to retain the words.
- Preserve the original suggestion in a canonical GuideNote. Cite the registered source snapshot when available, and relate the note to a supported context handle only when that relationship is explicit.
- Record in the caller's source reconciliation that a typed Recommendation could not be created because Place identity is missing. The current public API has no generic typed-gap object.

A GuideNote preserves canonical narrative; it does not become a typed Recommendation. If a later source identifies a stable, distinguishable Place, use [the recommendation guide](RECOMMENDATION_GUIDE.md) to decide whether a new Recommendation is supported.

The example below assumes the Trip is defined and the sequential upgrades required by the GuideNote method are complete.

```python
start = source_text.index(exact_suggestion)
end = start + len(exact_suggestion)

{"method": "source.register", "as": "source", "args": {
    "document_key": stable_document_key,
    "title": source_title,
    "text": source_text
}}
{"method": "guide.note.add", "args": {
    "title": note_title,
    "paragraphs": [{
        "text": exact_suggestion,
        "citations": [{"anchor": {
            "source": {"local": "source"},
            "start": start,
            "end": end,
            "exact_text": exact_suggestion
        }}]
    }]
}}
```

## Do not infer a return endpoint

Each independent `journey.compose` Leg requires an explicit source-supported `from` and `to`. A statement that a return time is unknown conveys timing or return intent, but it does not by itself identify the return destination. Do not reverse the preceding Leg, default to the earlier origin, or create a return Leg whose endpoint comes only from itinerary symmetry.

Create only the Legs whose endpoints the source supplies. Preserve an incomplete return statement in a GuideNote or source reconciliation, and record the endpoint as a data gap when that distinction matters. If the source explicitly names the return destination, the endpoint is known even when its departure or arrival time remains unknown.

Follow [the movement guide](MOVEMENT_GUIDE.md) for the complete `journey.compose` contract. This rule concerns endpoint evidence; it does not require a clock for an otherwise explicit independent Leg.

## Require a specific AccessPoint identity

Create an AccessPoint only when the source establishes a distinct entrance, gate, terminal, platform, or other fine-grained endpoint identity. Its coordinates and precise location may remain unknown after that identity exists. A statement that an entrance or parking entrance is unconfirmed does not establish a specific AccessPoint identity, so do not invent a placeholder AccessPoint name or later rename that placeholder into a newly confirmed entrance.

Preserve the original uncertainty in a GuideNote or citation. When the source explicitly calls for verification, an Issue or Task may target the parent Place without asserting that an AccessPoint already exists. A later source that identifies a specific entrance supports a new AccessPoint; omit its location until location evidence is available.

Follow [the access point guide](ACCESS_POINT_GUIDE.md) for required fields and bounded updates. Location uncertainty is a field-level unknown only after the endpoint identity is supported.

## Choose inline or Leg-backed Route segments

Choose the segment shape from the facts supplied for that segment:

| Supplied fact | Route representation |
|---|---|
| Mode, duration, distance, path, or notes only | Inline Segment |
| A segment-specific start/end clock or service fact | Segment with a `leg` |
| Service and Calls have enough explicit identity for the scheduled contract | Scheduled Leg, following the transport service guide |
| A clock is known but service number, operator, or service date is missing | Independent Leg with the known timing; leave the missing service fields unknown |

The same Route may mix inline and Leg-backed segments. Do not demote a known segment clock into stop purpose, free-text notes, or only the Route's overall timing. A service number is not required for an independent Leg.

```python
{"key": segment_key, "from": from_stop_key, "to": to_stop_key, "leg": {
    "mode": supplied_mode,
    "timing": {"kind": supplied_certainty, "start": {
        "local": supplied_local_datetime,
        "timezone": supplied_timezone
    }}
}}
```

Keep distinct source modes distinct on each segment. A segment explicitly described as generic walking remains `mode: "walking"`; wording attached to a segment that explicitly describes hiking, trekking, or traversing a trail can support `mode: "other"` with `mode_label: "hiking"`; a bus segment remains `mode: "bus"`. Explicit road-passenger wording such as shuttle bus, shuttle coach, 接驳车, 接驳巴士, 摆渡车, or 班车 is also `mode: "bus"`. Choose scheduled versus independent separately: an unknown operator does not block a scheduled Service; explicit `service_number`, `service_date`, and valid Calls use the scheduled contract, even when some Call times are explicitly unknown. Use an independent bus Leg only when the required service identity or legal Calls are unavailable. Keep a bare, category-ambiguous “shuttle” unresolved if the source does not establish whether it is a road vehicle, rail, ferry, or another mode. A Route title or a neighboring segment does not override the wording for the segment being represented. Do not collapse these labels because they occur in one Route. Store duration in `duration_minutes`; a clock belongs to Leg timing, while Route-level timing describes the overall arrangement.

See [the movement guide](MOVEMENT_GUIDE.md) for Route and inline Segment fields and [the transport service guide](TRANSPORT_SERVICE_GUIDE.md) for independent and scheduled Legs. Missing identity or unsupported revision behavior remains an explicit gap; do not fabricate source conflicts or call a source-field method that the live capabilities do not expose.
