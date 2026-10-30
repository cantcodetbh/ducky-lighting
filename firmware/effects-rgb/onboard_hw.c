#include "onboard_hw.h"
#define REG(a) (*(volatile uint32_t *)(uintptr_t)(a))
__attribute__((section(".ramfunc"),noreturn,noinline,used))
void nv_ram_fault(void) { for(;;)__asm__ volatile("wfi"); }
__attribute__((section(".ramfunc"),noinline))
static void wait_ready(void) {
    uint32_t timeout=5000000u;
    while(((REG(0x4000c010u)|REG(0x4000c040u))&1u) && --timeout){}
    /* Never return to APROM while its controller is still busy. A hardware
       fault leaves the old journal intact and requires physical power removal. */
    if(!timeout)nv_ram_fault();
}
/* This complete, relocation-free function and its literal pool are copied to SRAM.
   No calls or flash fetches are allowed between ISP trigger and completion. */
__attribute__((section(".ramfunc"),noinline,used))
int nv_ram_command(uint32_t command,uint32_t address,uint32_t value) {
    if(REG(0x40000000u)!=0x01132e10u)return 0;
    if(command==0x22u) {
        if(address!=NV_SLOT0 && address!=NV_SLOT1)return 0;
    } else if(command==0x21u) {
        if(address<NV_SLOT0 || address>=NV_SLOT1+NV_PAGE || (address&3u))return 0;
    } else return 0;
    if(REG(0x4000c010u)&1u)return 0;
    uint32_t original=REG(0x4000c000u),unlocked=REG(0x40000100u)&1u;
    if(original&64u)return 0;
    if(!unlocked) {
        REG(0x40000100u)=0x59;REG(0x40000100u)=0x16;REG(0x40000100u)=0x88;
        if(!(REG(0x40000100u)&1u))return 0;
    }
    /* Preserve boot-source selection. Disable SPROM/CONFIG/LDROM updates. */
    REG(0x4000c000u)=(original&~0x3du)|9u;
    /* Recheck the installed data-flash/boot configuration without enabling CFG writes. */
    REG(0x4000c00cu)=0;REG(0x4000c004u)=0x00300000u;REG(0x4000c010u)=1;
    __asm__ volatile("isb" ::: "memory");
    wait_ready();
    int ok=REG(0x4000c008u)==0xfffffb7du && !((REG(0x4000c000u)|REG(0x4000c040u))&64u);
    if(!ok) {
        REG(0x4000c000u)=original|64u;
        if(!unlocked)REG(0x40000100u)=0;
        return 0;
    }
    REG(0x4000c00cu)=command;REG(0x4000c004u)=address;REG(0x4000c008u)=value;
    REG(0x4000c010u)=1;
    __asm__ volatile("isb" ::: "memory");
    wait_ready();
    ok=!((REG(0x4000c000u)|REG(0x4000c040u))&64u);
    /* M032SE3AE has no flash cache (TRM 2.02 p322/362). */
    REG(0x4000c000u)=original|64u; /* restore update gates; W1C ISPFF */
    if(!unlocked)REG(0x40000100u)=0;
    return ok;
}
uint32_t nv_hw_read(uint32_t address) {return REG(address);}
static int invoke(uint32_t command,uint32_t address,uint32_t value) {
    uintptr_t offset=((uintptr_t)nv_ram_command&~(uintptr_t)1)-(uintptr_t)__ramfunc_start;
    return ((int (*)(uint32_t,uint32_t,uint32_t))(uintptr_t)((NV_RAM_DRIVER+offset)|1u))(command,address,value);
}
int nv_hw_erase(uint32_t address) {return invoke(0x22,address,0xffffffffu);}
int nv_hw_write(uint32_t address,uint32_t value) {return invoke(0x21,address,value);}
