/* Fixed APROM trial/restore sequence. No generic command, address or file API. */
#ifndef DUCKY_APROM_PROTOCOL_H
#define DUCKY_APROM_PROTOCOL_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
/* Buffers are BSS, populated only from a SHA-256-pinned local image. No stock image is embedded. */
static uint8_t candidate_image[131072],restore_image[63848];
static const char candidate_sha256[]="cc1c222b7a5bb03866c5a1baa57e7587fc214596ed9b271b4f27410332d43d43";
static const char restore_sha256[]="fb29585b17a0ee1883287def35a1b107695a13c4dc85355cb27f54921ea5f514";
struct job { const uint8_t *image; size_t length; const char *sha256; };
static struct job image_job(int restore) {
    struct job j={restore?restore_image:candidate_image,
        restore?sizeof(restore_image):sizeof(candidate_image),restore?restore_sha256:candidate_sha256};
    return j;
}
static uint32_t le32(const uint8_t *b) {
    return (uint32_t)b[0]|(uint32_t)b[1]<<8|(uint32_t)b[2]<<16|(uint32_t)b[3]<<24;
}
static void put32(uint8_t *b,uint32_t n) {for(unsigned i=0;i<4;++i)b[i]=(uint8_t)(n>>(8*i));}
static uint16_t sum16(const uint8_t b[64]) {
    unsigned n=0;for(unsigned i=0;i<64;++i)n+=b[i];return (uint16_t)n;
}
static int job_valid(const struct job *j) {
    return j && ((j->image==candidate_image && j->length==sizeof(candidate_image))
        || (j->image==restore_image && j->length==sizeof(restore_image)))
        && j->length>=48 && j->length<=131072 && j->length%4==0;
}
static unsigned report_count(const struct job *j) {
    return job_valid(j)?3u+1u+(unsigned)((j->length-48+55)/56):0;
}
static size_t data_count(const struct job *j,unsigned step) {
    if(!job_valid(j) || step<3 || step>=report_count(j))return 0;
    size_t offset=step==3?0:48+(size_t)(step-4)*56;
    size_t maximum=step==3?48:56;
    return j->length-offset<maximum?j->length-offset:maximum;
}
static int fixed_request(const struct job *j,unsigned step,uint8_t b[64]) {
    if(!job_valid(j) || step>=report_count(j))return 0;
    memset(b,0,64);put32(b+4,step==0?0x12:step*2+1);
    if(step<3) {put32(b,step==0?0xae:step==1?0xb1:0xa2);return 1;}
    if(step==3) {
        put32(b,0xa0);put32(b+8,0);put32(b+12,(uint32_t)j->length);
        memcpy(b+16,j->image,data_count(j,step));
    } else memcpy(b+8,j->image+48+(size_t)(step-4)*56,data_count(j,step));
    return 1;
}
static int valid_reply(const struct job *j,unsigned step,const uint8_t *rx,size_t n) {
    uint8_t tx[64];
    if(n!=64 || !fixed_request(j,step,tx))return 0;
    return ((unsigned)rx[0]|(unsigned)rx[1]<<8)==sum16(tx) && le32(rx+4)==step*2+2;
}
typedef int (*exchange_fn)(void *,unsigned,const uint8_t[64],uint8_t[64],size_t *);
struct progress {unsigned submitted,acknowledged;size_t bytes_acknowledged;int aprom_attempted;};
static int program_aprom(const struct job *j,exchange_fn exchange,void *ctx,struct progress *p,int inspect_only) {
    uint8_t tx[64],rx[64];
    memset(p,0,sizeof(*p));
    if(!job_valid(j))return 0;
    for(unsigned step=0;step<(inspect_only?3u:report_count(j));++step) {
        size_t n=0;
        if(!fixed_request(j,step,tx))return 0;
        p->submitted++;
        if(step==3)p->aprom_attempted=1; /* erasure may precede even a lost first acknowledgement */
        if(!exchange(ctx,step,tx,rx,&n) || !valid_reply(j,step,rx,n))return 0;
        p->acknowledged++;
        if(step==1 && le32(rx+8)!=0x01132e10)return 0;
        if(step==2 && (le32(rx+8)!=0xfffffb7d || le32(rx+12)!=0x000fffff
            || le32(rx+16)!=0xffffff5a || le32(rx+20)!=0xffffffff))return 0;
        p->bytes_acknowledged+=data_count(j,step);
    }
    return inspect_only || p->bytes_acknowledged==j->length;
}
#endif
