# Hints

Open one hint at a time. Try the next step on your own before you open the next hint.

<details>
<summary>Hint 1: Start from the answer, not the code</summary>

Read the assistant's answer as a list of separate claims: which products, what status, and when it ships. For each claim, find the tool result that contains it.

Run `trace` to see the events, then `show <n>` to open the ones that carry results. Add `--brief` if the schemas get in the way. A claim you can't find in any tool result came from somewhere else.

</details>

<details>
<summary>Hint 2: Walk the request path in order</summary>

Which tool would know an order's status? Open the server's `tools/list` result and read the tool descriptions.

Now follow that one tool through the six stages in the README, in order. For each stage, find the event that proves it happened for that tool. Seeing a `tools/call` isn't enough: check which tool it called and what came back. Use `server-log` to confirm what the server actually received.

Write down the last stage you can prove for that tool, and the first one you can't.

</details>

<details>
<summary>Hint 3: Compare two lists</summary>

Compare the tools the server advertised with the tools the model was given. If they differ, find what decides what the model is given, and check it against the names the server advertises today. `git log --stat` shows what each recent change touched.

Leave the server's advertised names alone, and keep the assistant unable to cancel orders. Before you change anything, complete your test and confirm it fails for the reason you found.

</details>
