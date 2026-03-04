#!/usr/bin/env python3
"""SessionStart hook: snapshot Claude Code environment for reproducibility.

Captures git SHA, CLAUDE.md hash + content, and skills directory hash.
Writes a sidecar JSON file that the Stop hook reads to enrich traces.

Registers CLAUDE.md as a versioned prompt in MLflow's Prompt Registry
so each trace can be linked to the exact instruction version.
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


def snapshot_environment(project_dir: str) -> dict:
    """Capture environment state for the given project directory.

    Returns a dict with git_sha, git_dirty, claude_md_hash,
    claude_md_content, skills_hash, snapshot_timestamp, and
    prompt registration info (prompt_name, prompt_version).
    """
    git_sha, git_dirty = _git_state(project_dir)
    claude_md_hash, claude_md_content = _claude_md_state(project_dir)
    skills_hash = _skills_hash(project_dir)
    prompt_name, prompt_version = _register_claude_md_prompt(
        claude_md_content, claude_md_hash, git_sha
    )

    return {
        "git_sha": git_sha,
        "git_dirty": git_dirty,
        "claude_md_hash": claude_md_hash,
        "claude_md_content": claude_md_content,
        "skills_hash": skills_hash,
        "prompt_name": prompt_name,
        "prompt_version": prompt_version,
        "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _git_state(project_dir: str) -> tuple[str, str]:
    """Return (sha, dirty_flag). Both 'none' if not a git repo."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if sha.returncode != 0:
            return "none", "none"

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        is_dirty = bool(status.stdout.strip())
        return sha.stdout.strip(), str(is_dirty).lower()
    except Exception:
        return "none", "none"


def _claude_md_state(project_dir: str) -> tuple[str, str]:
    """Return (hash, content). Hash is 'none' and content '' if missing or unreadable."""
    path = os.path.join(project_dir, "CLAUDE.md")
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return h, content
    except Exception:
        return "none", ""


def _skills_hash(project_dir: str) -> str:
    """SHA-256 of sorted SKILL.md files under skills/. 'none' if no skills dir."""
    skills_dir = os.path.join(project_dir, "skills")
    if not os.path.isdir(skills_dir):
        return "none"

    try:
        parts = []
        for root, _dirs, files in os.walk(skills_dir):
            for fname in files:
                if fname == "SKILL.md":
                    fpath = os.path.join(root, fname)
                    relpath = os.path.relpath(fpath, skills_dir)
                    try:
                        with open(fpath, encoding="utf-8") as f:
                            parts.append((relpath, f.read()))
                    except Exception:
                        continue

        if not parts:
            return "none"

        parts.sort(key=lambda t: t[0])
        combined = "\0".join(f"{relpath}\n{content}" for relpath, content in parts)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()
    except Exception:
        return "none"


def _register_claude_md_prompt(
    content: str, content_hash: str, git_sha: str
) -> tuple[str | None, int | None]:
    """Register CLAUDE.md as a versioned prompt in MLflow's Prompt Registry.

    Only creates a new version when the content hash changes.
    Returns (prompt_name, version) or (None, None) on failure/no content.
    """
    if not content or content_hash == "none":
        return None, None

    try:
        import mlflow.genai

        prompt_name = "claude-md"
        commit_msg = f"git:{git_sha[:8]}" if git_sha != "none" else "no-git"

        # Check if latest version already has this hash
        try:
            latest = mlflow.genai.load_prompt(f"prompts:/{prompt_name}/latest")
            if latest.template == content:
                # Content unchanged — return existing version
                return prompt_name, latest.version
        except Exception:
            pass  # Prompt doesn't exist yet, will be created

        pv = mlflow.genai.register_prompt(
            name=prompt_name,
            template=content,
            commit_message=commit_msg,
            tags={"claude_md_hash": content_hash, "git_sha": git_sha},
        )
        return prompt_name, pv.version
    except Exception:
        return None, None


def _write_sidecar(project_dir: str, session_id: str, env_data: dict):
    """Write environment snapshot to sidecar JSON."""
    mlflow_dir = os.path.join(project_dir, ".claude", "mlflow")
    os.makedirs(mlflow_dir, exist_ok=True)
    sidecar_path = os.path.join(mlflow_dir, f"env_{session_id}.json")

    env_data["session_id"] = session_id
    with open(sidecar_path, "w") as f:
        json.dump(env_data, f)


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
        session_id = hook_input.get("session_id", "unknown")
        project_dir = os.environ.get(
            "CLAUDE_PROJECT_DIR", hook_input.get("cwd", os.getcwd())
        )
        env_data = snapshot_environment(project_dir)
        _write_sidecar(project_dir, session_id, env_data)
    except Exception:
        pass
    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
