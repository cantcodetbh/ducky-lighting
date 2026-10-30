#ifndef DUCKY_ONBOARD_HW_H
#define DUCKY_ONBOARD_HW_H
#include "onboard_store.h"
#define NV_RAM_DRIVER 0x20002d00u
#define NV_RAM_DRIVER_LIMIT 0x300u
int nv_ram_command(uint32_t command,uint32_t address,uint32_t value);
uint32_t nv_hw_read(uint32_t address);
int nv_hw_erase(uint32_t address);
int nv_hw_write(uint32_t address,uint32_t value);
extern uint8_t __ramfunc_start[],__ramfunc_end[];
#endif
