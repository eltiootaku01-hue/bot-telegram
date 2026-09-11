# Experiments

This directory is reserved for ideas, prototypes, integrations, and algorithms that are not yet trusted enough for the main bot runtime.

## Rules

- Nothing here is imported by `app/` unless explicitly promoted.
- Experimental code must include a short note explaining its purpose, risks, and what would make it production-ready.
- Prefer small, reversible experiments over replacing stable components.
- When an experiment proves useful, move the smallest proven part into `app/`, add tests, and remove or archive the prototype.

The goal is to let the bot learn from external patterns without destabilizing the working core.
