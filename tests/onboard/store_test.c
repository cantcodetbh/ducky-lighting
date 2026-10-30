/* Production record code with RAM-only NOR flash. No device APIs. */
#include "onboard_store.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FAIL line%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static uint8_t flash[1024],before[1024];
static unsigned operations,cut_at,torn_mode;
static uint32_t offset(uint32_t address){CHECK(address>=NV_SLOT0 && address<NV_SLOT1+NV_PAGE && !(address&3));return address-NV_SLOT0;}
static uint32_t read_word(uint32_t address){uint32_t value;memcpy(&value,flash+offset(address),4);return value;}
static int erase_page(uint32_t address){
    CHECK(address==NV_SLOT0 || address==NV_SLOT1);++operations;
    if(operations==cut_at){if(torn_mode)memset(flash+offset(address),0xff,256);return 0;}
    memset(flash+offset(address),0xff,NV_PAGE);return 1;
}
static int write_word(uint32_t address,uint32_t value){
    uint32_t old=read_word(address);CHECK((old&value)==value);++operations;
    if(operations==cut_at){if(torn_mode){uint32_t partial=old&(value|0xaaaaaaaa);memcpy(flash+offset(address),&partial,4);}return 0;}
    memcpy(flash+offset(address),&value,4);return 1;
}
static const struct nv_io io={read_word,erase_page,write_word};
static void seed(uint32_t address,uint32_t seq){
    uint32_t data[NV_WORDS];memset(data,0xff,sizeof(data));data[0]=NV_MAGIC0;data[1]=NV_MAGIC1;data[2]=1;data[3]=seq;data[4]=0;
    memset((uint8_t *)data+NV_FRAME_OFFSET,0,NV_RGB_BYTES);data[NV_CRC_OFFSET/4]=nv_crc_bytes((uint8_t *)data,NV_CRC_OFFSET);data[NV_COMMIT_OFFSET/4]=NV_COMMIT;memcpy(flash+offset(address),data,sizeof(data));
}
static void factory(void){memset(flash,0xff,sizeof(flash));seed(NV_SLOT0,0);seed(NV_SLOT1,1);operations=0;cut_at=0;torn_mode=0;}
int main(void){
    uint16_t first[210],second[210],actual[210];uint32_t scratch[NV_WORDS];
    for(unsigned i=0;i<210;++i){first[i]=(uint16_t)((i%256)*257u);second[i]=(uint16_t)((255-i%256)*257u);}
    factory();CHECK(nv_load(&io,actual)==0 && operations==0);
    CHECK(nv_commit(&io,scratch,first,0));CHECK(operations==61);CHECK(nv_load(&io,actual)==1 && !memcmp(first,actual,sizeof(first)));
    unsigned saved_ops=operations;CHECK(nv_commit(&io,scratch,first,0));CHECK(operations==saved_ops);
    memcpy(before,flash,sizeof(flash));unsigned powercuts=0;
    for(unsigned clear=0;clear<=1;++clear)for(unsigned cut=1;cut<=61;++cut)for(unsigned torn=0;torn<=1;++torn){
        memcpy(flash,before,sizeof(flash));operations=0;cut_at=cut;torn_mode=torn;
        CHECK(!nv_commit(&io,scratch,second,(int)clear));CHECK(operations==cut);
        int result=nv_load(&io,actual);CHECK(result==1 || (clear && result==0));
        if(result==1)CHECK(!memcmp(actual,first,sizeof(first)) || (!clear && !memcmp(actual,second,sizeof(second))));
        /* A reboot, fresh scratch and another explicit attempt can complete. */
        cut_at=0;operations=0;memset(scratch,0xa5,sizeof(scratch));CHECK(nv_commit(&io,scratch,second,(int)clear));
        CHECK(nv_load(&io,actual)==(clear?0:1));if(!clear)CHECK(!memcmp(actual,second,sizeof(second)));++powercuts;
    }
    factory();CHECK(nv_commit(&io,scratch,first,0));CHECK(nv_commit(&io,scratch,second,1));CHECK(nv_load(&io,actual)==0);
    saved_ops=operations;CHECK(nv_commit(&io,scratch,second,1));CHECK(saved_ops==operations);
    /* Every one-bit corruption of newest record falls back to the intact prior record. */
    factory();CHECK(nv_commit(&io,scratch,first,0));memcpy(before,flash,sizeof(flash));unsigned corruptions=0;
    for(unsigned bit=0;bit<NV_BYTES*8;++bit){memcpy(flash,before,sizeof(flash));flash[bit/8]^=(uint8_t)(1u<<(bit%8));CHECK(nv_load(&io,actual)==0);++corruptions;}
    memset(flash,0x12,sizeof(flash));operations=0;CHECK(nv_load(&io,actual)==-1);CHECK(!nv_commit(&io,scratch,first,0) && operations==0);
    factory();first[0]=1;CHECK(!nv_commit(&io,scratch,first,0) && operations==0);first[0]=0;
    /* Sequence wrap, exact colours, and clear never resurrect the older profile. */
    factory();seed(NV_SLOT1,0xfffffffeu);seed(NV_SLOT0,0xffffffffu);CHECK(nv_commit(&io,scratch,second,0));CHECK(read_word(NV_SLOT1+12)==0);CHECK(nv_load(&io,actual)==1);CHECK(nv_commit(&io,scratch,second,1));CHECK(nv_load(&io,actual)==0);
    puts("PASS: exact RGB boot restoration; clear tombstone; redundant-save wear avoidance; 244 interruption/torn-write cases; 1920 corruption cases; sequence wrap; unknown storage refused. RAM-only flash.");
    CHECK(powercuts==244 && corruptions==1920);return 0;
}
