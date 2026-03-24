---
name: quint-spec
description: Write, test, and model-check Quint formal specifications for code. Use when the user asks to create a Quint spec, formally verify logic, model-check state machines, or validate code correctness with Quint.
argument-hint: [description of what to specify]
allowed-tools: Read, Write, Edit, Bash(quint *), Bash(tail *), Bash(mkdir *), Glob, Grep
---

# Quint Specification Skill

Write Quint (quint-lang) formal specifications, run simulation tests, and model-check invariants with Apalache.

## Environment

- `quint` is installed at `/opt/homebrew/bin/quint` (v0.31.0+)
- Apalache is auto-downloaded by quint on first `quint verify` run
- Specs go in the `spec/` directory at the project root
- **Network access is required** for `quint test` (Rust evaluator) and `quint verify` (Apalache). Use `dangerouslyDisableSandbox: true` on these commands.

## Workflow

### 1. Read the code to specify

Read and understand the code before writing anything. Identify:
- The **state variables** (what changes over time)
- The **actions/transitions** (what causes state to change)
- The **invariants** (what must always be true)
- The **terminal states** (where the system stops)

### 2. Write the spec

Create a `.qnt` file in `spec/`. Follow this structure:

```quint
module my_spec {

  // ── Constants & pure helpers ──────────────────────────────
  pure val MAX_SOMETHING: int = 5
  pure def helperFn(n: int): int = { ... }

  // ── State variables ───────────────────────────────────────
  var phase: str
  var counter: int

  // ── Initial state ─────────────────────────────────────────
  action init = all {
    phase' = "idle",
    counter' = 0,
  }

  // ── Actions (state transitions) ───────────────────────────
  action doSomething = all {
    phase == "idle",           // guard
    phase' = "running",        // next state
    counter' = counter + 1,
  }

  // ── Stutter step (REQUIRED for model checking) ────────────
  action stutter = all {
    phase' = phase,
    counter' = counter,
  }

  // ── Step (non-deterministic choice) ───────────────────────
  action step = any {
    doSomething,
    stutter,      // prevents deadlock in terminal states
  }

  // ── Invariants ────────────────────────────────────────────
  val myInvariant: bool = { ... }
  val allInvariants: bool = and { myInvariant, ... }

  // ── Tests (deterministic traces) ──────────────────────────
  run myTest = {
    init.then(doSomething).then(all {
      assert(counter == 1),
      phase' = phase, counter' = counter, // frame: assign all vars
    })
  }
}
```

### 3. Run tests

```bash
quint test spec/my_spec.qnt
```

### 4. Model-check invariants

```bash
quint verify --invariant allInvariants spec/my_spec.qnt
```

## Critical Apalache Limitations (MUST follow)

These cause hard errors. Not warnings — the model checker will refuse to run.

### No variable-bound ranges in fold/map

Apalache cannot handle `x.to(stateVar).fold(...)` where the range bound is a state variable.

**WRONG** (will crash Apalache):
```quint
pure def pow(base: int, exp: int): int = {
  1.to(exp).fold(1, (acc, _) => acc * base)
}
// Used in an action:
totalDelay' = totalDelay + pow(2, retryIndex)
```

**RIGHT** — use pre-computed if/else lookup tables:
```quint
pure def delayFor(n: int): int = {
  if (n == 1) 2
  else if (n == 2) 4
  else if (n == 3) 8
  else if (n == 4) 16
  else 32
}
```

This applies everywhere: actions, invariants, any expression that Apalache evaluates symbolically. If a `fold`, `map`, or `to` range bound depends on a state variable, replace it with a concrete lookup.

### No primed variables (') in val definitions

Invariants (`val`) can only reference current-state variables. Using `phase'` (next-state) in a `val` is a parse error.

**WRONG:**
```quint
val noRetryAfterSuccess: bool = {
  phase == "success" implies phase' != "retrying"
}
```

**RIGHT** — enforce this structurally via action guards instead. If an action should be impossible in a given state, make the guard exclude it.

### Deadlock on terminal states

Apalache reports "deadlock" when no transition is enabled. Terminal states (success, failure) naturally have no outgoing transitions.

**FIX** — always include a stutter step:
```quint
action stutter = all {
  phase' = phase,
  counter' = counter,
  // ... assign ALL state vars to themselves
}

action step = any {
  realAction1,
  realAction2,
  stutter,  // <-- prevents deadlock
}
```

### Every action must assign ALL state variables

If an action doesn't mention a variable, Apalache treats it as unconstrained (any value). This is almost never what you want.

**WRONG:**
```quint
action doThing = all {
  phase' = "done",
  // forgot counter' — Apalache may assign it to anything
}
```

**RIGHT:**
```quint
action doThing = all {
  phase' = "done",
  counter' = counter,  // explicitly unchanged
}
```

## Spec Design Guidelines

### What to specify (where Quint adds real value)

- **State machines with multiple interleaving actors** — the combinatorial explosion of interleavings is exactly what model checkers handle and humans can't
- **Double-call / re-entrancy guards** — prove a function can only be called once, or that concurrent access is safe
- **Bounded retry / backoff logic** — prove attempt counts, delay accumulation, and termination
- **Protocol invariants** — ordering guarantees, no-duplicate delivery, consistency properties

### What NOT to specify (waste of time)

- **Runtime/language semantics** — don't model "does Dart's event loop work correctly". You'd just be asserting your assumption about the runtime.
- **HTTP client behavior** — network timeouts, DNS, connection pooling are not model-checkable
- **Trivially obvious arithmetic** — if the code is `x + 1` and you can see it's correct, a spec adds nothing
- **Properties already enforced by the type system**

### Modeling non-determinism

For success/fail outcomes, use separate actions rather than a `nondet` oracle variable:

```quint
// Model both outcomes as distinct actions, let step pick non-deterministically
action attemptSuccess = all { phase == "trying", phase' = "done", ... }
action attemptFailure = all { phase == "trying", phase' = "failed", ... }
action step = any { attemptSuccess, attemptFailure, ... }
```

### Invariant design

- Name invariants descriptively: `callerUnblockedAfterFirstAttempt`, not `inv1`
- Create individual `val` for each property, then combine into `allInvariants`
- Use `implies` for conditional properties: `phase == "done" implies configLoaded`
- Always create a combined `allInvariants` for the `--invariant` flag

### Test design

- Cover the happy path, the worst-case path, and at least one mid-path
- Assert ALL relevant state variables in test assertions, not just the main one
- Tests use `.then()` chaining: `init.then(action1).then(action2).then(assertions)`
- The final `.then()` block must assign all state variables (frame condition)

## Iterative workflow

1. Write the spec
2. Run `quint test` — catches logic errors in your deterministic traces
3. Run `quint verify --invariant allInvariants` — exhaustive model check
4. If Apalache reports a violation, read the counterexample trace it prints — it shows the exact state sequence that breaks the invariant
5. Determine: is the spec wrong, or is the code wrong? Fix accordingly.
6. If the spec reveals a real code bug, fix the code AND update the spec, then re-verify

## Reference example

See `spec/client_config_retry.qnt` in this project for a complete working example covering:
- Exponential backoff retry state machine
- Blocking-first / async-retry pattern
- Double-call guard invariant
- Pre-computed lookup tables (Apalache-safe)
- Stutter step for terminal states
- 4 simulation tests + 7 model-checked invariants
