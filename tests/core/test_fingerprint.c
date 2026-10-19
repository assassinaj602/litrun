#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "fingerprint.h"

int main(void) {
    printf("[TEST] Running C Fingerprint Probe...\n");

    litrun_hw_profile_t profile;
    int rc = litrun_probe_hardware(&profile);
    assert(rc == 0);

    /* Verify essential fields are populated */
    assert(strlen(profile.arch) > 0);
    assert(strlen(profile.board_name) > 0);
    assert(strlen(profile.soc) > 0);
    assert(strlen(profile.profile_id) > 0);
    assert(profile.cores > 0);
    assert(profile.ram_total_mb > 0);

    printf("  ✓ Detected Architecture: %s\n", profile.arch);
    printf("  ✓ Detected Board:        %s\n", profile.board_name);
    printf("  ✓ Detected SoC:          %s\n", profile.soc);
    printf("  ✓ Canonical Profile ID:  %s\n", profile.profile_id);
    printf("  ✓ Total RAM:             %ld MB\n", profile.ram_total_mb);
    printf("  ✓ Available RAM:         %ld MB\n", profile.ram_avail_mb);

    /* Test JSON generation */
    char *json = litrun_probe_json();
    assert(json != NULL);
    assert(strstr(json, "profile_id") != NULL);
    assert(strstr(json, "memory") != NULL);
    assert(strstr(json, "vector_extensions") != NULL);
    printf("  ✓ JSON serialization verified\n");
    free(json);

    /* Test custom profile ID derivation */
    litrun_hw_profile_t mock_pi5;
    memset(&mock_pi5, 0, sizeof(mock_pi5));
    strncpy(mock_pi5.board_name, "Raspberry Pi 5 Model B Rev 1.0", sizeof(mock_pi5.board_name));
    mock_pi5.ram_total_mb = 8192;
    strncpy(mock_pi5.cpu_part, "Cortex-A76", sizeof(mock_pi5.cpu_part));
    char id[64];
    litrun_derive_profile_id(&mock_pi5, id, sizeof(id));
    assert(strcmp(id, "rpi5-bcm2712-8gb-a76") == 0);
    printf("  ✓ Mock Raspberry Pi 5 profile ID correctly derived: %s\n", id);

    litrun_hw_profile_t mock_pi4;
    memset(&mock_pi4, 0, sizeof(mock_pi4));
    strncpy(mock_pi4.board_name, "Raspberry Pi 4 Model B Rev 1.4", sizeof(mock_pi4.board_name));
    mock_pi4.ram_total_mb = 4096;
    strncpy(mock_pi4.cpu_part, "Cortex-A72", sizeof(mock_pi4.cpu_part));
    litrun_derive_profile_id(&mock_pi4, id, sizeof(id));
    assert(strcmp(id, "rpi4-bcm2711-4gb-a72") == 0);
    printf("  ✓ Mock Raspberry Pi 4 profile ID correctly derived: %s\n", id);

    printf("[TEST] All C Fingerprint Tests Passed!\n");
    return 0;
}
