---
summary: "CLI reference for `juno docs` (search the live docs index)"
read_when:
  - You want to search the live Juno docs from the terminal
title: "docs"
---

# `juno docs`

Search the live docs index.

Arguments:

- `[query...]`: search terms to send to the live docs index

Examples:

```bash
juno docs
juno docs browser existing-session
juno docs sandbox allowHostControl
juno docs gateway token secretref
```

Notes:

- With no query, `juno docs` opens the live docs search entrypoint.
- Multi-word queries are passed through as one search request.
