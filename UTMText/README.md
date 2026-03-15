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

## Alpha/Beta and relabelling shorthands


# YAML/text notation
