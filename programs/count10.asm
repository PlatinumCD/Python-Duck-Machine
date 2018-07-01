        LOAD r1,r0,r0[510]
        STORE  r1,watch_1
        LOAD r1,const0_3  # Const 0
        STORE  r1,count_2
        LOAD r1,r0,r0[510]
        STORE  r1,observe_4
loop_5:  #While loop
        LOAD r2,observe_4
        SUB  r0,r2,r0
        JUMP/Z endloop_6
watch_1: DATA 0 #watch
count_2: DATA 0 #count
observe_4: DATA 0 #observe
const0_3:  DATA 0
