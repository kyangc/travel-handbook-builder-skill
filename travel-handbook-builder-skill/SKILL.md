---
name: travel-handbook-builder-skill
description: Create or revise a private typed travel handbook from supplied material and bounded public research. Use for handbook authoring, not for choosing travel plans, booking, or publishing.
---

# Travel handbook builder

Turn traveler choices and sourced facts into a private handbook. The runtime records typed requests; the Agent interprets material. Keep unknowns explicit. Do not choose destinations, hotels, flights, visits, daily themes, or final routes for the traveler.

## Common path

Resolve paths from this Skill directory. See [setup](README.md) for installation or an existing Python. Use `scripts/travel-handbook` for file-backed work and `scripts/preview-service` for the local browser. The [default CLI workflow](references/DEFAULT_WORKFLOW_GUIDE.md) gives create, edit, and preview commands. Load [Python examples](references/PYTHON_OPTIONAL_GUIDE.md) only for programmatic state handling. Public `read` capabilities and the [method index](references/README.md) define the available operations; do not invent methods from implementation details.

For a new handbook, preserve the actual initial request and receipt. Read its revision, review `preview`, then `apply` that same request and run `check`. After a valid check, initialize a new managed directory with `client init ROOT --state FULL_STATE` **before the first browser opening**. Start the persistent preview for that ROOT and retain its URL. Later work stays in the same ROOT through `client context`/`client read`, `client prepare-place` or `client prepare-request`, and `client commit`. Read the [managed client guide](references/CLIENT_GUIDE.md) when preparing a change or recovering a response. Never edit managed state or canonical files directly.

Use supplied material and, where helpful, bounded reliable public research to make already selected destinations readable. A name-only Place is valid but does not prove content work is complete. Missing optional images, hours, duration, coordinates, prices, bookings, or tickets do not block a first version. Read [content collection](references/CONTENT_COLLECTION_GUIDE.md) when researching or placing facts. Preserve source identity, applicable dates, exceptions, uncertainty, and traveler decisions. Public schedules are not confirmed bookings.

For an edit, read the current object and related context first. Use `prepare-place` only for a supported non-overwriting Place supplement; use a public semantic request through `prepare-request` for corrections, availability, arrangement changes, or an `unsupported` result. Review the preview, commit its operation ID, read back affected objects, and check publication status. Keep other fields intact, including siblings when replacing a composite value. If the response is uncertain, retry the same operation ID. Do not recreate an object to simulate an edit.

## Boundaries

- Existing objects use public `{"handle": "..."}` references; within a batch use `{"local": "..."}` aliases. Set `expected_revision` from a current read. Replay requires the original request ID and identical payload; a new ID is a new write.
- On a failed preview or structured error, inspect its code and validation path before making a corrected request. Preserve manual edits, completed actions, and confirmed facts.
- Place content describes the place; this visit's date, time, and dwell belong to its active Day/Item. Do not infer travel time or a chosen route from gaps between activities.
- `check.valid`, current canonical, and an HTTP response establish different things. Inspect the rendered page before claiming text or images are visible. Neither a local preview nor export proves facts, feasibility, bookings, or public publication.
- Before the first map preview, use `scripts/preview-service maps-status ROOT`. If no Google Maps key was offered or configured, ask once; continue authoring, and use `maps-skip ROOT` on decline or no answer. `maps-configure ROOT` reads a private key on standard input. Never put it in requests, exports, arguments, logs, or links. Without a key the map has points and lines but no basemap; see [setup](README.md).

## Load only the relevant detail

- Complete source text, citations, uncertain Place identity or movement endpoints: [source and identity decisions](references/RECOMMENDATION_ROUTE_DECISION_GUIDE.md).
- Place facts, coordinates, notes, hours, or images: [content collection](references/CONTENT_COLLECTION_GUIDE.md), then the matching topic in the [method index](references/README.md).
- Dates, moves, withdrawal, routes, lodging, Tasks, weather, or source updates: select the matching guide from the [method index](references/README.md). An existing Visit refined into a Route uses `route.bind_visit`; withdrawal and unlinking are not full deletion.
- Browser service, media paths, or recovery: [browser preview](references/BROWSER_PREVIEW_GUIDE.md) and [managed client](references/CLIENT_GUIDE.md).

Deliver the actual change, material sources and conditions, important unknowns, preview URL and managed ROOT, and level of visual verification. Keep raw handles and request IDs in the managed record unless audit or handoff needs them.
