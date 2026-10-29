/* Actual reference ParseCmd linked to RAM-only flash stubs. Never USB or MMIO. */
#include "protocol.h"
#include "reference_stub.h"
#include <stdio.h>
#include <stdlib.h>
#define CHECK(x) do {if(!(x)){fprintf(stderr,"FAIL line%d %s\n",__LINE__,#x);exit(1);}}while(0)
struct fake_sys fake_sys={0x01132e10,0};
struct fake_fmc fake_fmc={0};
struct fake_scb fake_scb={0};
static uint8_t aprom[131072],ldrom[4096];
static const uint32_t config[4]={0xfffffb7d,0x000fffff,0xffffff5a,0xffffffff};
static unsigned erase_calls,write_calls,config_writes,read_fault,swap_write;
void ReadData(unsigned start,unsigned end,void *data) {
    CHECK(end>=start);
    if(start==0x300000 && end==0x300010)memcpy(data,config,16);
    else {CHECK(end<=sizeof(aprom));memcpy(data,aprom+start,end-start);
        if(read_fault && end>start)((uint8_t *)data)[0]^=1;}
}
void WriteData(unsigned start,unsigned end,const void *data) {
    CHECK(end>=start && end<=65536);++write_calls;memcpy(aprom+start,data,end-start);
    if(swap_write && end-start>=2){uint8_t first=aprom[start];aprom[start]=aprom[start+1];aprom[start+1]=first;swap_write=0;}
}
void EraseAP(unsigned start,unsigned size) {
    CHECK(start==0 && size==sizeof(aprom));++erase_calls;memset(aprom+start,0xff,size);
}
void UpdateConfig(unsigned *data,unsigned *result) {(void)data;(void)result;++config_writes;CHECK(0);}
void GetDataFlashInfo(uint32_t *addr,uint32_t *size) {*addr=131072;*size=0;}
void FMC_Erase_User(unsigned addr) {(void)addr;CHECK(0);}
static int emit;
static void packet(const char *event,const uint8_t b[64]) {
    printf("{\"event\":\"%s\",\"body_hex\":\"",event);
    for(unsigned i=0;i<64;++i)printf("%02x",b[i]);puts("\"}");
}
struct scenario {unsigned calls,fault_step,fault;};
static int exchange(void *ctx,unsigned step,const uint8_t tx[64],uint8_t rx[64],size_t *n) {
    struct scenario *s=ctx;CHECK(step==s->calls++);
    uint8_t copy[64];memcpy(copy,tx,64);if(emit)packet("submitting",tx);
    if(step==s->fault_step && s->fault==1)return 0;
    read_fault=step==s->fault_step && s->fault==8;
    swap_write=step==s->fault_step && s->fault==9;
    CHECK(ParseCmd(copy,64)==0);read_fault=0;
    memcpy(rx,response_buff,64);*n=64;
    if(step==s->fault_step)switch(s->fault) {
        case 2:rx[0]^=1;break;
        case 3:rx[4]^=1;break;
        case 4:*n=63;break;
        case 5:*n=65;break;
        case 6:if(step==1)rx[8]^=1;else if(step==2)rx[8]^=2;else return 0;break;
        case 7:if(step>=3)return 0;break; /* ack lost AFTER erase/write */
    }
    if(emit)packet("received",rx);
    return 1;
}
static void reset_flash(void) {
    memset(aprom,0xa5,sizeof(aprom));memset(ldrom,0x5a,sizeof(ldrom));
    erase_calls=write_calls=config_writes=read_fault=swap_write=0;
    g_apromSize=sizeof(aprom);g_dataFlashAddr=sizeof(aprom);g_dataFlashSize=0;
    bUpdateApromCmd=0;
}
int main(int argc,char **argv) {
    /* Synthetic images, never manufacturer firmware. Different adjacent bytes exercise checksum collisions. */
    for(size_t i=0;i<sizeof(candidate_image);++i)candidate_image[i]=(uint8_t)(i*131+17);
    for(size_t i=0;i<sizeof(restore_image);++i)restore_image[i]=(uint8_t)(i*137+23);
    {struct job j=image_job(0);struct progress p;struct scenario ok={0,~0u,0};reset_flash();
      CHECK(program_aprom(&j,exchange,&ok,&p,1));CHECK(p.submitted==3 && !p.aprom_attempted && !erase_calls && !write_calls);}

    if(argc==2 && (!strcmp(argv[1],"--transcript-candidate") || !strcmp(argv[1],"--transcript-restore"))) {
        struct job j=image_job(!strcmp(argv[1],"--transcript-restore"));struct progress p;struct scenario ok={0,~0u,0};
        reset_flash();emit=1;CHECK(program_aprom(&j,exchange,&ok,&p,0));
        printf("{\"event\":\"program_result\",\"ok\":true,\"image_sha256\":\"%s\",\"submitted\":%u,\"acknowledged\":%u,\"bytes_acknowledged\":%zu,\"aprom_attempted\":true}\n",j.sha256,p.submitted,p.acknowledged,p.bytes_acknowledged);return 0;
    }
    CHECK(argc==1);
    unsigned negative=0;
    for(int restore=0;restore<2;++restore) {
        struct job j=image_job(restore);struct progress p;
        reset_flash();struct scenario ok={0,~0u,0};
        CHECK(program_aprom(&j,exchange,&ok,&p,0));
        CHECK(p.submitted==report_count(&j) && p.acknowledged==p.submitted);
        CHECK(p.bytes_acknowledged==j.length && p.aprom_attempted);
        CHECK(erase_calls==1 && write_calls==report_count(&j)-3 && config_writes==0);
        CHECK(memcmp(aprom,j.image,j.length)==0);
        for(size_t i=j.length;i<sizeof(aprom);++i)CHECK(aprom[i]==0xff);
        for(size_t i=0;i<sizeof(ldrom);++i)CHECK(ldrom[i]==0x5a);
        /* Walk all packets independently: only fixed command family, exact
           offset/size and zero unused tail; reconstruct the image byte-for-byte. */
        uint8_t reconstructed[65536]={0};size_t offset=0;
        for(unsigned step=0;step<report_count(&j);++step) {
            uint8_t tx[64];CHECK(fixed_request(&j,step,tx));
            CHECK(le32(tx)==(step==0?0xae:step==1?0xb1:step==2?0xa2:step==3?0xa0:0));
            if(step>=3) {
                unsigned header=step==3?16:8;size_t count=data_count(&j,step);
                if(step==3)CHECK(le32(tx+8)==0 && le32(tx+12)==j.length);
                memcpy(reconstructed+offset,tx+header,count);offset+=count;
                for(size_t i=header+count;i<64;++i)CHECK(tx[i]==0);
            }
        }
        CHECK(offset==j.length && memcmp(reconstructed,j.image,j.length)==0);
        /* Failures before the destructive command must leave the app intact;
           later failures stop exactly there and never retry/resume automatically. */
        unsigned positions[]={0,1,2,3,4,100,report_count(&j)-1};
        for(unsigned k=0;k<sizeof(positions)/sizeof(positions[0]);++k)for(unsigned fault=1;fault<=8;++fault) {
            unsigned step=positions[k];
            if((fault==6 && step!=1 && step!=2)||(fault==7 && step<3)||(fault==8 && step<3))continue;
            reset_flash();struct scenario s={0,step,fault};
            CHECK(!program_aprom(&j,exchange,&s,&p,0));CHECK(s.calls==step+1);
            if(step<3) {CHECK(!erase_calls && !write_calls && !p.aprom_attempted);CHECK(aprom[0]==0xa5);}
            else CHECK(p.aprom_attempted);
            CHECK(config_writes==0);++negative;
        }
        /* Deliberately corrupt two written bytes with an equal-sum swap.
           Reference reply validation succeeds while flash differs: prove the
           checksum is NOT full-image readback/hash verification. */
        reset_flash();struct scenario collision={0,3,9};
        CHECK(program_aprom(&j,exchange,&collision,&p,0));
        CHECK(memcmp(aprom,j.image,j.length)!=0);
        /* Lock/identity mismatch is not silently accepted. */
        fake_sys.PDID=0x01132e00;reset_flash();struct scenario wrong={0,~0u,0};
        CHECK(!program_aprom(&j,exchange,&wrong,&p,0));CHECK(wrong.calls==2 && !erase_calls);
        fake_sys.PDID=0x01132e10;
        uint8_t rx[64]={0};for(size_t n=0;n<64;++n)CHECK(!valid_reply(&j,0,rx,n));
        CHECK(!valid_reply(&j,0,rx,65));
        uint8_t tx[64];CHECK(!fixed_request(&j,report_count(&j),tx));
    }
    /* Wrong pointers/lengths cannot select arbitrary files through this core. */
    struct job bad={aprom,sizeof(aprom),"invalid"};struct progress p;struct scenario s={0,~0u,0};
    CHECK(!program_aprom(&bad,exchange,&s,&p,0) && s.calls==0);
    printf("PASS: candidate and manufacturer restore programmed byte-for-byte through pinned ParseCmd with RAM-only peripherals; %u failure scenarios; no config/LDROM writes; no retry; equal-sum corruption is demonstrably undetected.\n",negative);
    return 0;
}
