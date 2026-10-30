#include "onboard_store.h"
static uint32_t crc_byte(uint32_t crc,uint8_t value) {
    crc^=value;
    for(unsigned bit=0;bit<8;++bit)crc=(crc>>1)^((0u-(crc&1u))&0xedb88320u);
    return crc;
}
uint32_t nv_crc_bytes(const uint8_t *data,size_t length) {
    uint32_t crc=0xffffffffu;
    for(size_t i=0;i<length;++i)crc=crc_byte(crc,data[i]);
    return ~crc;
}
static uint8_t read_byte(const struct nv_io *io,uint32_t address) {
    return (uint8_t)(io->read(address&~3u)>>((address&3u)*8));
}
static int valid(const struct nv_io *io,uint32_t slot) {
    if(io->read(slot)!=NV_MAGIC0 || io->read(slot+4)!=NV_MAGIC1 || io->read(slot+8)!=1u
       || io->read(slot+16)>1u || io->read(slot+NV_COMMIT_OFFSET)!=NV_COMMIT)return 0;
    uint32_t crc=0xffffffffu;
    for(unsigned i=0;i<NV_CRC_OFFSET;++i)crc=crc_byte(crc,read_byte(io,slot+i));
    return ~crc==io->read(slot+NV_CRC_OFFSET);
}
static uint32_t latest(const struct nv_io *io) {
    int a=valid(io,NV_SLOT0),b=valid(io,NV_SLOT1);
    if(!a)return b?NV_SLOT1:0;
    if(!b)return NV_SLOT0;
    return (int32_t)(io->read(NV_SLOT1+12)-io->read(NV_SLOT0+12))>0?NV_SLOT1:NV_SLOT0;
}
int nv_load(const struct nv_io *io,uint16_t frame[210]) {
    uint32_t slot=latest(io);
    if(!slot)return -1;
    if(io->read(slot+16)==0)return 0;
    for(unsigned i=0;i<210;++i)frame[i]=(uint16_t)((unsigned)read_byte(io,slot+NV_FRAME_OFFSET+i)*257u);
    return 1;
}
int nv_commit(const struct nv_io *io,uint32_t scratch[NV_WORDS],const uint16_t frame[210],int clear) {
    uint32_t old=latest(io);
    /* Both pages belong to this schema only after installation seeds a valid tombstone.
       Unknown/invalid storage is never initialized or erased by a save request. */
    if(!old || (clear!=0 && clear!=1))return 0;
    if(!clear)for(unsigned i=0;i<210;++i)if(frame[i]!=(uint16_t)((frame[i]>>8)*257u))return 0;
    int same=io->read(old+16)==(clear?0u:1u);
    if(same && !clear)for(unsigned i=0;i<210;++i)
        if(read_byte(io,old+NV_FRAME_OFFSET+i)!=(uint8_t)(frame[i]>>8)){same=0;break;}
    if(same)return 1; /* identical saves cause no erase/program wear */
    uint8_t *record=(uint8_t *)scratch;
    for(unsigned i=0;i<NV_WORDS;++i)scratch[i]=0xffffffffu;
    scratch[0]=NV_MAGIC0;scratch[1]=NV_MAGIC1;scratch[2]=1;
    scratch[3]=io->read(old+12)+1u;scratch[4]=clear?0u:1u;
    for(unsigned i=0;i<210;++i)record[NV_FRAME_OFFSET+i]=clear?0:(uint8_t)(frame[i]>>8);
    scratch[NV_CRC_OFFSET/4]=nv_crc_bytes(record,NV_CRC_OFFSET);
    uint32_t target=old==NV_SLOT0?NV_SLOT1:NV_SLOT0;
    if(!io->erase(target))return 0;
    for(unsigned i=0;i<NV_COMMIT_OFFSET/4;++i)
        if(!io->write(target+i*4,scratch[i]))return 0;
    /* Verify all data and CRC before programming the final commit word. */
    for(unsigned i=0;i<NV_COMMIT_OFFSET/4;++i)if(io->read(target+i*4)!=scratch[i])return 0;
    if(!io->write(target+NV_COMMIT_OFFSET,NV_COMMIT))return 0;
    return valid(io,target) && latest(io)==target;
}
