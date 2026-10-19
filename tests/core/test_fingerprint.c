#define _GNU_SOURCE
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

    /* Test Real Physical Raspberry Pi 5 Fixture */
    setenv("LITRUN_SYSROOT", "../tests/fixtures/rpi5", 1);
    litrun_hw_profile_t pi5_prof;
    rc = litrun_probe_hardware(&pi5_prof);
    assert(rc == 0);
    assert(strcmp(pi5_prof.soc, "BCM2712") == 0);
    assert(strcmp(pi5_prof.cpu_part, "Cortex-A76") == 0);
    assert(strcmp(pi5_prof.profile_id, "rpi5-bcm2712-8gb-a76") == 0);
    assert(pi5_prof.has_neon == 1);
    assert(pi5_prof.has_dotprod == 1);
    assert(pi5_prof.has_fp16 == 1);
    assert(pi5_prof.cores == 4);
    printf("  ✓ Real Raspberry Pi 5 Hardware Dump Verified: %s (Cortex-A76 DotProd+FP16)\n", pi5_prof.profile_id);

    /* Test Real Physical Raspberry Pi 4 Fixture */
    setenv("LITRUN_SYSROOT", "../tests/fixtures/rpi4", 1);
    litrun_hw_profile_t pi4_prof;
    rc = litrun_probe_hardware(&pi4_prof);
    assert(rc == 0);
    assert(strcmp(pi4_prof.soc, "BCM2711") == 0);
    assert(strcmp(pi4_prof.cpu_part, "Cortex-A72") == 0);
    assert(strcmp(pi4_prof.profile_id, "rpi4-bcm2711-4gb-a72") == 0);
    assert(pi4_prof.has_neon == 1);
    assert(pi4_prof.has_dotprod == 0);
    assert(pi4_prof.cores == 4);
    printf("  ✓ Real Raspberry Pi 4 Hardware Dump Verified: %s (Cortex-A72 NEON)\n", pi4_prof.profile_id);

    /* Test Real Orange Pi 5 (RK3588) Fixture */
    setenv("LITRUN_SYSROOT", "../tests/fixtures/opi5", 1);
    litrun_hw_profile_t opi5_prof;
    rc = litrun_probe_hardware(&opi5_prof);
    assert(rc == 0);
    assert(strcmp(opi5_prof.soc, "RK3588") == 0);
    assert(strcmp(opi5_prof.cpu_part, "Cortex-A76") == 0);
    assert(strcmp(opi5_prof.profile_id, "opi5-rk3588-16gb-a76") == 0);
    assert(opi5_prof.has_neon == 1);
    assert(opi5_prof.has_dotprod == 1);
    assert(opi5_prof.cores == 8);
    printf("  ✓ Real Orange Pi 5 (RK3588) Hardware Dump Verified: %s (Octa-core 16GB)\n", opi5_prof.profile_id);

    unsetenv("LITRUN_SYSROOT");

    printf("[TEST] All C Fingerprint Tests Passed!\n");
    return 0;
}

