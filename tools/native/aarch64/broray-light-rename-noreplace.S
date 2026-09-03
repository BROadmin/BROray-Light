/*
 * BROray-Light atomic no-clobber rename helper.
 *
 * Contract:
 *   fd 7: retained and validated source parent directory
 *   fd 8: retained and validated destination parent directory
 *   argv[1]: source leaf, 1..255 bytes, no slash, not dot or dot-dot
 *   argv[2]: destination leaf under the same constraints
 *
 * The helper performs exactly one mutating syscall:
 *   renameat2(7, argv[1], 8, argv[2], RENAME_NOREPLACE)
 *
 * Exit status:
 *   0 committed; 64 argc; 65 source leaf; 66 destination leaf;
 *   67 EEXIST; 68 ENOSYS; 69 EINVAL/EOPNOTSUPP; 70 other syscall error.
 */

.arch armv8-a

.equ SYS_exit,             93
.equ SYS_renameat2,       276
.equ RENAME_NOREPLACE,      1
.equ SOURCE_PARENT_FD,      7
.equ DESTINATION_PARENT_FD, 8

.section .text
.p2align 2
.global _start
.type _start, %function

_start:
    ldr     x0, [sp]
    cmp     x0, #3
    b.ne    .Lusage

    ldr     x19, [sp, #16]
    ldr     x20, [sp, #24]

    mov     x0, x19
    bl      .Lleaf_invalid
    cbnz    w0, .Lbad_source

    mov     x0, x20
    bl      .Lleaf_invalid
    cbnz    w0, .Lbad_destination

    mov     w0, #SOURCE_PARENT_FD
    mov     x1, x19
    mov     w2, #DESTINATION_PARENT_FD
    mov     x3, x20
    mov     w4, #RENAME_NOREPLACE
    mov     w8, #SYS_renameat2
    svc     #0

    cbz     x0, .Lok
    cmn     x0, #17
    b.eq    .Lcollision
    cmn     x0, #38
    b.eq    .Lenosys
    cmn     x0, #22
    b.eq    .Lunsupported
    cmn     x0, #95
    b.eq    .Lunsupported
    mov     w0, #70
    b       .Lexit

.Lleaf_invalid:
    mov     x1, x0
    mov     w2, wzr
.Lleaf_scan:
    ldrb    w3, [x1], #1
    cbz     w3, .Lleaf_end
    cmp     w3, #47
    b.eq    .Lleaf_reject
    add     w2, w2, #1
    cmp     w2, #255
    b.ls    .Lleaf_scan
    b       .Lleaf_reject

.Lleaf_end:
    cbz     w2, .Lleaf_reject
    cmp     w2, #1
    b.eq    .Lleaf_one
    cmp     w2, #2
    b.ne    .Lleaf_accept
    ldrb    w3, [x0]
    cmp     w3, #46
    b.ne    .Lleaf_accept
    ldrb    w3, [x0, #1]
    cmp     w3, #46
    b.eq    .Lleaf_reject
    b       .Lleaf_accept

.Lleaf_one:
    ldrb    w3, [x0]
    cmp     w3, #46
    b.eq    .Lleaf_reject

.Lleaf_accept:
    mov     w0, wzr
    ret

.Lleaf_reject:
    mov     w0, #1
    ret

.Lusage:
    mov     w0, #64
    b       .Lexit
.Lbad_source:
    mov     w0, #65
    b       .Lexit
.Lbad_destination:
    mov     w0, #66
    b       .Lexit
.Lcollision:
    mov     w0, #67
    b       .Lexit
.Lenosys:
    mov     w0, #68
    b       .Lexit
.Lunsupported:
    mov     w0, #69
    b       .Lexit
.Lok:
    mov     w0, wzr
.Lexit:
    mov     w8, #SYS_exit
    svc     #0
    brk     #0

.size _start, .-_start

.section .note.GNU-stack,"",%progbits
