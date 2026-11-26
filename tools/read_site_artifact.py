"""Read one frozen public static-site artifact; never execute the reviewed site."""
import base64
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import PurePosixPath
import re
import selectors
import stat
import struct
import subprocess
import sys
import time
import zipfile

REPO = "Tcuzzo/Tcuzzo.github.io"
PIN = {
    "run_id": "45772044182",
    "run_attempt": "1",
    "job_id": "139746769820",
    "artifact_id": "15094875880",
    "head_sha": "ba4cef80a09fa9226f0d37c968f08062e4132237",
    "zip_sha256": "7b47e89a6cab23996141d1f578bef75cf4dc5698c6b8a72252878db9a76b73a5",
}
TARGETS = (
    "home", "hydra", "research", "router", "hydra-evidence",
    "hydra-console", "research-evidence", "research-console",
)
WIDTHS = (1440, 390)
SVGS = tuple("hydra/figures/" + name + ".svg" for name in (
    "failure-flow", "overview", "request-flow", "setup-map", "typed-routing",
))
CHECKS = "site-review/browser-checks.json"
PNGS = tuple(f"site-review/{target}-{width}.png" for width in WIDTHS for target in TARGETS)
ALLOWED = set(SVGS + PNGS + (CHECKS,))
MAX_ZIP = 8 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024
CHUNK = 12 * 1024
DEADLINE = time.monotonic() + 180


class CollectionError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise CollectionError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def emit(event, **fields):
    print("SITE_EVIDENCE_V1 " + json.dumps(
        {"event": event, **fields}, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ), flush=True)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def parse_json(data):
    def invalid_constant(_value):
        raise CollectionError("non-finite JSON value")
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


def gh_bytes(suffix, limit):
    """Bound both pipes, elapsed time, and the fixed-repository GET response."""
    deadline = min(DEADLINE, time.monotonic() + 45)
    require(time.monotonic() < deadline, "collection deadline exhausted")
    command = [
        "gh", "api", "--hostname", "github.com", "--method", "GET",
        "-H", "Accept: application/vnd.github+json",
        "-H", "X-GitHub-Api-Version: 2022-11-28", f"repos/{REPO}/{suffix}",
    ]
    environment = dict(os.environ, GH_HOST="github.com", GH_PROMPT_DISABLED="1", GH_DEBUG="")
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=environment) as process:
        output = bytearray()
        stderr_size = 0
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, "stdout")
                selector.register(process.stderr, selectors.EVENT_READ, "stderr")
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    require(remaining > 0, "GitHub GET timed out")
                    for key, _mask in selector.select(remaining):
                        block = os.read(key.fileobj.fileno(), 65536)
                        if not block:
                            selector.unregister(key.fileobj)
                        elif key.data == "stdout":
                            require(len(output) + len(block) <= limit, "GitHub response exceeds bound")
                            output.extend(block)
                        else:
                            stderr_size += len(block)
                            require(stderr_size <= 16384, "GitHub diagnostic output exceeds bound")
                remaining = deadline - time.monotonic()
                require(remaining > 0, "GitHub GET timed out")
                process.wait(timeout=remaining)
            require(process.returncode == 0, "GitHub GET failed; diagnostics withheld")
            return bytes(output)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def api(suffix):
    raw = gh_bytes(suffix, 512 * 1024)
    return parse_json(raw), sha256(raw)


def frozen_identity():
    for key in ("run_id", "run_attempt", "job_id", "artifact_id"):
        require(re.fullmatch(r"[1-9][0-9]*", PIN[key]) is not None, f"freeze {key} first")
    for key, length in (("head_sha", 40), ("zip_sha256", 64)):
        require(re.fullmatch("[0-9a-f]{" + str(length) + "}", PIN[key]) is not None,
                f"freeze {key} first")
    run_id, attempt, job_id, artifact_id = (
        int(PIN[key]) for key in ("run_id", "run_attempt", "job_id", "artifact_id")
    )
    run, run_hash = api(f"actions/runs/{run_id}")
    job, job_hash = api(f"actions/jobs/{job_id}")
    jobs, jobs_hash = api(f"actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
    artifact, artifact_hash = api(f"actions/artifacts/{artifact_id}")
    require(run["id"] == run_id and run["run_attempt"] == attempt, "run identity mismatch")
    require(run["repository"]["full_name"] == REPO and run["repository"]["private"] is False,
            "source repository is not the expected public repository")
    require(run["head_repository"]["full_name"] == REPO
            and run["head_repository"]["private"] is False, "head repository mismatch")
    require(run["head_sha"] == PIN["head_sha"] and run["event"] == "pull_request",
            "run head or event mismatch")
    require(run["path"] == ".github/workflows/site-check.yml", "workflow path mismatch")
    require(run["status"] == "completed" and run["conclusion"] == "success", "source run not successful")
    require(job["id"] == job_id and job["run_id"] == run_id
            and job["run_attempt"] == attempt and job["head_sha"] == PIN["head_sha"],
            "job identity mismatch")
    require(job["name"] == "site" and job["status"] == "completed"
            and job["conclusion"] == "success", "source job not successful")
    require(jobs["total_count"] == 1 and len(jobs["jobs"]) == 1
            and jobs["jobs"][0]["id"] == job_id, "source attempt is not the expected single job")
    required_steps = {
        "Require committed charts to match their sources",
        "Capture the changed surfaces",
        "Preserve rendered chart and review images",
    }
    successful = {step["name"] for step in job["steps"]
                  if step["status"] == "completed" and step["conclusion"] == "success"}
    require(required_steps <= successful, "required source capture steps not successful")
    require(artifact["id"] == artifact_id and artifact["name"] == "static-site-review"
            and artifact["expired"] is False, "artifact identity or availability mismatch")
    link = artifact["workflow_run"]
    require(link["id"] == run_id and link["head_sha"] == PIN["head_sha"]
            and link["repository_id"] == run["repository"]["id"]
            and link["head_repository_id"] == run["head_repository"]["id"],
            "artifact is not bound to the expected run and repositories")
    started, completed, created = (datetime.fromisoformat(value) for value in (
        job["started_at"], job["completed_at"], artifact["created_at"]
    ))
    require(all(value.tzinfo is not None for value in (started, completed, created))
            and started <= created <= completed, "artifact creation is outside the source job")
    require(artifact["digest"] == "sha256:" + PIN["zip_sha256"], "artifact digest metadata mismatch")
    size = artifact["size_in_bytes"]
    require(type(size) is int and 0 < size <= MAX_ZIP, "artifact size outside bound")
    identity = {
        **PIN, "repository": REPO, "workflow": run["path"], "job_name": job["name"],
        "artifact_name": artifact["name"], "size_in_bytes": size,
        "run_status": run["status"], "run_conclusion": run["conclusion"],
        "job_status": job["status"], "job_conclusion": job["conclusion"],
        "job_started_at": job["started_at"], "job_completed_at": job["completed_at"],
        "artifact_created_at": artifact["created_at"],
        "artifact_job_link": "single source job and matching creation interval",
        "api_response_sha256": {"run": run_hash, "job": job_hash,
                                "attempt_jobs": jobs_hash, "artifact": artifact_hash},
    }
    return identity


def archive_members(raw):
    require(raw.startswith(b"PK\x03\x04"), "archive signature mismatch")
    members = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        require(len(infos) == len(ALLOWED) and len(set(names)) == len(names)
                and set(names) == ALLOWED, "archive member allowlist or uniqueness mismatch")
        require(sum(info.file_size for info in infos) <= MAX_TOTAL, "archive total exceeds bound")
        for info in infos:
            name = info.filename
            require(name == info.orig_filename and "\\" not in name
                    and not PurePosixPath(name).is_absolute()
                    and ".." not in PurePosixPath(name).parts, "unsafe archive member name")
            mode = stat.S_IFMT(info.external_attr >> 16)
            require(not info.is_dir() and mode in (0, stat.S_IFREG), "non-regular archive member")
            require(not (info.flag_bits & 1) and info.compress_type in (
                zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), "unsupported archive encoding")
            limit = 2 * 1024 * 1024 if name.endswith(".png") else 512 * 1024
            require(0 < info.file_size <= limit and 0 <= info.compress_size <= MAX_ZIP,
                    "archive member exceeds bound")
            with archive.open(info) as member:
                data = member.read(limit + 1)
            require(len(data) == info.file_size, "archive member length mismatch")
            members[name] = data
    return members


def emit_blob(name, data, mime):
    digest = sha256(data)
    count = (len(data) + CHUNK - 1) // CHUNK
    emit("blob-start", name=name, mime=mime, bytes=len(data), sha256=digest, chunks=count)
    for index, start in enumerate(range(0, len(data), CHUNK)):
        chunk = data[start:start + CHUNK]
        emit("blob-chunk", name=name, index=index, sha256=sha256(chunk),
             base64=base64.b64encode(chunk).decode("ascii"))
    emit("blob-end", name=name, sha256=digest, chunks=count)
    return {"name": name, "mime": mime, "bytes": len(data), "sha256": digest, "chunks": count}


def validate_browser(members):
    rows = parse_json(members[CHECKS])
    expected = {(target, width) for target in TARGETS for width in WIDTHS}
    require(isinstance(rows, list) and len(rows) == len(expected), "browser check count mismatch")
    seen = set()
    for row in rows:
        require(isinstance(row, dict), "browser check is not an object")
        target, width = row.get("target"), row.get("width")
        require(isinstance(target, str) and type(width) is int, "browser target types invalid")
        pair = (target, width)
        require(pair in expected and pair not in seen, "browser targets missing or duplicated")
        seen.add(pair)
        name = f"site-review/{target}-{width}.png"
        require(row.get("screenshot") == name and row.get("overflow") is False
                and row.get("varied") is True and row.get("failures") == [],
                "browser check reports failure")
        require(isinstance(row.get("title"), str) and 0 < len(row["title"]) <= 512,
                "browser title missing or oversized")
        png = members[name]
        require(len(png) >= 33 and png[:8] == b"\x89PNG\r\n\x1a\n"
                and png[8:16] == b"\x00\x00\x00\rIHDR", "PNG header invalid")
        image_width, image_height = struct.unpack(">II", png[16:24])
        require(type(row.get("imageWidth")) is int and type(row.get("imageHeight")) is int
                and row["imageWidth"] == image_width and row["imageHeight"] == image_height,
                "PNG dimensions do not match browser receipt")
        require(0 < image_width <= width and 0 < image_height <= 4096
                and image_width * image_height <= 6_000_000, "PNG dimensions exceed bounds")
        if target != "router":
            require((image_width, image_height) == (width, 1000), "viewport PNG dimensions mismatch")
    require(seen == expected, "browser targets incomplete")
    return len(rows)


def main():
    identity = frozen_identity()
    raw = gh_bytes(f"actions/artifacts/{PIN['artifact_id']}/zip", MAX_ZIP)
    require(len(raw) == identity["size_in_bytes"], "downloaded archive size mismatch")
    require(sha256(raw) == PIN["zip_sha256"], "downloaded archive digest mismatch")
    members = archive_members(raw)
    # Publish the actual evidence before any final collection verdict.
    emit("raw-browser-checks", name=CHECKS, bytes=len(members[CHECKS]),
         sha256=sha256(members[CHECKS]), utf8=members[CHECKS].decode("utf-8"))
    manifest = [emit_blob("static-site-review.zip", raw, "application/zip")]
    for name in (CHECKS,) + SVGS + PNGS:
        mime = "application/json" if name == CHECKS else (
            "image/svg+xml" if name.endswith(".svg") else "image/png"
        )
        manifest.append(emit_blob(name, members[name], mime))
    count = validate_browser(members)
    emit("collection-verdict", status="COLLECTED_AND_BOUND", identity=identity,
         browser_checks=count, files=manifest, runtime_acceptance=False,
         visual_review_required=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        emit("collection-verdict", status="FAILED", error_type=type(error).__name__,
             reason=str(error) if isinstance(error, CollectionError) else "collection did not complete",
             runtime_acceptance=False, visual_review_required=True)
        sys.exit(1)
