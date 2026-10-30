#include "host_rgb.h"
int ducky_rgb_command(struct ducky_rgb_state *state, const uint8_t *p, size_t n)
{
    unsigned start, end;
    if (n != 8 || p[0] != 0xd1 || p[7] != 0) return 0;
    if (p[1] == 1) {
        if (p[2] >= 5 || p[3] >= 14) return 0;
        start = ((unsigned)p[2] * 14 + p[3]) * 3;
        end = start + 3;
    } else if (p[1] == 2) {
        if (p[2] != 0 || p[3] != 0) return 0;
        start = 0;
        end = DUCKY_RGB_CHANNELS;
    } else if (p[1] == 3) {
        if (p[2] || p[3] || p[4] || p[5] || p[6]) return 0;
        state->active = 0;
        return 1;
    } else return 0;
    for (unsigned i = start; i < end; i += 3) {
        state->frame[i] = (uint16_t)((unsigned)p[4] * 257);
        state->frame[i+1] = (uint16_t)((unsigned)p[5] * 257);
        state->frame[i+2] = (uint16_t)((unsigned)p[6] * 257);
    }
    state->active = 1;
    return 1;
}
