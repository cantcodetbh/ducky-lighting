/* Device-side reference component. Not integrated into, or flashable as, stock firmware. */
#ifndef DUCKY_HOST_RGB_H
#define DUCKY_HOST_RGB_H
#include <stddef.h>
#include <stdint.h>
#define DUCKY_RGB_CHANNELS 210
struct ducky_rgb_state {
    uint16_t frame[DUCKY_RGB_CHANNELS];
    uint8_t active;
};
/* Exactly eight bytes: D1 op row column R G B 00.
   op=1 set slot, op=2 fill (row/column zero), op=3 release (remaining bytes zero).
   On success returns 1; invalid packets return 0 without changing state.
   Caller owns initialization, complete USB reception and interrupt-safe publication. */
int ducky_rgb_command(struct ducky_rgb_state *state, const uint8_t *packet, size_t length);
#endif
