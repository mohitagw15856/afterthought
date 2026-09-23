# coach

```
afterthought coach interview [--answers FILE] [--name NAME]
afterthought coach plan [--days N] [--start DATE] [--dry-run] [--record] [--fixtures DIR]
afterthought coach today [--as-of DATE]
afterthought coach done <id | prefix | day> [--note ...] [--evidence PATH] [--as-of DATE]
afterthought coach skip <id | prefix | day> [--note ...]
afterthought coach status [--json]
```

An onboarding coach for someone new to working with AI. It never teaches in the abstract: every task uses the person's own documents, tools and worries.

## Interview

Eight questions: role, the three biggest weekly tasks, tools and file types, the task that takes too long, what they have tried with AI, what worries them, minutes per day, and the 30-day goal. Answers go to `coach/profile.json` and a readable `coach/profile.md` (origin: human, no block ids). `--answers` takes a JSON file keyed by question id for scripted use.

## Plan

One structured model call turns the profile into `N` daily tasks, each with a reusable skill label and a one-line reason. The plan is written to `coach/curriculum.json` and rendered to `coach/curriculum.md` as a checklist grouped by week. Every line ends in `^at-llm-<profile hash>-<day>`: the curriculum was proposed by a model from the profile, and the page's `sources` say so. The fixture key is the profile hash plus the day count, so re-planning an unchanged profile is free and changes nothing.

## Progress

`today` lists tasks whose day has arrived (from `--start`, or the day you first mark something) and are still open. `done` and `skip` update the item, its checkbox (`[x]` done, `[-]` skipped), the completion date, a note and an optional evidence path. `status` counts progress and lists the skills with at least one completed task.

## Feedback into the wiki

Every progress change, and the end of every `compile`, calls the sync:

- `coach/skills.md` lists each skill the person has shown, tagged `^at-system-<item id>` so the line traces to the task that proved it.
- The person's own page under `entities/people/` gets a managed `## Learned` section with the same lines. `compile` treats `Learned` as managed, so it survives re-compiles like `Facts`, `Related` and `Sources`.

That is how the wiki knows what the person has learned to do: not from a claim, but from a completed task with a date.
