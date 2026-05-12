include: utm.tmh

// pg 2, middle left
:to_left: |()
shift_dub_L(s/s,L +; [/[,R |) back_to_dub_start: g/g,R $()
saw_left: g/g,L |
done

// pg 6, bottom left
:to_H: |()
shift_dub_R(s/s,R |())
verify_g'_placed_before_H(yes e |; no e ^)
done:

// pg 6, bottom right
:verify_g'_placed_before_H: |
q': 10/10,R .; 00/00,R .; #0/#0,R .; 11/11,R $g'; #1/#1,R $g'; 01/01,L |
to_front_of_dub: 10/10,L .; 00/00,L .; #0/#0,L .; 11/11,L .; #1/#1,L .; \
        g/g,R + : g/g,L no
g': 0/0,R .; 01/01,R .; 00/00,R .; \
        H0/H0,L |; H1/H1,L |; H/H,L | \
        #/#,L ^; #0/#0,L ^; #1/#1,L ^; 10/10,L ^; 11/11,L ^
through_0s: 0/0,L .; \
        #0/#0,L |; 10/10,L |; 11/11,L |; #1/#1,L |; 00/00,L |; 01/01,L |
to_front_of_dub: g/g,R + \
        #0/#0,L .; 10/10,L .; 11/11,L .; #1/#1,L .; 00/00,L .; 01/01,L . \
        : g/g,L |
yes:
no:
