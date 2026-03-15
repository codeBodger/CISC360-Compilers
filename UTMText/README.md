# Handwritten notation

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
