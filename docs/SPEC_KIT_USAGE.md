# How We Use Spec Kit in Meme-Stocks

This repo uses [GitHub Spec Kit](https://github.com/github/spec-kit) for spec-driven development on top of the existing workflow. Specs complement (do not replace) ROADMAP, PRD, and ARCHITECTURE.

## Quick Reference: Commands in Cursor

| Command | Purpose |
|---------|---------|
| `/speckit.constitution` | Create or update project principles |
| `/speckit.specify <description>` | Create a new feature spec (creates branch + spec dir) |
| `/speckit.plan` | Generate technical plan for current spec |
| `/speckit.tasks` | Generate implementation tasks |
| `/speckit.implement` | Execute tasks (requires plan + tasks) |
| `/speckit.clarify` | Ask structured questions before planning (optional) |
| `/speckit.analyze` | Cross-artifact consistency check (optional) |
| `/speckit.checklist` | Quality checklist for spec (optional) |

## Workflow: Adding a New Feature

1. **Align with ROADMAP**
   Check `docs/ROADMAP.md` for current phase and task. Update ROADMAP if adding net-new work.

2. **Create the spec** (creates branch + `specs/###-short-name/spec.md`):
   ```
   /speckit.specify Add dashboard auto-refresh at 60-second interval; pause when tab hidden
   ```
   Or create the spec directory and files manually (brownfield option).

3. **Create the plan** (from project root, on the feature branch or with `SPECIFY_FEATURE` set):
   ```
   /speckit.plan
   ```

4. **Generate tasks**:
   ```
   /speckit.tasks
   ```

5. **Implement**:
   ```
   /speckit.implement
   ```
   Or implement manually, following the tasks. Run `./scripts/verify.sh` before done.

## Brownfield: Working Without Branch Switching

If you want to work on a spec without switching branches:

```bash
export SPECIFY_FEATURE=001-dashboard-auto-refresh
```

Then run `/speckit.plan`, `/speckit.tasks`, or `/speckit.implement`. The scripts resolve the spec directory from `SPECIFY_FEATURE`.

## Structure

```
.specify/
├── memory/
│   └── constitution.md    # Project principles
├── templates/             # Spec, plan, tasks templates
└── scripts/              # create-new-feature, check-prerequisites

specs/
├── 001-dashboard-auto-refresh/   # Pilot spec
│   ├── spec.md
│   ├── plan.md
│   └── tasks.md
└── ...

.cursor/commands/         # speckit.* slash commands
```

## Constitution

`.specify/memory/constitution.md` defines principles tailored for meme-stocks:

- Roadmap alignment
- Explicit failures over silence
- Test discipline
- Skepticism and honest reporting
- Reliability and observability
- No look-ahead bias in research
- Incremental delivery

These complement `.cursorrules` and `.cursor/rules/`.

## First-Time Setup (Already Done)

Spec Kit was initialized with:

```bash
uvx --from "git+https://github.com/github/spec-kit.git" specify init --here --ai cursor-agent --ignore-agent-tools
```

For persistent use:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
```

## References

- `docs/BROWNFIELD_SPEC_KIT.md` — Context for AI agents writing specs
- `docs/ROADMAP.md` — Current phase and tasks
- `docs/ARCHITECTURE.md` — Implementation patterns
