/* CHANNEL DEFAULT ARRAY — embed in OEFW fagci-mod source
 * Drop into radio/channels.c alongside gNoaaDefaultChannels[11]
 * Adjust the loader code in CHANNELS_CheckFreeChannels or wherever the
 * factory-reset copy path is, to iterate this array and call
 * CHANNELS_SaveChannel(i, &gUserDefaultChannels[i]) for i in 0..N-1.
 *
 * Frequency field: uint32 in 10 Hz units. 1455000 = 145.500 MHz.
 * gModulationType: 0=FM, 1=AM, 2=LSB, 3=USB.
 * bIsNarrow: 0=wide, 1=narrow.
 * Available: 1=slot in use.
 * Power/Scan/BCL bits stay 0 for default-coverage.
 */
#include "radio/channels.h"

static const ChannelInfo_t gUserDefaultChannels[USER_DEFAULT_CH_COUNT] = {
    /* BANK 1 — Seefunk FM 25kHz */
    [0]  = { .RX = { .Frequency = 1568000, .Code = 0, .CodeType = 0 },
             .TX = { .Frequency = 1568000, .Code = 0, .CodeType = 0 },
             .Available = 1, .gModulationType = 0, .bIsNarrow = 1,
             .IsInscanList = 0xFF,
             .Name = "Ch16   " },
    [1]  = { .RX = { .Frequency = 1566500, .Code = 0, .CodeType = 0 },
             .TX = { .Frequency = 1566500, .Code = 0, .CodeType = 0 },
             .Available = 1, .gModulationType = 0, .bIsNarrow = 1,
             .IsInscanList = 0xFF,
             .Name = "Ch13   " },
    /* ... fill in the remaining 46 entries ... */
};

/* In the boot/factory-reset code path, after the NOAA defaults are
 * handled, add:
 *
 *   for (uint16_t i = 0; i < ARRAY_SIZE(gUserDefaultChannels); i++) {
 *       if (gUserDefaultChannels[i].Available) {
 *           CHANNELS_SaveChannel(i + 100, &gUserDefaultChannels[i]);
 *       }
 *   }
 *
 * The +100 offset leaves the first 100 memory slots free for the user to
 * program additional channels on-device, if they ever do.
 */
