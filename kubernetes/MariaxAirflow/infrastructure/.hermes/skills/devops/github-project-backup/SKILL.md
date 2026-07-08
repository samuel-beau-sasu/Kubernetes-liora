---
name: github-project-backup
description: Strategy for backing up specific project files and AI agent persistence to GitHub while minimizing repository size and avoiding noise.
---

# GitHub Project Backup & Agent Persistence

This skill governs the process of selectively backing up a working directory to GitHub, ensuring that only essential configuration files, documentation, and AI agent state (knowledge/memory) are preserved.

## Trigger Conditions
- User wants to push a project to GitHub but is concerned about "memory" (storage/repo size).
- Need to backup an AI agent's learned experience (skills, memories, state) to allow restoration on another machine.
- Project contains heavy directories (node_modules, venv, .cache, logs) that must be excluded.

## Procedural Workflow

### 1. Analysis & Filtering
- **Identify Noise:** Scan the directory for hidden folders (`.*`) and known heavy directories (`venv`, `__pycache__`, `logs`).
- **Identify Core Assets:**
    - Configs: `.yaml`, `.yml`, `.json`.
    - Logic: `.py`, `.sh`, `.bash`.
    - Docs: `.md`.
- **Identify Agent State:** Specifically target the agent's persistence layer (e.g., `.hermes/skills/`, `.hermes/memories/`, `.hermes/state.db`).

### 2. Exclusion Setup (.gitignore)
Create a `.gitignore` that targets categories of noise rather than individual files:
- System/IDE noise (`.vscode-server/`, `.copilot/`, `__pycache__/`).
- Python environments (`venv/`).
- Agent transient data (`.hermes/logs/`, `.hermes/cache/`, `state.db-wal`).
- Application logs (`**/logs/`, `*.log`).

### 3. Selective Staging & Index Cleanup
Instead of `git add .` (which can timeout or include unwanted files in large directories), use targeted additions:
- `git add .gitignore`
- `git add path/to/agent/persistence/`
- `git add "*.yml" "*.yaml" "*.md" "*.sh" "*.py"`

**Crucial: Cleaning the Index**
If `git add .` was previously run and noise files were accidentally tracked (even after adding a `.gitignore`), they will continue to be staged. To fix this, clear the index and re-stage:
- `git rm -r --cached .` (Removes everything from the index without deleting files from disk)
- `git add .` (Re-indexes files according to the current `.gitignore`)
- `git commit --amend` (Updates the previous commit to remove the noise)


### 4. Commit and Push
- Commit with a descriptive message (e.g., "Backup: [Project Name] and Agent Knowledge").
- Push to the remote origin.

**Pitfall: GitHub File Size Limit (100MB)**
If a push is rejected with `remote: error: File ... exceeds GitHub's file size limit of 100.00 MB`, it means a large file was committed *before* the `.gitignore` was effective or was added manually.
- **Symptom:** `pre-receive hook declined` or `GH001: Large files detected`.\n- **Fix:** You must rewrite the local history to remove the file from the commit history entirely.\n  - `git reset --hard HEAD` (or back to the last known good commit).\n  - `git rm -r --cached .` to clear the index.\n  - `git add .` (ensure `.gitignore` is correct).\n  - Create a new, clean commit.\n  - `git push origin master --force` to overwrite the problematic remote state.\n\n**Caution: The `git add .` Re-indexing Trap**\nEven after a cleanup, running `git add .` can accidentally re-stage hidden system files (e.g., `.vscode-server/`) if the `.gitignore` is not explicit enough or if the files are located in directories not covered by the patterns. This can re-introduce the 100MB limit error.\n- **Fix:** Combine `git rm -r --cached .` with an explicit check of `git status` before the final commit to ensure no high-volume system paths are listed as \"new files\".\n\n**Network Stability & Timeouts**\nIf `git push` fails with `HTTP 408` or `unexpected disconnect` despite a small payload:\n- **Increase Buffer:** `git config --global http.postBuffer 524288000` (500MB).\n- **Disable Compression:** `git config --global core.compression 0`.\n- **Background Execution:** For large pushes, use background processes to avoid interface timeouts.

## Pitfalls & Lessons
- **The `git add .` Timeout:** In environments with massive hidden caches (e.g., `.npm`, `.cache`), `git add .` may timeout. Always prioritize selective `git add` for targeted backups.
- **Agent State Recovery:** To successfully migrate an agent's "mind," you must save the skills and memories folders AND the primary state database (`state.db`), but exclude the write-ahead logs (`-wal`) and shared memory files (`-shm`) as they are transient.
- **Authentication Failures (HTTP vs SSH):** If `git push` fails with `fatal: could not read Username`, it's usually due to a missing or expired Personal Access Token (PAT) when using HTTPS. 
    - *Fix 1 (Manual):* Use a PAT as the password or embed it in the URL: `https://<TOKEN>@github.com/user/repo.git`.
    - *Fix 2 (Modern):* Use the GitHub CLI (`gh auth login`) to automate credential management via OAuth. This is the preferred method for AI agents to maintain stable connectivity.

## Verification
- Run `git status` after staging to verify no "noise" files (like venv or logs) were accidentally tracked.
- Confirm the presence of key persistence files in the commit.
