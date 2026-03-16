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


# YAML/text notation

As an example:
```yaml
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

YAML is a bit odd: it's basically prettier JSON.  Hopefully you can easilly-ish
see what's happening above, though.  The most important thing is probably that
everything is automatically converted into a string, unless it can be turned
into something else, like `1`, `-32`, or `false`, or it is part of other syntax,
like `[`, `-`, or `?`.

If you have any other ideas, we can totally discuss, this is just what I came up
with Sunday evening.
