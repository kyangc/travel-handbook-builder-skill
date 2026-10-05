"""A narrow, managed persistence client over the public authoring API."""

import copy
import json

from . import (AuthoringError, apply, check, export_package, import_package,
               preview, read_workspace)
from .core import (_read_workspace_from_snapshot, _validate_importable_package,
                   _workspace_read_snapshot)
from . import _client_storage as storage
from ._client_storage import (
    CANONICAL_NAME,
    CLIENT_FORMAT,
    OPERATIONS_NAME,
    REPORT_NAME,
    STATE_NAME,
    ClientError,
    atomic_write_json,
    create_operation,
    file_sha256,
    initialize_layout,
    locked,
    operation_directories,
    operation_path,
    read_json,
    value_sha256,
    validate_layout,
)


FIXED_PATHS = {
    "state": STATE_NAME,
    "canonical": CANONICAL_NAME,
    "report": REPORT_NAME,
    "operations": OPERATIONS_NAME,
    "lock": ".travel-handbook-client.lock",
}
CLIENT_PAGE_SIZE = 100
SUPPORTED_PATCHES = {
    "set_if_absent": ["address", "timezone", "content.summary"],
    "append_unique": ["content.highlights", "content.visit_advice", "content.cautions"],
}
NO_CHANGE = object()
EVIDENCE_ONLY = object()


def _ref_key(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _source_refs(value):
    found = []
    if isinstance(value, dict):
        if set(value) >= {"source_ref"} and isinstance(value["source_ref"], dict):
            found.append(value["source_ref"])
        for child in value.values():
            found.extend(_source_refs(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_source_refs(child))
    return found


def _publish_status(state_revision, canonical_revision):
    if canonical_revision == state_revision:
        return "current"
    if canonical_revision < state_revision:
        return "stale"
    return "failed"


def _changed_intent_recovery(path, status):
    return {
        "action": "new_request_id_for_changed_intent",
        "reuse_request_id": False,
        "existing_operation_id": path.name,
        "existing_phase": status.get("phase"),
        "if_original_commit_unknown": "retry_same_operation_id_first",
    }


def _prepare_failure(error, path, request_id):
    details = copy.deepcopy(error.details)
    details["operation_id"] = path.name
    details["recovery"] = {
        "action": "correct_intent_with_new_request_id",
        "reuse_request_id": False,
        "failed_request_id": request_id,
        "failed_operation_id": path.name,
        "same_intent_retry": "reuse_original_request_id",
    }
    return ClientError(error.code, str(error), **details)


class ManagedHandbook:
    """Own the persistence lifecycle of one initialized handbook directory."""

    def __init__(self, root, marker):
        self.root = root
        self._marker = marker

    @classmethod
    def initialize(cls, root, *, state=None, package=None):
        if (state is None) == (package is None):
            raise ClientError("CLIENT_INPUT_ERROR", "Provide exactly one of state or package")
        if package is not None:
            managed_state = import_package(copy.deepcopy(package))
            managed_state["handles"] = {
                f"h-client-{managed_state['workspace_id'][:12]}-{index}": reference
                for index, (_, reference) in enumerate(
                    sorted(managed_state["handles"].items()), start=1)
            }
            recovery_mode = "package_only"
        else:
            managed_state = copy.deepcopy(state)
            recovery_mode = "full_state"
        validation = check(managed_state)
        if not validation.get("valid"):
            raise ClientError("CLIENT_STATE_NOT_READY", "State must be valid before initialization",
                              errors=validation.get("errors", []))
        exported = export_package(managed_state, revision=managed_state["revision"])
        marker = {
            "format": CLIENT_FORMAT,
            "workspace_id": managed_state["workspace_id"],
            "recovery_mode": recovery_mode,
            "paths": copy.deepcopy(FIXED_PATHS),
        }
        initialized_root = initialize_layout(
            root,
            marker=marker,
            state=managed_state,
            canonical=exported["package"],
            report={key: value for key, value in exported.items() if key != "package"},
        )
        return cls.open(initialized_root)

    @classmethod
    def open(cls, root):
        initialized_root, marker = validate_layout(root)
        book = cls(initialized_root, marker)
        book._validated_state_and_canonical()
        return book

    def _validated_state_and_canonical(self):
        state = read_json(self.root / STATE_NAME)
        canonical = read_json(self.root / CANONICAL_NAME)
        if state.get("workspace_id") != self._marker.get("workspace_id"):
            raise ClientError("CLIENT_WORKSPACE_MISMATCH",
                              "Managed state does not match the initialized workspace")
        validation = check(state)
        if not validation.get("valid"):
            raise ClientError("CLIENT_STATE_INVALID", "Managed state is not valid",
                              errors=validation.get("errors", []))
        if not isinstance(canonical, dict) or type(canonical.get("revision")) is not int:
            raise ClientError("CLIENT_CANONICAL_INVALID", "Managed canonical has no valid revision")
        try:
            _validate_importable_package(copy.deepcopy(canonical))
        except AuthoringError as error:
            raise ClientError("CLIENT_CANONICAL_INVALID", "Managed canonical is not valid",
                              error=error.as_dict()) from error
        return state, canonical, validation

    def status(self):
        with locked(self.root):
            state, canonical, _ = self._validated_state_and_canonical()
            state_revision = state["revision"]
            canonical_revision = canonical["revision"]
            publish_status = _publish_status(state_revision, canonical_revision)
            result = {
                "root": str(self.root),
                "workspace_id": state["workspace_id"],
                "recovery_mode": self._marker["recovery_mode"],
                "state_revision": state_revision,
                "canonical_revision": canonical_revision,
                "publish_status": publish_status,
                "canonical_path": str(self.root / CANONICAL_NAME),
                "integrity_scope": {
                    "checked": ["marker", "workspace_id", "revision", "fixed paths", "symlinks"],
                    "limitation": "same-revision external rewrites are not all detectable",
                },
            }
            operation_statuses = []
            for path in operation_directories(self.root):
                status_path = path / "status.json"
                operation_statuses.append((status_path.stat().st_mtime_ns, path.name,
                                           read_json(status_path)))
            phase_counts = {}
            for _, _, operation_status in operation_statuses:
                phase = operation_status.get("phase", "invalid")
                phase_counts[phase] = phase_counts.get(phase, 0) + 1
            result["operations"] = {"count": len(operation_statuses),
                                    "phases": phase_counts}
            if operation_statuses:
                _, operation_id, operation_status = max(operation_statuses)
                result["last_operation"] = {
                    "operation_id": operation_id,
                    "request_id": operation_status.get("request_id"),
                    "phase": operation_status.get("phase"),
                }
            if "import_report" in state:
                result["import_report"] = copy.deepcopy(state["import_report"])
            return result

    def check(self):
        """Return the complete current-state check, independent of publication age."""
        with locked(self.root):
            state, canonical, report = self._validated_state_and_canonical()
            state_revision = state["revision"]
            canonical_revision = canonical["revision"]
            return {
                "state_revision": state_revision,
                "canonical_revision": canonical_revision,
                "publish_status": _publish_status(state_revision, canonical_revision),
                "report": report,
            }

    def read(self, selection=None, limit=None, cursor=None, include_source_text=False, report=None,
             include_capabilities=True):
        """Read the current managed state through the public authoring surface."""
        with locked(self.root):
            state, canonical, _ = self._validated_state_and_canonical()
            result = read_workspace(
                state, selection=selection, limit=limit, cursor=cursor,
                include_source_text=include_source_text, report=report,
                include_capabilities=include_capabilities,
            )
            if report is not None:
                result['canonical_revision'] = canonical['revision']
                result['publish_status'] = _publish_status(state['revision'], canonical['revision'])
            return result

    def _read_pages(self, state, object_type, snapshot):
        objects = []
        cursor = None
        pages = 0
        while True:
            try:
                result = _read_workspace_from_snapshot(
                    state, snapshot,
                    selection={"types": [object_type]},
                    limit=CLIENT_PAGE_SIZE,
                    cursor=cursor,
                )
            except AuthoringError as error:
                if cursor is not None:
                    raise ClientError("CONTEXT_CHANGED", "Workspace changed during context scan",
                                      current_revision=state.get("revision")) from error
                raise
            pages += 1
            objects.extend(result["objects"])
            pagination = result["pagination"]
            if not pagination["has_more"]:
                return objects, pages
            cursor = pagination["next_cursor"]

    def place_context(self, *, target, source_text_handles=None):
        source_text_handles = [] if source_text_handles is None else source_text_handles
        if (not isinstance(target, dict) or len(target) != 1
                or next(iter(target), None) not in {"handle", "name"}):
            raise ClientError("CLIENT_INPUT_ERROR", "target requires exactly one handle or name")
        if not isinstance(source_text_handles, list) or any(
                not isinstance(handle, str) or not handle for handle in source_text_handles):
            raise ClientError("CLIENT_INPUT_ERROR", "source_text_handles must be a handle list")
        with locked(self.root):
            state, _, _ = self._validated_state_and_canonical()
            return self._place_context_from_state(state, target, source_text_handles)

    def _place_context_from_state(self, state, target, source_text_handles):
        snapshot = _workspace_read_snapshot(state)
        if "handle" in target:
            try:
                direct = _read_workspace_from_snapshot(
                    state, snapshot,
                    selection={"handles": [target["handle"]]},
                    limit=CLIENT_PAGE_SIZE,
                )
            except AuthoringError as error:
                if error.code in {"REFERENCE_NOT_FOUND", "INVALID_ARGUMENT"}:
                    raise ClientError("TARGET_NOT_FOUND", "Place handle was not found",
                                      handle=target["handle"]) from error
                raise
            candidates = [entry for entry in direct["objects"] if entry["type"] == "place"]
            if not candidates and direct['objects']:
                raise ClientError('TARGET_KIND_MISMATCH', 'client context supports Place only; use client read for this object',
                                  expected_type='place', actual_type=direct['objects'][0]['type'],
                                  handle=target['handle'],
                                  recovery={'argv': ['client', 'read', str(self.root), '--handle', target['handle']]})
            place_pages = 1
        else:
            places, place_pages = self._read_pages(state, "place", snapshot)
            candidates = [entry for entry in places
                          if entry["record"].get("name") == target["name"]]
        if not candidates:
            raise ClientError("TARGET_NOT_FOUND", "Place was not found", target=copy.deepcopy(target))
        if len(candidates) > 1:
            raise ClientError("TARGET_AMBIGUOUS", "Place name matches more than one record",
                              candidates=[{"handle": item["handle"],
                                           "name": item["record"].get("name")}
                                          for item in candidates])
        place = candidates[0]
        target_ref = state["handles"].get(place["handle"])

        notes, note_pages = self._read_pages(state, "guide_note", snapshot)
        related_notes = [entry for entry in notes
                         if target_ref in entry["record"].get("related_refs", [])]
        items, item_pages = self._read_pages(state, "item", snapshot)
        related_items = [entry for entry in items
                         if entry["record"].get("place_ref") == target_ref]
        issues, issue_pages = self._read_pages(state, "issue", snapshot)
        related_issues = [entry for entry in issues
                          if target_ref in entry["record"].get("target_refs", [])]
        wanted_source_refs = {_ref_key(ref) for ref in _source_refs(place["record"])}
        for note in related_notes:
            wanted_source_refs.update(_ref_key(ref) for ref in _source_refs(note["record"]))
        sources, source_pages = self._read_pages(state, "source", snapshot)
        related_sources = [entry for entry in sources
                           if _ref_key(state["handles"].get(entry["handle"]))
                           in wanted_source_refs]
        related_handles = {entry["handle"] for entry in related_sources}
        invalid_text_handles = [handle for handle in source_text_handles
                                if handle not in related_handles]
        if invalid_text_handles:
            raise ClientError("SOURCE_NOT_RELATED",
                              "Source text can only be requested for related Sources",
                              handles=invalid_text_handles)
        source_texts = {}
        unavailable = []
        for handle in source_text_handles:
            selected = _read_workspace_from_snapshot(
                state, snapshot,
                selection={"handles": [handle]},
                limit=CLIENT_PAGE_SIZE,
                include_source_text=True,
            )
            snapshots = selected.get("source_texts", [])
            if snapshots:
                source_texts[handle] = copy.deepcopy(snapshots)
            else:
                unavailable.append(handle)
        return {
            "revision": state["revision"],
            "recovery_mode": self._marker["recovery_mode"],
            "place": copy.deepcopy(place),
            "related_guide_notes": copy.deepcopy(related_notes),
            "related_items": copy.deepcopy(related_items),
            "related_issues": copy.deepcopy(related_issues),
            "association_review": {
                "needed": bool(related_items and (related_notes or related_issues)),
                "reason": "place-linked text may describe mutable arrangements",
                "automatic_text_or_issue_change": False,
            },
            "sources": copy.deepcopy(related_sources),
            "source_texts": source_texts,
            "source_text_unavailable": unavailable,
            "supported_patches": copy.deepcopy(SUPPORTED_PATCHES),
            "pages_scanned": {
                "place": place_pages,
                "guide_note": note_pages,
                "item": item_pages,
                "issue": issue_pages,
                "source": source_pages,
            },
            "complete": True,
        }

    def _find_operation_by_request_id(self, request_id):
        for path in operation_directories(self.root):
            status = read_json(path / "status.json")
            if status.get("request_id") == request_id:
                return path, status
        return None, None

    def _reject_unjournaled_receipt(self, state, request_id):
        if request_id in state["receipts"]:
            raise ClientError(
                "REQUEST_ID_ALREADY_COMMITTED",
                "request_id belongs to a successful request outside this managed journal",
                request_id=request_id, current_revision=state["revision"],
            )

    def _prepared_result(self, path, status):
        result = {
            "operation_id": path.name,
            "request_id": status["request_id"],
            "status": status["phase"],
            "intent_sha256": status["intent_sha256"],
        }
        for name in ("request_sha256", "expected_revision", "proposed_revision", "methods",
                     "source_written", "guide_note_written", "unsupported"):
            if name in status:
                result[name] = copy.deepcopy(status[name])
        preview_path = path / "preview.json"
        if preview_path.exists():
            result["preview"] = read_json(preview_path)
        return result

    def _resume_prepare(self, path, status, state):
        if status.get("phase") not in {"intent_saved", "request_saved", "prepare_failed"}:
            return status
        request_path = path / "request.json"
        if status.get("kind") == "professional_request" and status["phase"] == "intent_saved":
            intent_path = path / "intent.json"
            if file_sha256(intent_path) != status.get("intent_sha256"):
                raise ClientError("CLIENT_INTENT_CORRUPT", "Persisted request intent is corrupted",
                                  operation_id=path.name)
            intent = read_json(intent_path)
            if not request_path.exists():
                atomic_write_json(request_path, intent)
            elif file_sha256(request_path) != status["intent_sha256"]:
                raise ClientError("CLIENT_REQUEST_CORRUPT", "Interrupted request differs from intent",
                                  operation_id=path.name)
            status.update({
                "phase": "request_saved",
                "request_sha256": file_sha256(request_path),
                "expected_revision": intent["expected_revision"],
                "methods": [operation.get("method") if isinstance(operation, dict) else None
                            for operation in intent["operations"]]
                if isinstance(intent["operations"], list) else [],
            })
            atomic_write_json(path / "status.json", status)
        if not request_path.exists():
            raise ClientError("CLIENT_NOT_PREPARED",
                              "Interrupted operation has no persisted request to preview",
                              operation_id=path.name, phase=status.get("phase"))
        if file_sha256(request_path) != status.get("request_sha256"):
            raise ClientError("CLIENT_REQUEST_CORRUPT", "Persisted request hash does not match",
                              operation_id=path.name)
        request = read_json(request_path)
        try:
            preview_result = preview(state, request)
        except AuthoringError as error:
            client_error = _prepare_failure(error, path, status["request_id"])
            atomic_write_json(path / "error.json", client_error.as_dict())
            status["phase"] = "prepare_failed"
            atomic_write_json(path / "status.json", status)
            raise client_error from error
        atomic_write_json(path / "preview.json", preview_result)
        status.update({
            "phase": "prepared",
            "proposed_revision": preview_result["proposed_revision"],
        })
        if status.get("kind") != "professional_request":
            status.update({"source_written": False, "guide_note_written": False})
        atomic_write_json(path / "status.json", status)
        return status

    def prepare_request(self, request):
        """Journal and preview one existing public authoring request."""
        if (not isinstance(request, dict)
                or set(request) != {"request_id", "expected_revision", "operations"}
                or not isinstance(request["request_id"], str)
                or not request["request_id"].strip()):
            raise ClientError("CLIENT_INPUT_ERROR", "Expected a public authoring request")
        intent = copy.deepcopy(request)
        intent_hash = value_sha256(intent)
        with locked(self.root):
            state, _, _ = self._validated_state_and_canonical()
            existing_path, existing_status = self._find_operation_by_request_id(intent["request_id"])
            if existing_path is not None:
                if (existing_status.get("kind") != "professional_request"
                        or existing_status.get("intent_sha256") != intent_hash):
                    raise ClientError("REQUEST_ID_REUSED",
                                      "request_id already belongs to a different managed operation",
                                      operation_id=existing_path.name,
                                      recovery=_changed_intent_recovery(existing_path, existing_status))
                if file_sha256(existing_path / "intent.json") != intent_hash:
                    raise ClientError("CLIENT_INTENT_CORRUPT", "Persisted request intent is corrupted",
                                      operation_id=existing_path.name)
                if existing_status.get("phase") != "intent_saved":
                    request_path = existing_path / "request.json"
                    if (not request_path.exists()
                            or file_sha256(request_path) != existing_status.get("request_sha256")):
                        raise ClientError("CLIENT_REQUEST_CORRUPT", "Persisted request is corrupted",
                                          operation_id=existing_path.name)
                existing_status = self._resume_prepare(existing_path, existing_status, state)
                return self._prepared_result(existing_path, existing_status)
            self._reject_unjournaled_receipt(state, intent["request_id"])
            _, path = create_operation(
                self.root, intent=intent, request_id=intent["request_id"],
                intent_sha256=intent_hash, kind="professional_request",
            )
            atomic_write_json(path / "request.json", intent)
            status = {
                "kind": "professional_request",
                "phase": "request_saved",
                "request_id": intent["request_id"],
                "intent_sha256": intent_hash,
                "request_sha256": file_sha256(path / "request.json"),
                "expected_revision": intent["expected_revision"],
                "methods": [operation.get("method") if isinstance(operation, dict) else None
                            for operation in intent["operations"]]
                if isinstance(intent["operations"], list) else [],
            }
            atomic_write_json(path / "status.json", status)
            storage._fault("after_request_persisted")
            status = self._resume_prepare(path, status, state)
            return self._prepared_result(path, status)

    def _compile_enrichment(self, edit, context):
        patch = edit["patch"]
        if not isinstance(patch, dict) or set(patch) != {"path", "op", "value"}:
            raise ClientError("CLIENT_INPUT_ERROR", "patch requires path, op, and value only")
        path, operation, value = patch["path"], patch["op"], patch["value"]
        if path not in SUPPORTED_PATCHES.get(operation, []):
            availability = isinstance(path, str) and (path == "availability" or path.startswith("availability."))
            reason = "availability" if availability else (
                "deletion" if operation in {"clear", "remove"} else "correction")
            raise ClientError(
                "CLIENT_UNSUPPORTED_EDIT",
                "Managed enrichment supports additions to a fixed set of fields only",
                unsupported={
                    "reason": reason,
                    "requested_path": path,
                    "requested_op": operation,
                    "boundary": {
                        "guide": "references/DEFAULT_WORKFLOW_GUIDE.md" if not availability
                        else "references/HOURS_IMPACT_GUIDE.md",
                        "method": "place.hours.update" if availability else "place.update",
                    },
                    "safe_exit": "managed state and canonical were preserved; use client read and the cited guide, then client prepare-request/commit in this root",
                },
            )
        if not isinstance(value, str) or not value.strip():
            raise ClientError("CLIENT_INPUT_ERROR", "patch.value must be a nonempty string")
        place_record = context["place"]["record"]
        patch_changed = True
        if operation == "set_if_absent":
            if path.startswith("content."):
                field = path.split(".", 1)[1]
                current = place_record.get("content", {}).get(field)
            else:
                field = path
                current = place_record.get(field)
            if current is not None:
                if current == value:
                    patch_changed = False
                else:
                    raise ClientError("EXISTING_VALUE_CONFLICT",
                                      "Managed enrichment does not overwrite an existing value",
                                      path=path, current_value=current)
            else:
                if path.startswith("content."):
                    content = copy.deepcopy(place_record.get("content", {}))
                    content[field] = value
                    place_set = {"content": content}
                else:
                    place_set = {field: value}
        else:
            field = path.split(".", 1)[1]
            content = copy.deepcopy(place_record.get("content", {}))
            current = content.get(field, [])
            if not isinstance(current, list):
                raise ClientError("CLIENT_STATE_INVALID", "Supported content list has an invalid shape",
                                  path=path)
            if value in current:
                patch_changed = False
            else:
                content[field] = [*current, value]
                place_set = {"content": content}

        source = edit["source"]
        if not isinstance(source, dict) or len(source) != 1 or next(iter(source), None) not in {"new", "existing"}:
            raise ClientError("CLIENT_INPUT_ERROR", "source requires exactly one new or existing choice")
        operations = []
        if "new" in source:
            source_value = source["new"]
            allowed = {"kind", "title", "url", "published_at", "notes"}
            if (not isinstance(source_value, dict) or set(source_value) - allowed
                    or not {"kind", "title"} <= set(source_value)):
                raise ClientError("CLIENT_INPUT_ERROR", "new source has unsupported or missing fields")
            if patch_changed:
                operations.append({"method": "source.record", "as": "client_source",
                                   "args": copy.deepcopy(source_value)})
            source_ref = {"local": "client_source"}
            existing_source_record = None
        else:
            existing = source["existing"]
            if not isinstance(existing, dict) or set(existing) != {"handle"}:
                raise ClientError("CLIENT_INPUT_ERROR", "existing source requires one handle")
            related_handles = {entry["handle"] for entry in context["sources"]}
            if existing["handle"] not in related_handles:
                raise ClientError("SOURCE_NOT_RELATED", "Existing Source must come from target context",
                                  handle=existing["handle"])
            source_ref = {"handle": existing["handle"]}
            existing_source_record = next(entry["record"] for entry in context["sources"]
                                          if entry["handle"] == existing["handle"])
        guide_note = edit["guide_note"]
        if not isinstance(guide_note, dict) or set(guide_note) != {"title", "text"}:
            raise ClientError("CLIENT_INPUT_ERROR", "guide_note requires title and text only")
        if any(not isinstance(guide_note[name], str) or not guide_note[name].strip()
               for name in ("title", "text")):
            raise ClientError("CLIENT_INPUT_ERROR", "guide_note title and text must be nonempty")
        exact_note_exists = False
        if existing_source_record is not None:
            expected_paragraph = {
                "text": guide_note["text"],
                "citations": [{"source_ref": {
                    "type": "source", "id": existing_source_record["id"]}}],
            }
            target_ref = {"type": "place", "id": place_record["id"]}
            exact_note_exists = any(
                note["record"].get("title") == guide_note["title"]
                and note["record"].get("paragraphs") == [expected_paragraph]
                and note["record"].get("related_refs") == [target_ref]
                for note in context["related_guide_notes"]
            )
        if not patch_changed:
            if existing_source_record is None:
                return EVIDENCE_ONLY
            return NO_CHANGE if exact_note_exists else EVIDENCE_ONLY
        operations.append({"method": "place.update", "args": {
            "target": {"handle": context["place"]["handle"]},
            "set": place_set,
        }})
        if not exact_note_exists:
            operations.append({"method": "guide.note.add", "as": "client_guide_note", "args": {
                "title": guide_note["title"],
                "related": [{"handle": context["place"]["handle"]}],
                "paragraphs": [{"text": guide_note["text"],
                                "citations": [{"source": source_ref}]}],
            }})
        return {
            "request_id": edit["request_id"],
            "expected_revision": edit["expected_revision"],
            "operations": operations,
        }

    def prepare_place_enrichment(self, edit):
        required = {"request_id", "expected_revision", "target", "patch", "source", "guide_note"}
        if not isinstance(edit, dict) or set(edit) != required:
            raise ClientError("CLIENT_INPUT_ERROR", "Enrichment intent has missing or unsupported fields")
        if not isinstance(edit["request_id"], str) or not edit["request_id"].strip():
            raise ClientError("CLIENT_INPUT_ERROR", "request_id must be nonempty")
        if type(edit["expected_revision"]) is not int:
            raise ClientError("CLIENT_INPUT_ERROR", "expected_revision must be an integer")
        if (not isinstance(edit["target"], dict) or set(edit["target"]) != {"handle"}
                or not isinstance(edit["target"]["handle"], str)):
            raise ClientError("CLIENT_INPUT_ERROR", "prepare target requires one Place handle")
        intent = copy.deepcopy(edit)
        intent_hash = value_sha256(intent)

        with locked(self.root):
            state, _, _ = self._validated_state_and_canonical()
            existing_path, existing_status = self._find_operation_by_request_id(edit["request_id"])
            if existing_path is not None:
                if (existing_status.get("kind") == "professional_request"
                        or existing_status.get("intent_sha256") != intent_hash):
                    raise ClientError("REQUEST_ID_REUSED",
                                      "request_id already belongs to a different enrichment intent",
                                      operation_id=existing_path.name,
                                      recovery=_changed_intent_recovery(existing_path, existing_status))
                if file_sha256(existing_path / "intent.json") != intent_hash:
                    raise ClientError("CLIENT_INTENT_CORRUPT", "Persisted enrichment intent is corrupted",
                                      operation_id=existing_path.name)
                existing_status = self._resume_prepare(existing_path, existing_status, state)
                return self._prepared_result(existing_path, existing_status)
            self._reject_unjournaled_receipt(state, intent["request_id"])
            context = self._place_context_from_state(state, edit["target"], [])
            if state["revision"] != edit["expected_revision"]:
                raise ClientError("REVISION_CONFLICT", "Read fresh context before preparing enrichment",
                                  current_revision=state["revision"])
            _, path = create_operation(
                self.root,
                intent=intent,
                request_id=edit["request_id"],
                intent_sha256=intent_hash,
            )
            try:
                request = self._compile_enrichment(edit, context)
            except ClientError as error:
                status = {
                    "phase": "unsupported" if error.code == "CLIENT_UNSUPPORTED_EDIT" else "failed",
                    "request_id": edit["request_id"],
                    "intent_sha256": intent_hash,
                    "unsupported": copy.deepcopy(error.details.get("unsupported")),
                    "source_written": False,
                    "guide_note_written": False,
                }
                atomic_write_json(path / "error.json", error.as_dict())
                atomic_write_json(path / "status.json", status)
                if error.code == "CLIENT_UNSUPPORTED_EDIT":
                    return self._prepared_result(path, status)
                raise
            if request is NO_CHANGE:
                status = {
                    "phase": "no_change",
                    "request_id": edit["request_id"],
                    "intent_sha256": intent_hash,
                    "source_written": False,
                    "guide_note_written": False,
                }
                atomic_write_json(path / "status.json", status)
                return self._prepared_result(path, status)
            if request is EVIDENCE_ONLY:
                status = {
                    "phase": "unsupported",
                    "request_id": edit["request_id"],
                    "intent_sha256": intent_hash,
                    "source_written": False,
                    "guide_note_written": False,
                    "unsupported": {
                        "reason": "evidence_only",
                        "boundary": {"guide": "references/GUIDE_NOTE_GUIDE.md",
                                     "method": "guide.note.add"},
                        "safe_exit": "existing text was preserved and the proposed evidence was not adopted; use client read and the cited guide, then client prepare-request/commit in this root",
                    },
                }
                atomic_write_json(path / "status.json", status)
                return self._prepared_result(path, status)
            atomic_write_json(path / "request.json", request)
            request_hash = file_sha256(path / "request.json")
            status = {
                "phase": "request_saved",
                "request_id": edit["request_id"],
                "intent_sha256": intent_hash,
                "request_sha256": request_hash,
                "expected_revision": request["expected_revision"],
                "methods": [operation["method"] for operation in request["operations"]],
            }
            atomic_write_json(path / "status.json", status)
            storage._fault("after_request_persisted")
            persisted_request = read_json(path / "request.json")
            try:
                preview_result = preview(state, persisted_request)
            except AuthoringError as error:
                client_error = _prepare_failure(error, path, edit["request_id"])
                atomic_write_json(path / "error.json", client_error.as_dict())
                status["phase"] = "prepare_failed"
                atomic_write_json(path / "status.json", status)
                raise client_error from error
            atomic_write_json(path / "preview.json", preview_result)
            status.update({
                "phase": "prepared",
                "proposed_revision": preview_result["proposed_revision"],
                "source_written": False,
                "guide_note_written": False,
            })
            atomic_write_json(path / "status.json", status)
            return self._prepared_result(path, status)

    def _publish_current_state(self, state):
        validation = check(state)
        if not validation.get("valid"):
            raise ClientError("CLIENT_EXPORT_FAILED", "Committed state did not pass validation",
                              errors=validation.get("errors", []))
        exported = export_package(state, revision=state["revision"])
        storage._fault("before_canonical_validation")
        _validate_importable_package(copy.deepcopy(exported["package"]))
        atomic_write_json(
            self.root / REPORT_NAME,
            {key: value for key, value in exported.items() if key != "package"},
        )
        storage._fault("after_report_before_canonical")
        atomic_write_json(self.root / CANONICAL_NAME, exported["package"])

    def _actual_canonical_revision(self):
        try:
            canonical = read_json(self.root / CANONICAL_NAME)
        except ClientError:
            return None
        return canonical.get("revision") if isinstance(canonical, dict) else None

    def _confirmed_commit_storage_error(self, *, operation_id, state, receipt, error, code):
        canonical_revision = self._actual_canonical_revision()
        return {
            "committed": True,
            "replayed": bool(receipt.get("replayed")),
            "operation_revision": receipt["original_commit_revision"],
            "state_revision": state["revision"],
            "canonical_revision": canonical_revision,
            "publish_status": ("current" if canonical_revision == state["revision"] else "stale"),
            "canonical_path": str(self.root / CANONICAL_NAME),
            "refresh_same_page": canonical_revision == state["revision"],
            "receipt": receipt,
            "warnings": copy.deepcopy(receipt.get("warnings", [])),
            "error": {
                "code": code,
                "message": str(error),
                "durability": "state was reread with the exact receipt after a storage error",
            },
            "recovery": {
                "action": "retry_same_operation_id",
                "operation_id": operation_id,
                "new_request_id": False,
            },
        }

    def _unknown_commit_storage_error(self, *, operation_id, error):
        return {
            "committed": None,
            "commit_status": "unknown",
            "canonical_revision": self._actual_canonical_revision(),
            "publish_status": "unknown",
            "canonical_path": str(self.root / CANONICAL_NAME),
            "refresh_same_page": False,
            "error": {
                "code": "CLIENT_COMMIT_STATUS_UNKNOWN",
                "message": str(error),
            },
            "recovery": {
                "action": "retry_same_operation_id",
                "operation_id": operation_id,
                "new_request_id": False,
            },
        }

    def _commit_storage_error_result(self, *, operation_id, request, error, code):
        try:
            persisted_state = read_json(self.root / STATE_NAME)
            _, confirmed_receipt = apply(persisted_state, request)
        except (AuthoringError, ClientError, OSError):
            return self._unknown_commit_storage_error(
                operation_id=operation_id, error=error)
        if not confirmed_receipt.get("replayed"):
            return self._unknown_commit_storage_error(
                operation_id=operation_id, error=error)
        return self._confirmed_commit_storage_error(
            operation_id=operation_id,
            state=persisted_state,
            receipt=confirmed_receipt,
            error=error,
            code=code,
        )

    def commit(self, operation_id):
        with locked(self.root):
            state, _, _ = self._validated_state_and_canonical()
            path = operation_path(self.root, operation_id)
            status = read_json(path / "status.json")
            request_path = path / "request.json"
            if not request_path.exists():
                raise ClientError("CLIENT_NOT_PREPARED", "Operation has no prepared request",
                                  operation_id=operation_id, phase=status.get("phase"))
            actual_hash = file_sha256(request_path)
            if actual_hash != status.get("request_sha256"):
                raise ClientError("CLIENT_REQUEST_CORRUPT", "Persisted request hash does not match",
                                  operation_id=operation_id)
            request = read_json(request_path)
            if status.get("phase") in {"request_saved", "prepare_failed"}:
                preview_result = preview(state, request)
                atomic_write_json(path / "preview.json", preview_result)
                status["phase"] = "prepared"
                status["proposed_revision"] = preview_result["proposed_revision"]
                atomic_write_json(path / "status.json", status)
            try:
                new_state, receipt = apply(state, request)
            except AuthoringError as error:
                details = copy.deepcopy(error.details)
                if error.code == "REVISION_CONFLICT" and status.get("kind") == "professional_request":
                    details["recovery"] = {
                        "action": "client_read_then_prepare_new_request",
                        "reuse_request_id": False,
                    }
                elif error.code == "REVISION_CONFLICT":
                    intent = read_json(path / "intent.json")
                    target_handle = intent.get("target", {}).get("handle")
                    try:
                        selected = read_workspace(
                            state, selection={"handles": [target_handle]}, limit=1)
                        place = next(entry for entry in selected["objects"]
                                     if entry["type"] == "place")
                        details["target_context"] = {
                            "revision": state["revision"],
                            "handle": place["handle"],
                            "name": place["record"].get("name"),
                            "content": copy.deepcopy(place["record"].get("content")),
                        }
                    except (AuthoringError, StopIteration):
                        details["target_context"] = {
                            "revision": state["revision"],
                            "handle": target_handle,
                            "unavailable": True,
                        }
                client_error = ClientError(error.code, str(error), **details)
                atomic_write_json(path / "error.json", client_error.as_dict())
                status["phase"] = "commit_failed"
                atomic_write_json(path / "status.json", status)
                raise client_error from error
            storage._fault("after_apply_before_state")
            try:
                atomic_write_json(self.root / STATE_NAME, new_state)
            except OSError as error:
                return self._commit_storage_error_result(
                    operation_id=operation_id,
                    request=request,
                    error=error,
                    code="CLIENT_STATE_SAVE_UNCERTAIN",
                )
            storage._fault("after_state_replace")
            operation_revision = receipt["original_commit_revision"]
            try:
                atomic_write_json(path / "receipt.json", receipt)
                status.update({"phase": "committed", "operation_revision": operation_revision})
                atomic_write_json(path / "status.json", status)
            except OSError as error:
                return self._commit_storage_error_result(
                    operation_id=operation_id,
                    request=request,
                    error=error,
                    code="CLIENT_OPERATION_JOURNAL_FAILED",
                )
            storage._fault("after_receipt")
            try:
                self._publish_current_state(new_state)
            except Exception as error:
                detail = ({"code": error.code, "message": str(error),
                           **copy.deepcopy(error.details)}
                          if isinstance(error, AuthoringError) else
                          {"code": "CLIENT_EXPORT_FAILED", "message": str(error)})
                status["phase"] = "publish_failed"
                try:
                    atomic_write_json(path / "error.json", detail)
                    atomic_write_json(path / "status.json", status)
                except OSError as journal_error:
                    return self._commit_storage_error_result(
                        operation_id=operation_id,
                        request=request,
                        error=journal_error,
                        code="CLIENT_OPERATION_JOURNAL_FAILED",
                    )
                actual_canonical = read_json(self.root / CANONICAL_NAME)
                return {
                    "committed": True,
                    "replayed": bool(receipt.get("replayed")),
                    "operation_revision": operation_revision,
                    "state_revision": new_state["revision"],
                    "canonical_revision": actual_canonical.get("revision"),
                    "publish_status": "failed",
                    "canonical_path": str(self.root / CANONICAL_NAME),
                    "refresh_same_page": False,
                    "receipt": receipt,
                    "warnings": copy.deepcopy(receipt.get("warnings", [])),
                    "error": detail,
                }
            status["phase"] = "complete"
            try:
                atomic_write_json(path / "status.json", status)
            except OSError as error:
                return self._commit_storage_error_result(
                    operation_id=operation_id,
                    request=request,
                    error=error,
                    code="CLIENT_OPERATION_JOURNAL_FAILED",
                )
            current_canonical = read_json(self.root / CANONICAL_NAME)
            return {
                "committed": True,
                "replayed": bool(receipt.get("replayed")),
                "operation_revision": operation_revision,
                "state_revision": new_state["revision"],
                "canonical_revision": current_canonical["revision"],
                "publish_status": "current",
                "canonical_path": str(self.root / CANONICAL_NAME),
                "refresh_same_page": True,
                "receipt": receipt,
                "warnings": copy.deepcopy(receipt.get("warnings", [])),
            }


__all__ = ["ClientError", "ManagedHandbook"]
