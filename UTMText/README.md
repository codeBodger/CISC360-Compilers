# Handwritten notation

I've probably missed some things and made some mistakes: please let me know if
you have any questions.

## Simple-ish shorthands

- If a state does not have a transition leaving it on a given tape symbol,
  either the TM should fail, or the symbol has been deemed impossible, so the
  behaviour does not matter (though failure is probably the safest bet, so we
  know there's been some kind of error).
- If a state has a transition to read lower-case gamma, this means that *any*
  tape symbol can be read for the given transition.
  - If such a state also has *other* transitions, the gamma transition is to be
    taken if no other transition matches.
  - If such a transition *writes* a lower-case gamma (as many do), the character
    read should also be written.
- A transition on lower-case sigma indicates that any *input* symbol can be read
  for the transition.
  - As with lower-case gamma, if there are other transitions on input symbols,
    the sigma transition should be followed in all other cases.
  - If such a transition writes a lower-case sigma, the character read should
    also be written.

## Subroutines

- Each subroutine has an underlined label, which is used to 'call' it elsewhere
- When a subroutine is referenced (i.e. 'called'), it is as though it were a
  macro: the transition(s) in should simply be directed to (a copy of) the
  subroutine's start state, while the transition out should be directed from the
  'done' state.
- When a subroutine is called, it may have an epsilon transition leaving it.  As
  this is not a valid transition, it should be resolved in compilation by
  joining the resulting states on either side of the epsilon transition.  Note
  that no state should have both an epsilon transition and any other transitions
  out of it.
- True end-states such as 'reject' or 'accept' in subroutines should simply be
  treated as end-states: in compilation, all 'reject' states can be combined
  into one; the same with all 'accept's.
- The additional feaux end-states 'no' and 'yes' should act much like 'done',
  but allowing for multiple epsilon transitions out of a subroutine, each
  labelled with the feaux end-state they should lead out of after compilation.

## Alpha/Beta and relabelling shorthands

- Lower-case alpha and beta match only ever '0' or '1'.
- They can be concatenated with eachother or with other symbols to match the
  double tape symbols shown in capital gamma at the top of page 1.
  - When concatenated in this way, alpha always matches the first character and
    beta always matches the second character, in order to avoid ambiguity.
- As with gamma and sigma transitions, if an alpha/beta transition writes one of
  these, it is the same as the one it read.
- Alpha and beta are sometimes used in the states they come from or go to.  When
  this is done, the state can be thought of as being multiple states, named with
  the alpha/beta referenced replaced with either '0' or '1'.
- States that reference these can also *relabel* the alpha or beta.  This is
  indicated with an arrow, and allows a transition *out* of the state to both
  read *and write* dynamic, but different, values (i.e. writing depending on
  what they read going into them).
- Alpha and beta can be concatenated with sigma, as well: this works as you
  likely expect.


# text notation

Every file must have a header defining:
- `Gamma:` (a comma separated set of tape symbols)
- `Sigma:` (a comma separated set of input symbols; a subset of `Gamma`)
- `blank:` (a string in `Gamma` \ `Sigma`)
- `left:` (a string in `Gamma` \ `Sigma`)
- `a_set:` (a comma separated set of strings or initial substrings in `Gamma`,
    not including `left`)
- `b_set:` (a comma separated set of strings or final substrings in `Gamma`, not
    including `left`)
- `accept:` (the name of the global accept state)
- `reject:` (the name of the global reject state)

Note: a special `include:` (filename) clause can be used in a header, which acts
much like `#include` in C and C++.  This can be used for anything, but should be
reserved for including parts of the header, so as not to have to repeat oneself
in every file.

A pre-emptive description of notation:
- Following the header is the description of the state machine.
- The state machine is made up of a structure of states and routines, separated
    merely by newlines and spaces.
- Routines are declared on their own lines surounded by colons, followed by the
    name of their start state (i.e. `:<name>: <start state>`), with their part
    of the state machine following on subsequent lines.
    - Routines' return states are identifiable by having no outgoing transitions
    - Any routine can reference the global `accept` and `reject` states with
        their file-local names, as defined in the header
- States are of the form `[<name>]: <transition>; ... ; <transition>`
    - The `name` is optional
    - The `name` need not be unique
    - Always the most recently declared instance of that `name` (if present;
        otherwise, the next declaration) is used when referenced in a
        `transition`, unless specified (see below)
- Transitions are of the form `<read>/<write>,<direction> <destination>`, where
    - `read` is the comma separated set of symbols to be read (each elements of
        `Gamma`) OR:
        - `g`, indicating that *any* tape symbol should be matched (or, more
            specifically, amy tape symbol without a transition elsewhere
            specified out of the state in question)
        - `s`, indicating that any (not elsewhere matched) element of `Sigma`
            should be matched
        - some combination of tape symbols concatenated with `a`, `b`, `a'`,
            `b'`, and `s`, such that the concatenation would yeild elements of
            `Gamma` when the placeholders are replaced with the things they can
            be (see the header), and `'` is only used in the context of a
            renaming state
    - `write` is as `read`, just only one element, not a set
        - If `left` is in `read`, only `left` is valid here
    - `direction` is either `R` or `L`, indicating the direction to move the
        tape
        - If `left` is in `read`, only `R` is valid here
    - `destination` is the name of a destination state
        - The destination state must be within the same routine, be one of
            `accept` or `reject`, or be a subroutine call
            - To call a subroutine, reference its name followed by
                `(<transition>; ... ; <transition>)`
        - The destination state may alternatively be or be prefixed with any of:
            - `.`: the source state (or, as a prefix, a state declared on this
                line with the given name)
            - `^`: the first state on the previous line (or the first state
                declared on the previous line with the given name)
            - `$`: the first state on this line (or the first state on any line,
                given that it has this name, looking above before below)
            - `|`: the first state on the next line (or the first state on the
                next line with the given name)
            - `-`: the previous state on this line (or the first state, looking
                backwards from the source state, with the given name)
            - `+`: the next state on this line (or the first state, looking
                forwards from the source state, with the given name)
            - Calling a subroutine, as described above, allows it to be
                referenced in these ways, in which case, nothing should be
                within the parentheses.
        - Appending `&(a->a'|b->b')` indicates that the referenced state must
            store the given value and call it the primed value, so it can be
            used in its outgoing transitions.
- Transitions out of subroutine calls are of the form
    `[<label>] (<read>/<write>,<direction>|e) <destination>`, where
    - Previously described elements are as then described
    - `label` is the name of the return state of the subroutine from which to
        follow the transition
        - `label` is required if the subroutine has multiple return states
    - `e` is a literal `e`, indicating that an epsilon transition is to be taken
        - Either all transitions out of a given routine from a given return
            state must be epsilon transitions, or none of them must be.
    - Subroutine calls can also be made separately from a transition, allowing
        them to be referenced in much the same way as if they were previously
        declared *within* a transition.
        - In this case, no colon should follow the parentheses, however.
- As evident partially in the descriptions of the state machine, states, and
    transitions, multiple states can be placed on one line.  The grammar does
    not require, however, any delimiter between states.  Additionally, to avoid
    excessively long lines, `\` can escape the newline character, as is common.
- Unless otherwise specified in compilation, `main` is taken to be the entry
    point.
- Comments:
    - full lines prefixed with `//`
    - if a comment line ends with `\`, the comment does not continue
    - if the line before a comment ends with `\`, the comment is ignored, and
        the line after the comment appened, not the comment itself.

## An Example

`main.tmh`
```
Gamma: [, _, 0, 1, 00, 01, 10, 11, #, #0, #1
Sigma: 0, 1, #
blank: _
left: [
a_set: 0, 1
b_set: 0, 1
accept: accept
reject: reject
```

`main.tm`
```
include: main.tmh

:main: S
S: [/[,R |
a_state: 0,1/0,R .; g/g,R |
another_state: 0/0,R + : g/g,L |
state_4: ab/ab,L |&a->a'
seen: ab/a'b,R |
move: 0/0,L a_subroutine(e |)
state_7: 0/0,L another_subroutine(no e +subroutine_4(); yes e |()) \
    1/1,L subroutine_3(s/s,L +(); [/[,R |()) subroutine_4(e +()) \
    subroutine_5(e +()) subroutine_6(e +()) subroutine_7(e -subroutine_4())
subroutine_4(e +()) subroutine_5(e +()) subroutine_6(e +()) \
    subroutine_7(s/s,L state_7; [/[,R reject; g/g,L ^subroutine_4())
```

## Old abandoned YAML notations

As an example:
```yaml
formalism: original
start state: S
table:
  S:
    # on '[', change to state 'a_state', rewrite, and move right
    '[': [a_state, R]
    # fail on all else
  a_state:
    '0': [R] # on '0', don't change state, rewrite, and move right
    '1': ['0', R] # on '1', don't change state, rewrite, and move right
    gamma: [another_state, R] # change to another_state, rewrite, and move right
  another_state:
    # on '0', change to anonymous state, rewrite, and move right
    # in anonymous state, on anything, change to state_4, rewrite, and move left
    '0': [{gamma: [state_4, L]}, R]
  state_4:
    # on alpha_beta, change to "seen alpha->alpha'", rewrite, and move left
    alpha_beta: ["seen alpha->alpha'", L]
  "seen alpha->alpha'":
    # on alpha_beta, change to move, write "alpha'_beta", i.e. the alpha from
    # before and the beta from just now (see 'Alpha/Beta and relabelling
    # shorthands' above), and move right
    alpha_beta: [move, "alpha'_beta", R]
  move:
    # on '0', enter a_subroutine, rewrite, and move left
    # upon exiting the subroutine, epsilon transition to state_7
    '0': [a_subroutine, L, {epsilon: state_7}]
  state_7:
    # on '0', enter another_subroutine, rewrite, and move left
    # upon exiting the subroutine, if ended in state 'no', epsilon transition to
    # state 8, if ended in state 'yes', epsilon transition to state_9
    '0': [another_subroutine, L, {'no epsilon': state_8,
                                  'yes epsilon': state_9}]
    # on '1', enter subroutine_3, follow typical transitions from 'done', as
    # indicated (I guess it looks kind of like the anonymous state)
    '1': [subroutine_3, L, {sigma: [state_8, L], '[': [state_9: R]}]
```

Or maybe better:
```yaml
formalism: nesting minimising
start state: S
table:
  # same as above until here
  move:
    # on '0', enter a_subroutine, rewrite, and move left
    # upon exiting the subroutine, transition to state_7, implicitly on epsilon
    '0': [[a_subroutine, state_7], L]
    # or equivalently:
    '0': [[a_subroutine: {epsilon: state_7}], L]
  state_7:
    # on '0', enter another_subroutine, rewrite, and move left
    # upon exiting the subroutine, if ended in state 'no', epsilon transition to
    # state_8, if ended in state 'yes', epsilon transition to state_9
    '0':
      - [another_subroutine: {'no epsilon': state_8, 'yes epsilon': state_9}]
      - L
    # on '1', enter subroutine_3, follow typical transitions from 'done', as
    # indicated
    '1': [[subroutine_3: {sigma: [state_8, L], '[': [state_9: R]}], L]
    # or if you'd prefer to think of it as an implicit epsilon transition to an
    # anonymous state:
    '1': [[subroutine_3, {sigma: [state_8, L], '[': [state_9: R]}], L]
  # The above rely on an idea of a pseudo-state or 'label' being for a list of
  # subroutines.  Below, state_8 is really an endless loop of subroutines with
  # epsilon transitions between them.  At the end, there's an epsilon transition
  # to state_8 itself, which really just goes to its first subroutine
  state_8:
    - subroutine_4
    - subroutine_5
    - subroutine_6
    - subroutine_7
    - state_8
  # Here, state_9 is similar to state_8, but the final subroutine (subroutine_7)
  # has explicit transitions out of it.
  state_9:
    - subroutine_4
    - subroutine_5
    - subroutine_6
    - subroutine_7:
        sigma: [state_7, L]
        '[': [failure, R]
        gamma: [state_8, L]
  # For identical effect, an anonymous state could be implicitly epsilonned to:
  state_9:
    - subroutine_4
    - subroutine_5
    - subroutine_6
    - subroutine_7
    - sigma: [state_7, L]
      '[': [failure, R]
      gamma: [state_8, L]
```

YAML is a bit odd: it's basically prettier JSON.  Hopefully you can easilly-ish
see what's happening above, though.  The most important thing is probably that
everything is automatically converted into a string, unless it can be turned
into something else, like `1`, `-32`, or `false`, or it is part of other syntax,
like `[`, `-`, or `?`.

If you have any other ideas, we can totally discuss, this is just what I came up
with Sunday evening.


# Routine statuus

Checked if completed

- [x] check.tm
    - [x] check_accept
    - [x] check_reject
- [ ] dub_operations.tm
    - [ ] to_dub_start_from_R
    - [ ] delete_dub
    - [ ] dubify_q'1g'1i
- [x] main.tm
    - [x] main
    - [x] init
    - [x] proc
- [ ] shift.tm
    - [ ] shift_dub_L
    - [ ] shift_dub_R
- [ ] to_location.tm
    - [x] to_left
    - [x] to_H
    - [x] verify_g'_placed_before_H
    - [ ] to_star_H
    - [ ] verify_g'_placed_before_star_H
    - [ ] move_to_hash
    - [ ] verify_hash1
- [ ] unclassified
    - [ ] do_i_del_1i
    - [ ] find_and_write_blank
    - [ ] find_trans
    - [ ] read_gamma
    - [ ] shift_right
    - [ ] write_gp
