ENTRY(ducky_open_hook)
PHDRS { patch PT_LOAD FLAGS(5); }
SECTIONS {
    . = 0xf970;
    .text : { *(.text*) *(.rodata*) } :patch
    .ARM.exidx : { *(.ARM.exidx*) } :patch
    .ramfunc ALIGN(4) : { __ramfunc_start = .; KEEP(*(.ramfunc)); __ramfunc_end = .; } :patch
    .data : { *(.data*) } :patch
    .bss : { *(.bss*) *(COMMON) } :patch
    /DISCARD/ : { *(.comment) *(.note*) }
    ASSERT(SIZEOF(.data)==0, "unexpected initialized globals")
    ASSERT(SIZEOF(.bss)==0, "unexpected BSS globals")
    ASSERT(SIZEOF(.ramfunc)<=0x300, "SRAM driver exceeds its reserved region")
    ASSERT(. < 0x1fc00, "application overlaps profile journal")
}
