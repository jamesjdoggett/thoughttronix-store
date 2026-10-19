---
name: implement
description: Implement one approved phase from a PRD and plan using feedback loops.
argument-hint: "@prd/<feature>.md @plans/<feature>.md implement phase <N>"
disable-model-invocation: true
---

# Implement

## 1. Understand the Phase

Read the referenced PRD and plan. Explore the codebase to understand the relevant files, patterns, and conventions. If the request does not identify a phase, ask which one.

Implement only that phase. Do not begin the next one.

## 2. Implement the Phase

Read and follow the TDD skill at .agents/skills/tdd/SKILL.md, including its required approval checkpoints. Use TDD for up to three important behaviors selected from the phase's acceptance criteria, or explain why none qualify.

Implement all remaining phase requirements using the project's normal development and testing process.

## 3. Run Feedback Loops

Run the full test suite, Ruff linting and formatting checks, and any other relevant project checks. Fix failures and repeat the checks until they pass.

Review the implementation against the phase's acceptance criteria and confirm that no requirements were missed.

## 4. Manual Verification

Explain how I can manually verify this phase in the browser, including numbered steps and expected results.

Stop and wait for my confirmation. Do not consider the phase complete or proceed to the final steps until I confirm that manual verification passed.

## 5. Finish the Phase

Update PROMPTS.md following its existing format and record the work completed during this session.

Commit the completed phase and push the commit to GitHub. Report the commit hash and push result.
