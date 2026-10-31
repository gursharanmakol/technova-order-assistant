# MCP Order Assistant Lab: Is Your Agent Actually Using MCP?

A customer asked TechNova's support assistant about their order and got a confident, specific answer that was wrong. The assistant gets order data from another team's service over MCP, and its trace shows a real MCP tool call that succeeded. Find out where the request left the path it should have taken, fix it without breaking a security requirement, and prove the fix with evidence and a regression test.

TechNova, its teams, and its order records are fictional, made up for this lab.

Set aside about an hour. Your time will vary with how familiar you are with Python projects, Git, and reading JSON.

## Who this is for

You should be comfortable working in a small Python project you did not write. That means opening files, reading short functions, running commands in a terminal, reading JSON output, and writing a basic `assert`. You should also be able to use Git and an editor or IDE.

You do **not** need MCP experience, an API key, an account, or any network access after setup. Knowing roughly what a "tool call" is helps, but the lab explains what you need.

## What you'll practice

This lab gives you practice checking an MCP integration from evidence instead of trusting the assistant's answer. You'll follow one request from the user's question to the final answer, ask for proof that each stage happened for the tool that matters, and locate the failure at the first stage with no proof.

You'll also see why "an MCP call happened" is not the same as "the answer is right". A tool call can succeed and still not support what the answer says.

## The system

The lab is a small working copy of TechNova's order assistant. It runs entirely on your machine.

| Part | Folder | What it does |
| --- | --- | --- |
| **Order service** | `order_service/` | The Orders team's MCP server. It owns the order records and offers tools for them. Other teams use it too, so what it advertises is its contract. |
| **Assistant (the Host)** | `assistant_host/` | Starts the order service, connects to it as an MCP client, asks which tools it has, passes tool descriptions to the model, runs the tool calls the model asks for, and returns the model's final answer. |
| **Model** | `assistant_host/model_standin.py` | A deterministic stand-in. See below. |

**The model is a stand-in, not an LLM.** Every run gives the same result on every machine, and there is no API key or cost. It follows a few simple rules, written at the top of `model_standin.py`. Like a real model, it never talks to MCP directly. It only sees what the Host gives it, and it may fill a gap with a confident guess. A real LLM might do the same, or might say it can't check. The method you practice here works either way. Every answer is labeled `(answered by scripted-stand-in: a deterministic simulated model, not an LLM)`.

The Host and the order service talk over stdio, using MCP protocol version `2026-07-28` and the official Python SDK (`mcp` 2.3.0). The messages you'll inspect are the real JSON-RPC messages they exchanged.

One question travels this path:

    user question
      -> Host asks the order service what it offers    (server/discover, tools/list)
      -> Host sends the question and tools to the model
      -> model picks a tool and arguments, or answers
      -> Host calls that tool on the order service      (tools/call)
      -> order service returns a result
      -> Host passes the result to the model
      -> model writes the final answer

## The six stages

To trust an answer that should come from a tool, you need proof of six things for that tool, in this order.

| Stage | Question | Where the evidence is |
| --- | --- | --- |
| 1. Discovery | Did the server advertise the tool? | The `tools/list` result |
| 2. Host exposure | Was the model given the tool? | The Host's request to the model |
| 3. Model selection | Did the model choose it, with the right arguments? | The model's tool choice |
| 4. Invocation | Did a `tools/call` for it cross the wire, and did the server receive it? | The `tools/call` request, and the server's own log |
| 5. Returned result | Did that same call succeed with structured data? | The response with the same id: `isError` and `structuredContent` |
| 6. Grounding | Does the answer say what the result said? | The final answer, compared with that `structuredContent` |

Check them in order, for the tool that matters, and stop at the first stage you cannot prove. Any stage can be the one that fails. Proof at one stage says nothing about the next one.

## Your assignment

**Ticket SUP-2291**

> A customer asked the assistant about order ORD-10042 and was told it is still being prepared. The customer received a FedEx shipping email two days ago. The order system shows the order shipped. Find out why the assistant answered the way it did, fix it, and prove the fix. Security review SEC-142 requires that the assistant can never cancel orders.

1. **Reproduce.** Run `ask` with the customer's question.
2. **Investigate.** Use `trace`, `show`, and `server-log` to walk the six stages for the tool that should have answered.
3. **Write up what you found.** Fill in sections 1 to 4 of `INCIDENT_REPORT.md`.
4. **Write the regression test.** Complete the TODOs in `tests/test_order_status_evidence.py` and run `test`. The tests must fail.
5. **Fix it.** Make the smallest change that fixes the cause.
6. **Prove it.** Run `test` again. Both tests must pass. Then run `ask` and `trace` again.
7. **Finish the write-up.** Fill in sections 5 to 8 of `INCIDENT_REPORT.md`.

Rules:
- Don't edit the worked-example assertion in the test file.
- Don't change what the order service advertises. Other teams depend on it.
- The assistant must still never be able to cancel an order.

**What you'll have when you're done**

- `INCIDENT_REPORT.md` filled in, citing event numbers from before and after your fix
- a completed regression test that failed before your change and passes after it
- a small change
- an `ask` answer that matches the order service's record, with a `trace` that shows where it came from

## Reading the evidence

| Command | What it shows |
| --- | --- |
| `uv run python lab.py check` | Your Python and `mcp` versions, and whether the lab loads. Ends with `Ready.` |
| `uv run python lab.py ask "What is the status of order ORD-10042?"` | The assistant's answer. Saves this run for the commands below. |
| `uv run python lab.py trace` | A numbered list of every event in the last run |
| `uv run python lab.py show 4` | The full content of event 4 |
| `uv run python lab.py show 4 --brief` | The same, with each JSON schema shown as `{...}` |
| `uv run python lab.py server-log` | The order service's own log of the requests it received in the last run |
| `uv run python lab.py test` | Runs your regression test in `tests/` |

How to read them:

- **`trace`** numbers events in the order they happened in the last `ask`. The `from -> to` column names the two parties: `host`, `server`, or `model`. Events between `host` and `server` are MCP messages. Events between `host` and `model` are what the Host gave the model and what the model returned.
- **`show <n>`** prints one event in full. For an MCP event, that is the exact JSON-RPC message. The trace only labels events, so open them with `show` to see what they contain.
- **`--brief`** replaces each JSON schema with `{...}`, which makes long messages easier to read. Nothing else changes. Leave it off when you want the schemas.
- **Request ids.** Every JSON-RPC request carries an `id`, and its response carries the same `id`. That is how you match a result to the request that asked for it. Ids are counted per run, so match by id instead of memorizing numbers.
- **`server-log`** is written by the order service process itself, not by the Host. It's a second witness. Each line reads `received <method> [name=<tool>] id=<id>`, and the ids match the ones on the wire.
- **Each `ask` replaces the saved run.** After you change anything, run `ask` again before you look at `trace`. The saved run lives in `traces/`, which Git ignores.

## The regression test

`tests/test_order_status_evidence.py` has two tests. Each starts with `run = run_ask(QUESTION)`, which asks the real assistant the customer's question, exactly like `ask`. It then gives you what was observed at each stage. The fields are listed at the top of the file, and `lab_support/evidence.py` explains each one.

- The first test proves the status answer is backed by a real tool call. Its first assertion, a worked example for discovery, is already written. TODOs 1 to 3 cover the other five stages.
- The second test proves the assistant still can't cancel orders. TODO 4 covers it.

Write your assertions under the TODOs, then delete the `pytest.fail(...)` line in each test. Run them with:

    uv run python lab.py test

The tests start the real order service, so each one takes a few seconds.

Write the test after you investigate and before you fix anything. Running it on the code as shipped must fail, and after your fix both tests must pass. Compare the answer against the tool result in `run`, not against text you typed in. That way the test still means something if the data changes.

## The incident report

`INCIDENT_REPORT.md` asks eight short questions. Answer them with event numbers from `trace` and lines from `server-log`. Write sections 1 to 4 before your fix and sections 5 to 8 after it. About half a page is enough.

When you're done, send in your work as described in the instructions you were given.

## Where things are

| Path | What it is |
| --- | --- |
| `lab.py` | The command-line tool you run |
| `order_service/server.py` | The Orders team's MCP server and its tools |
| `order_service/store.py` | The order records the server reads |
| `assistant_host/host.py` | The assistant: MCP client, model loop, and answer |
| `assistant_host/host.toml` | The assistant's settings |
| `assistant_host/model_standin.py` | The deterministic stand-in model and its rules |
| `assistant_host/model_api.py` | The messages passed between the Host and the model |
| `lab_support/` | Records and displays each run: the message tap, the timeline, and the evidence for tests |
| `tests/test_order_status_evidence.py` | The regression test you complete |
| `INCIDENT_REPORT.md` | Where you write your findings |
| `HINTS.md` | Three hints, one step at a time |

## What you'll need

- **Python 3.12 or newer** (tested on CPython 3.12.9 and 3.13)
- **Git** to clone the lab repository
- **A terminal** to run the lab commands (PowerShell, Terminal, or your editor's built-in terminal)
- **An editor or IDE** to read and change the code

`uv` is the recommended and tested way to run the lab. It can install Python for you. If you'd rather not use uv, you can use pip with a virtual environment instead. The setup steps below show both.

## Using AI tools

You may use AI for incidental technical help: setup problems, terminal or path issues, Python or pytest syntax, understanding an error message, or editor usage.

Please do not use AI for the diagnosis or the assertions. Prompts like "Why is this assistant giving the wrong status?", "What should I change?", or "Write the TODOs in this test" remove the reasoning this lab is meant to practice.

## Setup

### 1. Check your tools

**Recommended (uv):**

```bash
git --version
uv --version
```

If both commands print a version, continue to step 2. You do not need to install Python yourself when using uv.

<details>
<summary>Need to install Git or uv?</summary>

Git: https://git-scm.com/downloads

uv for Windows PowerShell:

```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

uv for macOS or Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen your terminal after installing uv. Then run the version checks again.

</details>

**Alternative (pip and a virtual environment):**

On Windows:

```powershell
git --version
python --version
```

On macOS or Linux:

```bash
git --version
python3 --version
```

Confirm Python reports 3.12 or newer, then continue. On Windows, if `python` is not found, try `py --version`.

### 2. Get the lab and check it

**Recommended (uv):**

```bash
git clone https://github.com/gursharanmakol/technova-order-assistant.git
cd technova-order-assistant
uv run python lab.py check
```

The first run may take a minute or two while uv prepares Python and the dependencies. You're ready when the last line starts with `Ready.`

**Alternative (pip and a virtual environment):**

Clone the lab:

```bash
git clone https://github.com/gursharanmakol/technova-order-assistant.git
cd technova-order-assistant
```

Then create a virtual environment (a `.venv` folder that holds this lab's packages), activate it, install the dependencies, and check the lab. Run these in the lab folder, where the `cd` command above left you.

On Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python lab.py check
```

- If PowerShell says running scripts is disabled, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then run the `Activate.ps1` line again. That setting lasts only for the current terminal window.
- In Command Prompt instead of PowerShell, activate with `.venv\Scripts\activate.bat`.
- If `python` is not found, use `py -m venv .venv` for the first line.

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python lab.py check
```

While the environment is active, your prompt starts with `(.venv)`. Each time you open a new terminal, run the activate line again before you use the lab.

With pip, drop `uv run` from every command in this README and use `python lab.py ...`. For example: `python lab.py ask "What is the status of order ORD-10042?"`.

If you already use Conda or an IDE interpreter, select a Python 3.12 or newer environment, run `python -m pip install -r requirements.txt` in this folder, then `python lab.py check`.

If `check` still does not pass after about 15 minutes, pause and re-check the Python version, Git, and install steps above before continuing.

## If you get stuck

Open `HINTS.md` and read one hint at a time. Each hint narrows the search a little more.

## After you finish

<details>
<summary>Reflection questions</summary>

1. The trace showed a `tools/call` that succeeded. Why wasn't that enough to trust the answer?
2. Which part of the answer was backed by a tool result, and which part wasn't?
3. What other fix might have made your status test pass, and which test or evidence would have caught it?

</details>

<details>
<summary>Pattern to remember after you finish</summary>

When an assistant's answer should come from a tool, work through these steps.

1. Decide which tool should have produced the answer.
2. Find that tool in the server's `tools/list` result.
3. Check that the model was given it.
4. Check that the model chose it, with the right arguments.
5. Find the `tools/call` for it on the wire, and the same request in the server's own log.
6. Find the response with the same id. Did it succeed, and what did it return?
7. Compare the answer with that result, claim by claim.
8. Stop at the first stage you can't prove. That's where to look for the cause. Change only what the evidence points to, and keep the security requirement intact.

</details>

## Optional follow-up reading

This lab practices the request flow from the AI in Practice Hub MCP series. [What MCP Is and How AI Agents Connect](https://aiinpracticehub.com/articles/what-mcp-is-how-ai-agents-connect-to-real-systems/) (Part 2) covers the Host, the Client, the Server, and tools. [How MCP Works: The Complete Request Flow](https://aiinpracticehub.com/articles/how-mcp-works-the-complete-request-flow/) (Part 3) walks the same messages you just inspected.

## License

Code and lab content: MIT. See `LICENSE`.

Dependencies are installed during setup and keep their own licenses. See `THIRD_PARTY_NOTICES.md`.
