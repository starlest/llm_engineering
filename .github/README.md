# AI Engineering, Built Block by Block

My workspace for learning to build applications with large language models. I am working through one course and one book, and building one project alongside them, from October 2026 to January 2027.

## The project: a WWE history assistant

An assistant that answers questions about WWE history from a set of 103 documents, and names the file each answer comes from. It grows in ten blocks:

0. Set up the workspace and check my Python
1. Answer a question about one document
2. Add a chat UI, typed output and a tool
3. Compare a small open-source model with a frontier model
4. Write 20 to 30 test questions and measure two baselines
5. Retrieve the right passages and name the sources
6. Tune retrieval, one experiment at a time
7. Grow the set to 50 questions and grade with an AI judge
8. Hand the decisions to an agent, with an approval step
9. Ship it behind an API, with every score

Each block's code, results and notes live in its own folder under [`plan/`](https://github.com/starlest/llm_engineering/tree/main/plan).

## How I work

- **Course:** I type every lesson out in a notebook of my own, beside the course's notebook in `week1/` to `week8/`.
- **Book:** after each course week I read the matching chapter and write my takeaways in `plan/blockN/notes.md`.
- **Checks:** [`plan/check.py`](https://github.com/starlest/llm_engineering/blob/main/plan/check.py) tests each exercise and writes [`plan/status.json`](https://github.com/starlest/llm_engineering/blob/main/plan/status.json), so progress is measured rather than ticked by hand.

## Map of this repository

| Path | What it holds |
| --- | --- |
| `plan/` | My project, block by block |
| `plan/docs/` | The documents the assistant answers from |
| `week1/` to `week8/` | The course's notebooks, with mine beside them |
| `README.md` | The course's own README |

## Credits

- Course: the AI Engineer Core Track by Ed Donner. Its code is [ed-donner/llm_engineering](https://github.com/ed-donner/llm_engineering), released under the MIT License (see [LICENSE](https://github.com/starlest/llm_engineering/blob/main/LICENSE)). This repository started as a fork of it.
- Book: *AI Engineering* by Chip Huyen.
- The WWE documents are an unofficial study set, not affiliated with WWE. How they were made is in `plan/DOCUMENTS.md`.
