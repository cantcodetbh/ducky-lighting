/* Offline RAM-only peripheral/flash stubs for the pinned Nuvoton C parser. */
#ifndef DUCKY_REFERENCE_STUB_H
#define DUCKY_REFERENCE_STUB_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "reference_commands.h"
#define __STATIC_INLINE static inline
#define TRUE 1
#define FMC_FLASH_PAGE_SIZE 512u
#define FMC_APROM_BASE 0u
#define Config0 0x300000u
struct fake_sys {uint32_t PDID,RSTSTS;};
struct fake_fmc {uint32_t ISPCTL;};
struct fake_scb {uint32_t AIRCR;};
extern struct fake_sys fake_sys;
extern struct fake_fmc fake_fmc;
extern struct fake_scb fake_scb;
#define SYS (&fake_sys)
#define FMC (&fake_fmc)
#define SCB (&fake_scb)
static inline uint32_t inpw(const void *p) {uint32_t n;memcpy(&n,p,4);return n;}
static inline void outpw(void *p,uint32_t n) {memcpy(p,&n,4);}
static inline void outps(void *p,uint16_t n) {memcpy(p,&n,2);}
void ReadData(unsigned start,unsigned end,void *data);
void WriteData(unsigned start,unsigned end,const void *data);
void EraseAP(unsigned start,unsigned size);
void UpdateConfig(unsigned *data,unsigned *result);
void GetDataFlashInfo(uint32_t *addr,uint32_t *size);
void FMC_Erase_User(unsigned addr);
extern uint32_t bUpdateApromCmd,g_apromSize,g_dataFlashAddr,g_dataFlashSize;
extern uint8_t response_buff[64];
int ParseCmd(unsigned char *buffer,uint8_t len);
#endif
