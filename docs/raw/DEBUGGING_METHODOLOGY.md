# Debugging Methodology

General-purpose debugging principles extracted from real incidents.
Not specific to CODESYS — applicable to any multi-layer system.

Primary case study: [BUG_HTTP_LIFECYCLE_STALL.md](BUG_HTTP_LIFECYCLE_STALL.md)
(HTTP server stops responding after 7 CODESYS lifecycle cycles; root cause was
`sys.stderr.write()` backpressure from Python stdlib's `BaseHTTPRequestHandler`).

---

## 1. Layer Isolation Protocol

**The single most effective technique in the entire investigation.**

When a system has layers (HTTP → service logic → process manager → OS), don't
debug from the top. Build standalone probes that test each layer in isolation,
starting from the bottom:

```
Probe 1: OS/process layer only           → PASS → cleared
Probe 2: + service logic                  → FAIL → bug is HERE or below
  (fix, re-run)                           → PASS → cleared
Probe 3: + HTTP layer                     → FAIL → bug is in HTTP layer
```

A probe that passes **definitively clears that layer and everything below it**.
A probe that fails **localizes the fault to at most that layer**.

### How to build a good isolation probe

- Bypass the layer above: call the API directly, not through the server
- Use the same config and parameters as the failing test
- Run at least as many iterations as the failing test
- Log enough to confirm the probe is actually exercising the same code paths
- Validate the probe itself before trusting its results

### What makes this better than printf debugging

Printf debugging narrows incrementally — each run eliminates one line.
Layer isolation eliminates an entire layer per run. With 4 layers, you need at
most 4 probe runs to identify which layer owns the fault. This is O(layers)
instead of O(lines of code).

---

## 2. The "N Iterations Then Fail" Pattern

When something works for N iterations and then fails, the cause is almost always
**resource accumulation**. Something grows by a fixed amount per iteration until
it hits a system limit.

### Systematic approach

1. **List every resource that could accumulate per iteration:**
   - pipe/socket buffer bytes written but not read
   - threads created but not joined
   - file descriptors opened but not closed
   - process handles not released
   - memory allocated but not freed
   - log/temp files growing without bound

2. **For each candidate, calculate:**
   - growth per iteration (bytes, count, handles)
   - system limit (buffer size, max fd, max threads)
   - expected failure point: limit / growth = N

3. **Compare N to the observed failure iteration.**
   If they match, you've found it.

### Example from this project

- Each HTTP request triggered `sys.stderr.write()` via `BaseHTTPRequestHandler.send_response()`
- The server was started with `stderr=PIPE` and nobody consumed the pipe
- Windows anonymous pipe buffer: ~4 KB
- Each access log line: ~100 bytes
- 8 lifecycle cycles x ~5-6 requests/cycle = ~40-48 writes
- 48 x 100 bytes = ~4800 bytes > 4096 byte buffer
- **Predicted failure: around cycle 7. Observed failure: cycle 7.**

If we had done this calculation on day 1, we would have found the root cause in
hours instead of days.

---

## 3. Framework Blind Spot

**The lesson that cost the most time.**

When debugging, there is a natural tendency to only analyze YOUR code and treat
framework/stdlib code as a black box. This creates a blind spot at the boundary
where your code calls the framework.

### What happened

We traced from `send_json_response()` → `self.send_response(status)` and stopped.
`send_response` is a stdlib method — we assumed it just writes headers.

But `send_response()` internally calls:
```
send_response()
  → log_request()
    → log_message()
      → sys.stderr.write()   ← the actual blocking call
```

Nobody looked inside `send_response()`. The root cause was three frames deep
in stdlib code that we never read.

### The rule

**When you narrow a bug to "somewhere in function X", trace the ENTIRE call
tree of X — including every framework/stdlib call — until you reach a syscall
or I/O operation.** Every I/O operation is a candidate for blocking.

Concretely:
- `wfile.write()` → socket send → I/O (we checked this)
- `send_response()` → `log_message()` → `sys.stderr.write()` → pipe write → I/O (**we missed this**)

The search must cover ALL I/O paths, not just the ones in your own code.

### How to do this efficiently

You don't need to read the entire stdlib. Instead:

1. Identify the region where the stall occurs (via layer isolation + log analysis)
2. List every function call in that region, including framework calls
3. For each framework call, ask: **does this do I/O?**
4. Check the source code (not the docs) for any call you're not 100% sure about
5. `python -c "import inspect, http.server; print(inspect.getsource(http.server.BaseHTTPRequestHandler.send_response))"` — one line to read any stdlib function

---

## 4. The Two-Bug Trap

**Fixing a real bug that isn't THE bug.**

During this investigation, we found and fixed a genuine bug: `process.terminate()`
only killed `cmd.exe` but not the CODESYS child processes (orphan processes on
Windows). This was a real defect — the layer-isolation probe failed because of it.

After fixing it, the probe passed 12 cycles. We thought we were done.

But the HTTP test still failed.

The orphan process bug was real. It was worth fixing. But it was **not the root
cause of the HTTP stall**. We had two independent bugs:

| Bug | Layer | Effect |
|---|---|---|
| Orphan CODESYS processes | Process manager | Probe fails at cycle 1 |
| stderr pipe backpressure | HTTP server | HTTP test fails at cycle 7 |

### The rule

**After fixing a bug, always re-run the original failing test, not just the
isolation probe.** The probe can pass because you fixed a real bug at a lower
layer, while the original failure persists at a higher layer.

If the original test still fails after your fix, you have at least two bugs.
Don't celebrate until the original test is green.

---

## 5. When to Change Strategy

We spent significant time on static analysis of our code — examining `wfile.write()`,
keep-alive semantics, socket buffer states, GIL contention, thread scheduling.
All of these turned out to be wrong.

### Signs that static analysis has hit diminishing returns

- You're on your third hypothesis about the same 10 lines of code
- Your hypotheses are getting more exotic (GIL contention, OS kernel behavior)
- You can't construct a concrete mechanism — just "maybe it could..."
- You've been staring at the same code for >2 hours without new insight

### What to do instead

1. **Add instrumentation, don't speculate.** Two log lines (`enter` + `done`)
   around `send_json_response` would have immediately shown whether the stall
   was inside or after it.

2. **Trace into framework code.** Read `send_response()` source. Read
   `handle_one_request()` source. 5 minutes of reading stdlib would have found
   `sys.stderr.write()`.

3. **Use a different tool.** We used Codex after getting stuck. It found the
   root cause by mechanically tracing the entire call chain — something a human
   tends to shortcut. Process debuggers, strace/procmon, `py-spy`, or even a
   fresh pair of eyes can break the analysis rut.

4. **Calculate, don't guess.** For accumulation bugs, the arithmetic (resource
   per iteration x iterations = limit?) is more reliable than reasoning about
   code behavior.

---

## 6. The "What's Different" Checklist

When test A passes and test B fails, the cause is in the **difference** between
A and B. But the difference list must be exhaustive.

### Common mistake: only listing your own code differences

We listed:
- Probe doesn't call `is_running()` between cycles ← checked, not the cause
- Probe doesn't use HTTP connections ← too vague
- Probe doesn't have `BaseHTTPRequestHandler` ← correct but didn't follow through

We missed:
- **Probe doesn't write to `sys.stderr` 50+ times** ← the actual cause

### The complete checklist

When comparing a passing context to a failing one, ask:

1. What code runs in B that doesn't run in A? **(including framework code)**
2. What I/O operations happen in B that don't happen in A? **(including logging)**
3. What resources are created in B that aren't in A? **(including implicit ones like pipe buffers)**
4. How was the process started differently? **(env vars, pipes, working dir, user)**
5. What accumulates in B across iterations that doesn't in A?

Item 4 is particularly insidious. The HTTP server was started with
`stderr=subprocess.PIPE` in the test fixture. The probe ran in the test process
itself (no pipe). This deployment difference — not a code difference — was the
root cause.

---

## Summary of Techniques by Effectiveness

| Technique | When to use | Effectiveness in this case |
|---|---|---|
| Layer isolation probes | First step for any multi-layer bug | Cleared 2 of 3 layers definitively |
| Accumulation arithmetic | "Works N times then fails" pattern | Would have found root cause on day 1 |
| Framework source reading | After narrowing to a region | Would have found root cause in 5 min |
| Targeted instrumentation | After layer isolation narrows scope | 2 log lines would have confirmed location |
| Static analysis of own code | Initial orientation | Useful early, diminishing returns fast |
| Exotic hypotheses | Never, unless you have evidence | All wrong, wasted time |

### The ideal order for this bug class

1. Layer isolation probe → identify which layer
2. Targeted instrumentation → identify which function
3. Accumulation arithmetic → calculate resource budget
4. Framework source reading → find the I/O call
5. Fix → verify with original test (not just probe)

---

## References

- [BUG_HTTP_LIFECYCLE_STALL.md](BUG_HTTP_LIFECYCLE_STALL.md) — full incident report
- [REAL_CODESYS_LESSONS.md](REAL_CODESYS_LESSONS.md) — CODESYS-specific debugging lessons
- Python docs: [subprocess — Frequently Used Arguments](https://docs.python.org/3/library/subprocess.html#frequently-used-arguments) — pipe deadlock warning
- Python source: `Lib/http/server.py` — `send_response()` calls `log_request()` calls `log_message()` calls `sys.stderr.write()`
