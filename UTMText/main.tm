include: utm.tmh

:main: |
init(e |)
proc()

:init: |
Q: 0,[/g,R .; 1/1,R |
G: 0/0,R .; 1/1,R |
S: 0/0,R .; 1/1,R |
s: 0/00,R .; 1/11,L |
to_front_of_dub: 00/00,L .; 1/1,R |()
move_to_hash(e +) : 0/00,R .; 1/H,R |()
shift_right(e to_dub_start_from_R(e |))
done:

:proc: |()
to_left(e +()) check_accept(e +()) check_reject(e +()) find_trans(e +()) \
        delete_dub(e +()) dubify_q'1g'1i(e +()) to_H(e +()) write_g'(e +()) \
        do_i_del_1i(e +()) read_g(e $())
