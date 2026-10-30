#ifndef DUCKY_ONBOARD_STORE_H
#define DUCKY_ONBOARD_STORE_H
#include <stdint.h>
#include <stddef.h>
#define NV_SLOT0 0x0001fc00u
#define NV_SLOT1 0x0001fe00u
#define NV_PAGE 512u
#define NV_WORDS 60u
#define NV_BYTES (NV_WORDS*4u)
#define NV_COMMIT_OFFSET 236u
#define NV_CRC_OFFSET 232u
#define NV_FRAME_OFFSET 20u
#define NV_RGB_BYTES 210u
#define NV_MAGIC0 0x334b5544u
#define NV_MAGIC1 0x50524759u
#define NV_COMMIT 0x54494d43u
struct nv_io {
    uint32_t (*read)(uint32_t address);
    int (*erase)(uint32_t address);
    int (*write)(uint32_t address,uint32_t value);
};
/* load: -1 = no valid journal, 0 = tombstone, 1 = saved colours. Never writes. */
int nv_load(const struct nv_io *io,uint16_t frame[210]);
/* scratch must have NV_WORDS words. Commit writes only the inactive reserved page. */
int nv_commit(const struct nv_io *io,uint32_t scratch[NV_WORDS],const uint16_t frame[210],int clear);
uint32_t nv_crc_bytes(const uint8_t *data,size_t length);
#endif
