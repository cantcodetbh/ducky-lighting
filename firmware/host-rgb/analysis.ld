/* OFFLINE placement only; does not assert actual flash/SRAM availability. */
ENTRY(ducky_open_hook)
PHDRS { patch PT_LOAD FLAGS(5); }
SECTIONS {
    . = 0xf970;
    .text : { *(.text*) *(.rodata*) } :patch
    .ARM.exidx : { *(.ARM.exidx*) } :patch
    .data : { *(.data*) } :patch
    .bss : { *(.bss*) *(COMMON) } :patch
    /DISCARD/ : { *(.comment) *(.note*) }
    ASSERT(SIZEOF(.data)==0, "unexpected initialized globals")
    ASSERT(SIZEOF(.bss)==0, "unexpected BSS globals")
    ASSERT(. < 0x20000, "exceeds nominal APROM")
}
