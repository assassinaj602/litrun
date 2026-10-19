#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "governor.h"

int main(void) {
    printf("[TEST] Running C Governor Tests...\n");

    litrun_governor_status_t gov;
    int rc = litrun_governor_poll(&gov);
    assert(rc == 0);
    assert(gov.ram_total_mb > 0);
    assert(gov.online_cores > 0);
    assert(gov.recommended_threads > 0);

    printf("  ✓ Governor Polled: %ld MB Total RAM, %ld MB Avail RAM\n",
           gov.ram_total_mb, gov.ram_avail_mb);
    printf("  ✓ Thermal State: %d, Online Cores: %d, Recommended Threads: %d\n",
           gov.thermal_state, gov.online_cores, gov.recommended_threads);

    /* Test RAM Envelope check for small model */
    long ram_needed = 0;
    char reason[256];
    /* 397MB model, 2048 context length, ~0.08MB KV per token */
    int res = litrun_governor_check_envelope(397, 2048, 80.0f, &ram_needed, reason, sizeof(reason));
    printf("  ✓ Small Model Check: res=%d, ram_needed=%ld MB, reason='%s'\n", res, ram_needed, reason);
    assert(ram_needed > 397);
    assert(strlen(reason) > 0);

    /* Test RAM Envelope check for an impossibly huge 1000GB model */
    res = litrun_governor_check_envelope(1000000, 2048, 80.0f, &ram_needed, reason, sizeof(reason));
    assert(res == -1);
    printf("  ✓ Huge Model Check (Must Block): res=%d, reason='%s'\n", res, reason);

    /* Test JSON serialization */
    char *json = litrun_governor_json();
    assert(json != NULL);
    assert(strstr(json, "cgroup") != NULL);
    assert(strstr(json, "memory") != NULL);
    assert(strstr(json, "thermals") != NULL);
    printf("  ✓ Governor JSON serialization verified\n");
    free(json);

    printf("[TEST] All C Governor Tests Passed!\n");
    return 0;
}

