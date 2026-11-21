# Phase 2 design: an XBRL tool the model can call

Status: implemented (get_fact, get_ratio, the tool-use loop); measured in P2.6.

## Why

Phase 1 reads every figure from text. When the relevant passage is retrieved, the model reads
the right figure 97.8 % of the time; the wrong answers come from a neighbouring definition, a
table header lost by the chunking, or a sign read from parentheses. The figure already exists,
exact, in the SEC's XBRL data. Phase 2 lets the model ask for it instead of reading it.

## Architecture

```mermaid
flowchart LR
    Q[Question] --> M[LLM]
    M -->|text question| R[RAG, as in phase 1]
    M -->|numeric question| T["get_fact (Python, XBRL)"]
    T --> M
    R --> A[Answer]
    M --> A
```

- The model never sees the XBRL data. It sees the question, the tool description, and the
  values the code sends back
- Python fetches the figures and computes any ratio. The model never does arithmetic
- Text questions (risks, strategy) keep going through the RAG of phase 1

## The tool-use loop

The API is stateless: each call resends the whole conversation.

1. The code sends the question and the tool list (`tools`: name, description, JSON Schema of
   the arguments)
2. The model answers with a `tool_use` block (tool name, arguments it filled in, an `id`) and
   `stop_reason = "tool_use"`
3. The code runs the function with those arguments
4. The code appends the model's turn, then a `user` turn holding a `tool_result` block with the
   same `id`, and calls the API again
5. The loop stops when `stop_reason = "end_turn"`. `end_turn` means the model finished
   writing, not that the answer is right: the benchmark decides that

N calls leave 2N messages, and every call rereads the whole history, so each round costs more
than the previous one.

## Tool contract (decided 20 Nov.)

```
get_fact(company: str, concept: str, period_end: str = None, fiscal_year: int = None)
```

- `company` restricted to the 5 tickers of the corpus (`enum` in the schema)
- `concept` is a human label from `CONCEPTS` (`enum`), never an XBRL name: the model maps the
  wording of the question to a label, Python maps the label to its XBRL concepts and aliases
- The period is copied from the question, never converted: `period_end` when it gives a date,
  `fiscal_year` when it gives "fiscal N", in the company's own naming (Nvidia's fiscal 2025
  ends on 26 January 2025). Python resolves the other one from the corpus
- No period: the latest fiscal year present in FinAgent's data, always named in the result
  ("fiscal 2025, ended 2025-09-27, latest in FinAgent's data"), so a figure that a newer 10-K
  has replaced is dated, never presented as current. Both given and inconsistent: an error
  result saying so
- Unknown company, concept or year: return an explicit "not found" result (`is_error`), never
  raise, so the model can correct its arguments or say it does not have the figure
- At scale, `company` becomes free text resolved by one lookup function (SEC
  `company_tickers.json`) and the facts move to a database; nothing else changes

## Known traps

- One figure, several concepts: `Revenues` against
  `RevenueFromContractWithCustomerExcludingAssessedTax` depending on the company
- Fiscal year is not the calendar year (Apple closes at the end of September)
- Mapping the question's wording ("revenue", "total long-term debt") to the right concept is
  now the model's job: the held-out phrasing of phase 1 shows where this fails
- "Absent" is not always 0, and XBRL tags vary by company: hand-written aliases and caveats do
  not scale beyond a few companies

## Choices made

- Ratios: a second tool, `get_ratio(company, ratio, period)`, with every formula fixed and tested
  in Python (`ratios.py`). The model never does arithmetic: it names the ratio, Python reads the
  inputs with the same readers as `get_fact` and returns the ratio, its definition, its inputs and
  any caveat. 14 ratios: margins, FCF, ROE, ROIC, Du Pont, the working capital cycle, debt to
  equity, payout, effective tax rate. Balance sheets are averaged for ROE, ROIC and Du Pont
- Routing: no classifier. Every route is a tool and the model picks one; the RAG of phase 1 will
  become a third tool for text questions
- Absent facts: each label states whether absent means 0 (no commercial paper, no dividend,
  checked in the 10-K) or an error. Nvidia's 2026 current securities exist but are missing from
  `companyfacts` (custom concept): its 2026 ROIC fails rather than returning a wrong number

## Measure

Same benchmark as phase 1, same split, run once on the test set: accuracy with the tool against
the 93.8 % of phase 1. Both the tool and the answer key read XBRL, so the gain measures the
mapping from question to concept and fiscal year, not the reading of a figure.
