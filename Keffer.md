Definition 14: A <u>Turing Machine</u> (TM) M is a 9-tuple (Σ, Γ, Q, ⊦, ⊔, s,
t, r, δ) where:
- Σ is a finite alphabet of input symbols
- Γ &sup; Σ is a finite alphabet of tape symbols
- Q is a finite set of states
- ⊦ &isin; Γ\Σ is the left end marker
- ⊔ &isin; Γ\Σ is the blank symbol
- s is the start state
- t is the accept state
- r is the reject state
- δ:Q&times;Γ &rarr; Q&times;Γ&times;{L,R} is the transition function

Some things to note (i.e. how a TM works):
- A Turing Machine has unbounded memory in the form of a tape of cells - the
  first of which contains ⊦ - stretching out to infinity to the right.
- The machine has a read/write head denoting the current cell that starts at the
  ⊦ and can move left or right with the caveat that it cannot move to the left
  of ⊦.
- The machine halts execution iff it enters either the accept or reject state.
- A tripple (q,ɣ,d) in the range of δ specifies that the machine will transition
  to state q, write the symbol ɣ to the current cell, and then move the
  read/write head one cell in direction d.
- The initial contents of the tape is ⊦, followed by the input, followed by an
  infinite sequence of ⊔s.

The above was taken from Dr. Keffer's notes for CISC 303 at the University of
Delaware, 2025-11-06.  Below is a description (by Samhain Ackerman) of the
graphical representation used by Dr. Keffer in that course.

When writing out a TM in graphical form, an incoming arrow from nowhere
(typically labelled with ⊦) points to s, the start state.  Transitions are
denoted as labelled arrows from a state q to a state q' (which can be the same
state), where the label is of the form ɣ/ɣ',d (or a list/set of such forms),
indicating that δ(q,ɣ) = (q',ɣ',d).
