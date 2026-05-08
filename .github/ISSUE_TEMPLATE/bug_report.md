---
name: Bug report
about: Something is broken or behaves incorrectly
title: "[bug] "
labels: bug
---

## What happened

A clear description of the bug.

## Expected behavior

What you expected to happen instead.

## Reproduction

Steps to reproduce. The minimum useful info:

- Provider mix (e.g. 3 stubs, 1 anthropic, 1 openai)
- Turn count when the issue appeared
- Whether you were in stub mode or using real keys
- Operating system and how you ran it (docker compose / local backend / local frontend)

```
1. ...
2. ...
3. ...
```

## Logs / output

Paste the relevant excerpt from `thought_logs/*.jsonl`, the FastAPI traceback, or the browser console.

```
<paste here>
```

## Environment

- Project Darwin commit / version:
- Python version:
- Node version:
- Browser (if frontend bug):
