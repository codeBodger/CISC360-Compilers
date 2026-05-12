include: utm.tmh

// pg 2, bottom
:check_accept: |()
shift_dub_R(0/0,R +; [/[,R +; 1/1,R |) Q: g/g,L $
: g/g,L |
shift_dub_R(0/0,R +; [/[,R +; 1/1,R |) G: g/g,L $
: g/g,L |
shift_dub_R(0/0,R +; [/[,R +; 1/1,R |) S: g/g,L $
: g/g,L |
shift_dub_R(0/0,R +; [/[,R +; 1/1,R |) s: g/g,L $
do_check: 00/00,R .; 11/11,R accept; 10/10,L |; 01/01,L |
to_front_of_dub: 00/00,L .; 1/1,R + : g/g,L |
done:

// pg 6, top
:check_reject: |()
shift_dub_R(0/0,R +; 1/1,R |) t: g/g,L
do_check: 00/00,R .; 11/11,R reject; 10/10,L |; 01/01,L |
to_front_of_dub: 00/00,L .; 1/1,R + : g/g,L |
done:
