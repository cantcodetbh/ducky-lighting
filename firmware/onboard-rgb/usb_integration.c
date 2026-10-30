/* custom9003 candidate: reserved APROM journal and explicit onboard save/clear.
 * Offline-tested implementation; physical trial required before release. */
#include "host_rgb.h"
#include "onboard_hw.h"
#define U8(a) (*(volatile uint8_t *)(uintptr_t)(a))
#define U32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define FN0(a) ((void (*)(void))(uintptr_t)((a)|1u))
struct rgb_context {
    struct ducky_rgb_state rgb;
    uint8_t rx[8], status[8];
    uint32_t descriptors[7], reports[4], lengths[4];
    uint8_t config[109], device[18];
    uint8_t receive_mode, pending, last_result, saved;
    uint32_t nv_scratch[NV_WORDS];
};
#define CTX ((volatile struct rgb_context *)0x20002500u)
_Static_assert(sizeof(struct rgb_context) <= 0x800, "test context reservation exceeded");
static const uint8_t keyboard_report[] = {
#include "keyboard_report.inc"
    /* Separate vendor application collection, Feature body 8, no Report ID. */
    0x06,0x00,0xff,0x09,0x01,0xa1,0x01,0x15,0x00,0x26,0xff,0x00,
    0x75,0x08,0x95,0x08,0x09,0x02,0xb1,0x02,0xc0
};
static inline uint32_t irq_lock(void) {
    uint32_t saved;
    __asm__ volatile("mrs %0, primask\n cpsid i" : "=r"(saved) :: "memory");
    return saved;
}
static inline void irq_restore(uint32_t saved) {
    __asm__ volatile("msr primask, %0" :: "r"(saved) : "memory");
}
static void stall_both(void) {
    /* Both internal control endpoints share USB endpoint number zero.
       Original SetStall(1) searches by USB number and can hit keyboard IN. */
    U32(0x400c050c)|=2;
    U32(0x400c051c)|=2;
}
static const struct nv_io store={nv_hw_read,nv_hw_erase,nv_hw_write};
static void restore_onboard(void) {
    int loaded=nv_load(&store,(uint16_t *)CTX->rgb.frame);
    CTX->saved=(uint8_t)(loaded==1);CTX->rgb.active=(uint8_t)(loaded==1);
}
void ducky_class_hook(void);
void ducky_open_hook(uint32_t table, uint32_t callback, uint32_t alternate)
{
    (void)callback;
    volatile uint8_t *bytes = (volatile uint8_t *)CTX;
    for (unsigned i=0; i<sizeof(*CTX); ++i) bytes[i]=0;
    for(unsigned i=0;i<(unsigned)(__ramfunc_end-__ramfunc_start);++i)
        U8(NV_RAM_DRIVER+i)=__ramfunc_start[i];
    restore_onboard();
    const uint32_t *original = (const uint32_t *)(uintptr_t)table;
    for (unsigned i=0;i<7;++i) CTX->descriptors[i]=original[i];
    for (unsigned i=0;i<4;++i) {
        CTX->reports[i]=((const uint32_t *)(uintptr_t)original[3])[i];
        CTX->lengths[i]=((const uint32_t *)(uintptr_t)original[5])[i];
    }
    for(unsigned i=0;i<109;++i) CTX->config[i]=((const uint8_t *)(uintptr_t)original[1])[i];
    for(unsigned i=0;i<18;++i) CTX->device[i]=((const uint8_t *)(uintptr_t)original[0])[i];
    CTX->config[25]=sizeof(keyboard_report);
    CTX->config[26]=0;
    CTX->device[12]=0x03; CTX->device[13]=0x90; /* candidate bcdDevice marker */
    CTX->reports[0]=(uint32_t)(uintptr_t)keyboard_report;
    CTX->lengths[0]=sizeof(keyboard_report);
    CTX->descriptors[0]=(uint32_t)(uintptr_t)CTX->device;
    CTX->descriptors[1]=(uint32_t)(uintptr_t)CTX->config;
    CTX->descriptors[3]=(uint32_t)(uintptr_t)CTX->reports;
    CTX->descriptors[5]=(uint32_t)(uintptr_t)CTX->lengths;
    ((void (*)(uint32_t,uint32_t,uint32_t))0xe5bfu)(
        (uint32_t)(uintptr_t)CTX->descriptors,(uint32_t)(uintptr_t)ducky_class_hook,alternate);
}
void ducky_setup_hook(void)
{
    /* A new SETUP cancels an incomplete OUT transfer, not an accepted command. */
    CTX->receive_mode=0;
    U8(0x20002470)=0;
    U32(0x200023dc)=0; U32(0x200023e4)=0; U32(0x200023e8)=0;
    FN0(0xe624)();
}
void ducky_class_hook(void)
{
    volatile uint8_t *s=(volatile uint8_t *)0x20002374u;
    unsigned value=(unsigned)s[2] | (unsigned)s[3]<<8;
    unsigned index=(unsigned)s[4] | (unsigned)s[5]<<8;
    unsigned length=(unsigned)s[6] | (unsigned)s[7]<<8;
    if (s[1]==9) {
        if(s[0]==0x21 && value==0x0300 && index==0 && length==8 && !CTX->pending) {
            CTX->receive_mode=1;
            ((void (*)(uint32_t,uint32_t))0xec7fu)((uint32_t)(uintptr_t)CTX->rx,8);
            U32(0x400c0518)|=0x80; /* original control OUT DATA1 selection */
            /* IN status is armed only after successful OUT reception. */
            return;
        }
        if(s[0]==0x21 && value==0x0200 && index==0 && length==1) {
            CTX->receive_mode=2;
            FN0(0xefd8)(); /* bounded conventional keyboard LED Output */
            return;
        }
        stall_both(); return;
    }
    if (s[1]==1 && (value>>8)==3) {
        if(s[0]!=0xa1 || value!=0x0300 || index!=0 || length!=8) {stall_both();return;}
        CTX->status[0]='D'; CTX->status[1]='R'; CTX->status[2]='G'; CTX->status[3]='B';
        CTX->status[4]=2; CTX->status[5]=CTX->rgb.active;
        CTX->status[6]=CTX->last_result; CTX->status[7]=(uint8_t)(CTX->pending|(CTX->saved<<1));
        ((void (*)(uint32_t,uint32_t))0xeb19u)((uint32_t)(uintptr_t)CTX->status,8);
        /* Match original standard IN requests: arm the final host OUT ZLP. */
        ((void (*)(uint32_t,uint32_t))0xec7fu)(0,0);
        return;
    }
    FN0(0xefd8)(); /* existing SET_IDLE and other original class handling */
}
void ducky_out_hook(void)
{
    unsigned mode=CTX->receive_mode;
    unsigned received=U32(0x400c0514);
    if(mode==0) {
        if(received==0) FN0(0xeca4)(); else stall_both();
        return;
    }
    CTX->receive_mode=0;
    if(U32(0x400c0510)!=8 || received!=(mode==1 ? 8u : 1u)) {
        U8(0x20002470)=0; U32(0x200023e8)=0;
        stall_both(); return;
    }
    if(mode==2) {FN0(0xeca4)(); return;}
    for(unsigned i=0;i<8;++i) CTX->rx[i]=U8(0x400c0108u+i);
    CTX->pending=1;
    U32(0x200023e4)=8; U32(0x200023e8)=0;
    ((void (*)(uint32_t,uint32_t))0xeb19u)(0,0);
}
void ducky_lighting_hook(void)
{
    uint32_t saved=irq_lock();
    if(CTX->pending) {
        unsigned op=CTX->rx[1];
        if(CTX->rx[0]==0xd1 && (op==4 || op==5)) {
            unsigned reserved=0;
            for(unsigned i=2;i<8;++i)reserved|=CTX->rx[i];
            CTX->last_result=0;
            if(!reserved && (op==5 || CTX->rgb.active)) {
                CTX->last_result=(uint8_t)nv_commit(&store,(uint32_t *)CTX->nv_scratch,
                                                   (const uint16_t *)CTX->rgb.frame,op==5);
                if(CTX->last_result) {
                    CTX->saved=(uint8_t)(op==4);
                    if(op==5)CTX->rgb.active=0;
                }
            }
        } else CTX->last_result=(uint8_t)ducky_rgb_command((struct ducky_rgb_state *)&CTX->rgb,
                                                   (const uint8_t *)CTX->rx,8);
        CTX->pending=0;
        if(CTX->last_result && !CTX->rgb.active) {
            U8(0x2000244e)=0xff; /* force current effect's on-enter callback */
            U8(0x20000db8)=1;
        }
    }
    if(CTX->rgb.active) {
        for(unsigned i=0;i<210;++i) ((volatile uint16_t *)0x20001600u)[i]=CTX->rgb.frame[i];
        U8(0x20000db8)=0; /* select original inactive-bank copy, bypass effects/overlays */
        FN0(0x5fd8)();
        irq_restore(saved);
        return;
    }
    irq_restore(saved);
    FN0(0x5fd8)();
}
void ducky_reset_hook(void)
{
    CTX->receive_mode=0; CTX->pending=0; CTX->last_result=0; CTX->rgb.active=0;
    for(unsigned i=0;i<210;++i) CTX->rgb.frame[i]=0;
    FN0(0xecf8)();
    restore_onboard();
    U8(0x2000244e)=0xff; U8(0x20000db8)=1;
}
/* ELF metadata for offline tests: inspect actual compiler layout, not guessed offsets. */
const uint32_t ducky_context_layout[] = {
    sizeof(struct rgb_context), offsetof(struct rgb_context,rx),
    offsetof(struct rgb_context,status), offsetof(struct rgb_context,receive_mode),
    offsetof(struct rgb_context,pending), offsetof(struct rgb_context,last_result),
    offsetof(struct rgb_context,rgb.active),offsetof(struct rgb_context,saved),offsetof(struct rgb_context,nv_scratch)
};
