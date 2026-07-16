from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from pathlib import Path
from pathlib import PurePosixPath

from inward_eyes.io import write_json


RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SOURCE_ID_PATTERN = re.compile(r"^S[0-9]{3}$")
WINDOWS_RESERVED_BASENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
CONTINUATION_HANDOFF_PATH = ".inward-eyes-handoff.json"
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def validate_run_id(run_id: str) -> str:
    value = str(run_id or "")
    basename = value.split(".", 1)[0].upper()
    if (
        not RUN_ID_PATTERN.fullmatch(value)
        or value in {".", ".."}
        or value.endswith(".")
        or basename in WINDOWS_RESERVED_BASENAMES
    ):
        raise ValueError(
            "run_id must be 1-128 ASCII letters, digits, dots, underscores, or hyphens, "
            "must start with a letter or digit, and must not contain path separators"
        )
    return value


def validate_source_id(source_id: str) -> str:
    value = str(source_id or "")
    if not SOURCE_ID_PATTERN.fullmatch(value):
        raise ValueError("source_id must match S followed by exactly three digits (for example S001)")
    return value


def resolve_run_relative(run_dir: Path, raw_path: str | Path, *, must_exist: bool = False) -> Path:
    root = run_dir.resolve()
    raw_value = str(raw_path)
    if (
        not raw_value
        or "\x00" in raw_value
        or "\\" in raw_value
        or ":" in raw_value
        or raw_value.startswith("/")
        or raw_value.endswith("/")
    ):
        raise ValueError(f"run-relative path required: {raw_path}")
    raw_parts = raw_value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError(f"canonical run-relative path required: {raw_path}")
    path = PurePosixPath(*raw_parts)
    candidate = (root / Path(*path.parts)).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes run directory: {raw_path}") from exc
    if must_exist and not candidate.exists():
        raise FileNotFoundError(candidate)
    return candidate


def create_continuation_handoff(
    run_dir: Path,
    *,
    run_id: str,
    from_stage: str,
    to_stage: str,
    input_path: str,
    artifact_sha256: dict[str, str] | None = None,
) -> str:
    safe_run_id = validate_run_id(run_id)
    if not from_stage or not to_stage:
        raise ValueError("continuation stages must be non-empty")
    resolve_run_relative(run_dir, input_path, must_exist=True)
    bound_artifact_sha256 = _validated_artifact_sha256(run_dir, artifact_sha256)
    marker_path = resolve_run_relative(run_dir, CONTINUATION_HANDOFF_PATH)
    if marker_path.exists():
        raise FileExistsError(f"continuation handoff already exists: {marker_path}")
    token = secrets.token_urlsafe(32)
    authenticated_fields = {
        "schema_version": "1.0",
        "run_id": safe_run_id,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "input_path": input_path,
        "artifact_sha256": bound_artifact_sha256,
    }
    write_json(
        marker_path,
        {
            **authenticated_fields,
            "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
            "handoff_hmac_sha256": hmac.new(
                token.encode("utf-8"),
                _canonical_handoff_payload(authenticated_fields),
                hashlib.sha256,
            ).hexdigest(),
        },
    )
    return token


def _canonical_handoff_payload(fields: dict[str, object]) -> bytes:
    return json.dumps(
        fields,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _validated_artifact_sha256(
    run_dir: Path,
    artifact_sha256: dict[str, str] | None,
) -> dict[str, str]:
    if artifact_sha256 is None:
        return {}
    if not isinstance(artifact_sha256, dict):
        raise ValueError("continuation artifact digests must be an object")
    validated: dict[str, str] = {}
    for raw_path, digest in artifact_sha256.items():
        if not isinstance(raw_path, str):
            raise ValueError("continuation artifact digest paths must be strings")
        resolve_run_relative(run_dir, raw_path, must_exist=True)
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise ValueError(f"continuation artifact digest is invalid: {raw_path}")
        validated[raw_path] = digest
    return dict(sorted(validated.items()))


def _consume_continuation_handoff(
    run_dir: Path,
    *,
    run_id: str,
    to_stage: str,
    input_path: str,
    token: str,
    artifact_sha256: dict[str, str] | None,
) -> None:
    marker_path = resolve_run_relative(run_dir, CONTINUATION_HANDOFF_PATH)
    claimed_path = marker_path.with_name(
        f".{marker_path.name}.claimed-{os.getpid()}-{secrets.token_hex(4)}"
    )
    try:
        marker_path.rename(claimed_path)
    except FileNotFoundError as exc:
        raise PermissionError("continuation handoff is missing or already consumed") from exc
    try:
        with claimed_path.open("r", encoding="utf-8") as handle:
            handoff = json.load(handle)
        if not isinstance(handoff, dict):
            raise ValueError("continuation handoff must be a JSON object")
        expected_token_sha = str(handoff.get("token_sha256") or "")
        actual_token_sha = hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()
        if not expected_token_sha or not hmac.compare_digest(expected_token_sha, actual_token_sha):
            raise PermissionError("continuation handoff token does not match")
        authenticated_fields = {
            "schema_version": handoff.get("schema_version"),
            "run_id": handoff.get("run_id"),
            "from_stage": handoff.get("from_stage"),
            "to_stage": handoff.get("to_stage"),
            "input_path": handoff.get("input_path"),
            "artifact_sha256": handoff.get("artifact_sha256"),
        }
        expected_hmac = handoff.get("handoff_hmac_sha256")
        actual_hmac = hmac.new(
            str(token).encode("utf-8"),
            _canonical_handoff_payload(authenticated_fields),
            hashlib.sha256,
        ).hexdigest()
        if not isinstance(expected_hmac, str) or not hmac.compare_digest(expected_hmac, actual_hmac):
            raise PermissionError("continuation handoff authentication does not match")
        if handoff.get("schema_version") != "1.0":
            raise ValueError("continuation handoff schema_version is invalid")
        if not isinstance(handoff.get("from_stage"), str) or not handoff["from_stage"]:
            raise ValueError("continuation handoff source stage is invalid")
        if handoff.get("run_id") != run_id:
            raise ValueError("continuation handoff run_id does not match")
        if handoff.get("to_stage") != to_stage:
            raise ValueError("continuation handoff target stage does not match")
        if handoff.get("input_path") != input_path:
            raise ValueError("continuation handoff input path does not match")
        resolve_run_relative(run_dir, input_path, must_exist=True)
        expected_artifact_sha256 = handoff.get("artifact_sha256", {})
        if not isinstance(expected_artifact_sha256, dict):
            raise ValueError("continuation handoff artifact digests must be an object")
        actual_artifact_sha256 = _validated_artifact_sha256(run_dir, artifact_sha256)
        if expected_artifact_sha256 != actual_artifact_sha256:
            raise PermissionError("continuation handoff artifact digests do not match")
    except BaseException:
        try:
            os.link(claimed_path, marker_path)
        except FileExistsError:
            claimed_path.unlink(missing_ok=True)
        except OSError as restore_exc:
            raise RuntimeError(
                "continuation handoff validation failed and the handoff could not be restored"
            ) from restore_exc
        else:
            claimed_path.unlink(missing_ok=True)
        raise
    else:
        claimed_path.unlink(missing_ok=True)


def prepare_run_dir(
    output_root: str | Path,
    run_id: str,
    *,
    continue_existing: bool = False,
    continuation_required_paths: tuple[str, ...] = (),
    continuation_manifest_tasks: tuple[str, ...] = (),
    continuation_manifest_path: str = "manifest.json",
    continuation_token: str | None = None,
    continuation_stage: str | None = None,
    continuation_input_path: str | None = None,
    continuation_artifact_sha256: dict[str, str] | None = None,
) -> Path:
    safe_run_id = validate_run_id(run_id)
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_dir = resolve_run_relative(root, safe_run_id)
    if continue_existing:
        if not run_dir.is_dir():
            raise FileNotFoundError(f"run directory does not exist for continuation: {run_dir}")
        for required_path in continuation_required_paths:
            resolve_run_relative(run_dir, required_path, must_exist=True)
        if continuation_manifest_tasks:
            manifest_path = resolve_run_relative(run_dir, continuation_manifest_path, must_exist=True)
            with manifest_path.open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            if not isinstance(manifest, dict):
                raise ValueError("existing manifest must be a JSON object")
            if manifest.get("run_id") != safe_run_id:
                raise ValueError("existing manifest run_id does not match requested continuation")
            if manifest.get("task") not in continuation_manifest_tasks:
                raise ValueError(
                    f"existing manifest task is not an allowed continuation stage: {manifest.get('task')}"
                )
        if not continuation_token or not continuation_stage or not continuation_input_path:
            raise PermissionError("continuation requires a one-time handoff token, stage, and input path")
        _consume_continuation_handoff(
            run_dir,
            run_id=safe_run_id,
            to_stage=continuation_stage,
            input_path=continuation_input_path,
            token=continuation_token,
            artifact_sha256=continuation_artifact_sha256,
        )
    else:
        if (
            continuation_token
            or continuation_stage
            or continuation_input_path
            or continuation_artifact_sha256 is not None
        ):
            raise ValueError("continuation handoff arguments require continue_existing=True")
        try:
            run_dir.mkdir()
        except FileExistsError as exc:
            raise FileExistsError(f"run directory already exists; choose a new run_id: {run_dir}") from exc
    return run_dir
