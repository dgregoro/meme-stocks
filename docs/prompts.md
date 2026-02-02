# Agent Prompt Templates

Reference this file in Cursor chat with `@docs/prompts.md` then say which template to use.

---

## Template: Implement Feature

```
Implement the following feature:

[DESCRIBE FEATURE HERE]

Instructions:
1. Read ARCHITECTURE.md for patterns to follow
2. Create files in order: Model → Repository → Service → API Route → Tests
3. Follow .cursorrules guidelines
4. Run ./scripts/verify.sh before reporting completion
5. Report: what was created, what tests were added, verification results
```

---

## Template: Add API Endpoint

```
Add a new API endpoint:

Endpoint: [METHOD] /api/[path]
Purpose: [what it does]
Request body: [if POST/PUT]
Response: [expected shape]

Follow ARCHITECTURE.md "Adding an API Route" pattern.
Run ./scripts/verify.sh when done.
```

---

## Template: Fix Bug

```
Fix this bug:

Problem: [describe the bug]
Expected: [what should happen]
Actual: [what happens instead]
Location: [file or area if known]

Instructions:
1. Investigate the issue
2. Propose a fix
3. Add a test that would have caught this bug
4. Run ./scripts/verify.sh
```

---

## Template: Add Background Job

```
Add a new background job:

Job name: [name]
Purpose: [what it does]
Schedule: [how often]
Idempotent: Must be safe to run multiple times

Follow ARCHITECTURE.md "Adding a New Background Job" pattern.
Add to scheduler_service.py.
Run ./scripts/verify.sh when done.
```

---

## Template: Roadmap Task

```
Execute ROADMAP.md Phase [N], Task [X].

Instructions:
1. Read the task description in ROADMAP.md
2. Follow ARCHITECTURE.md patterns
3. Run ./scripts/verify.sh when done
4. Update ROADMAP.md to mark task complete
5. Report what was done and verification results
```

---

## Template: Quick Task

```
[DESCRIBE TASK]

Follow project conventions in .cursorrules and ARCHITECTURE.md.
Run ./scripts/verify.sh when done.
```
