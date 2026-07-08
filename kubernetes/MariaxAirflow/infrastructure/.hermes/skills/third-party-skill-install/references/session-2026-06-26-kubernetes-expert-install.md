# Session transcript: `skills-sh/personamanagmentlayer/pcl/kubernetes-expert`

Date: 2026-06-26
Host: /home/ubuntu (Linux 6.17.0-1017-aws)
Context: user asked to install this third-party skill; outcome was a phantom
quarantine (no files on disk) and a blocked index scan.

This file is **session-specific detail** — concrete commands, exact log
output, and what we found. The general lesson is in SKILL.md; the recipe
to reproduce the verification is here.

---

## 1. Exact CLI output from the install attempt

Command:

```
hermes skills install skills-sh/personamanagmentlayer/pcl/kubernetes-expert
```

Output:

```
Fetching: skills-sh/personamanagmentlayer/pcl/kubernetes-expert
Quarantined to .hub/quarantine/kubernetes-expert
Running security scan...
Scan: kubernetes-expert
(skills-sh/personamanagmentlayer/pcl/kubernetes-expert/community)  Verdict: SAFE
  LOW      privilege_escalation SKILL.md:15                    "allowed-tools:"

Decision: ALLOWED — Allowed (community source, safe verdict)

╭───────────────────────────── Upstream Metadata ──────────────────────────────╮
│ Repo: https://github.com/personamanagmentlayer/pcl                           │
│ Detail Page: https://skills.sh/personamanagmentlayer/pcl/kubernetes-expert   │
╰──────────────────────────────────────────────────────────────────────────────╯

╭───────────────────────────────── Disclaimer ─────────────────────────────────╮
│ You are installing a third-party skill at your own risk.                     │
│                                                                              │
│ External skills can contain instructions that influence agent behavior,      │
│ shell commands, and scripts. Even after automated scanning, you should       │
│ review the installed files before use.                                       │
│                                                                              │
│ Files will be at: ~/.hermes/skills/kubernetes-expert/                        │
╰──────────────────────────────────────────────────────────────────────────────╯
Install 'kubernetes-expert'?
Confirm [y/N]: Installation cancelled.
```

Exit code: 0. The "Installation cancelled" is just the no-input timeout —
not a fetch failure (necessarily).

## 2. Quarantine check — phantom quarantine

The CLI claimed `Quarantined to .hub/quarantine/kubernetes-expert`, but:

```
$ ls -la /home/ubuntu/.hub/quarantine/kubernetes-expert/
ls: cannot access '/home/ubuntu/.hub/quarantine/kubernetes-expert/': No such file or directory

$ ls -la /home/ubuntu/.hermes/skills/.hub/quarantine/
total 8
drwxrwxr-x 2 ubuntu ubuntu 4096 Jun 26 15:30 .
drwxrwxr-x 4 ubuntu ubuntu 4096 Jun 26 15:30 ..
```

Empty. The fetch silently failed — almost certainly 404 on the upstream
GitHub repo `personamanagmentlayer/pcl` (which is not a known public
namespace).

## 3. Hub state at the time

```
/home/ubuntu/.hermes/skills/.hub/
├── audit.log         (0 bytes — empty)
├── index-cache/
│   └── hermes-index.json   (39,403,796 bytes — ~40 MB)
├── lock.json         {"version": 1, "installed": {}}
├── taps.json         {"taps": []}
└── quarantine/       (empty)
```

`lock.json` shows nothing installed, `taps.json` shows no custom sources
added. The index cache is the only populated file in `.hub/`.

## 4. The blocked index scan

Trying to inspect the index from `execute_code`:

```python
import json
with open('/home/ubuntu/.hermes/skills/.hub/index-cache/hermes-index.json') as f:
    idx = json.load(f)
```

Result:

```
BLOCKED: User denied this command. The user has NOT consented to this
action. Do NOT retry this command, do NOT rephrase it, and do NOT attempt
the same outcome via a different command. Stop the current workflow and
wait for the user to respond before taking any further destructive or
irreversible action.
```

Tirih blocked the bulk-read of a 40 MB file via the Python execute_code
sandbox. Correct behavior — that path looks like an exfiltration pattern.

**Lesson:** don't try to bulk-search `hermes-index.json` from
`execute_code`. Use `hermes skills search <query>` or
`hermes skills browse` from the terminal instead.

## 5. Recommended next steps for this specific case

If the user re-asks to install this skill:

1. First confirm the upstream URL is real — visit
   https://github.com/personamanagmentlayer/pcl directly and verify
   the skill path exists.
2. If not, suggest an alternative well-known Kubernetes skill (none
   bundled today) or pivot to writing the playbook content as a
   `references/` file under this skill or as a new umbrella.
3. If yes, re-run the install and have the user confirm at the y/N
   prompt directly (TTY), so the disclaimer is read by a human.

## 6. What we did instead

The user pivoted to wanting general Kubernetes reference content. We
wrote a single-file playbook to `/home/ubuntu/kubernetes-playbook.md`
covering ops courantes, déploiement/infra, and CI/CD & ops. That file
is **not** in the skill library — it's a user-owned markdown file. If
they later want it as a skill, the natural home would be a new
`kubernetes` umbrella or as `references/playbook.md` under
`third-party-skill-install` (less appropriate — wrong class).