#ifndef LITRUN_FINGERPRINT_H
#define LITRUN_FINGERPRINT_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    char board_name[128];       /* e.g. "Raspberry Pi 5 Model B Rev 1.0" or "Generic x86_64" */
    char soc[64];               /* e.g. "BCM2712", "BCM2711", "RK3588", "x86_64" */
    char arch[32];              /* e.g. "aarch64", "x86_64", "riscv64" */
    char cpu_part[32];          /* e.g. "Cortex-A76", "Cortex-A72", "Cortex-A53", "x86_64" */
    int cores;                  /* Total online logical CPU cores */
    long ram_total_mb;          /* Total physical RAM in megabytes */
    long ram_avail_mb;          /* Currently available RAM in megabytes */
    long swap_total_mb;         /* Total swap space in megabytes */
    long swap_free_mb;          /* Free swap space in megabytes */
    float temp_c;               /* Current thermal sensor temperature in Celsius (-1.0 if unavailable) */

    /* ARM Vector / SIMD Extensions */
    int has_neon;               /* Advanced SIMD (NEON) */
    int has_dotprod;            /* Dot Product (ASIMDDP - sdot/udot) */
    int has_i8mm;               /* Int8 Matrix Multiply (I8MM) */
    int has_fp16;               /* Half precision floating point (FPHP) */
    int has_sve;                /* Scalable Vector Extension (SVE) */

    /* x86_64 Vector Extensions (when probed on x86 host) */
    int has_avx;
    int has_avx2;
    int has_avx512;
    int has_fma;

    /* NPU Detection */
    int has_rknn;               /* 1 if Rockchip NPU device (/dev/rknpu) exists */
    int has_nvdla;              /* 1 if NVIDIA NVDLA device exists */

    char profile_id[64];        /* Canonical profile, e.g. "rpi5-bcm2712-8gb-a76" */
} litrun_hw_profile_t;

/**
 * Probes the underlying embedded Linux hardware in <5 milliseconds.
 * Populates litrun_hw_profile_t struct.
 * Returns 0 on success, non-zero on critical failure.
 */
int litrun_probe_hardware(litrun_hw_profile_t *p);

/**
 * Returns a newly allocated JSON string representing the hardware profile.
 * The caller is responsible for calling free() on the returned pointer.
 */
char* litrun_probe_json(void);

/**
 * Derives the canonical profile ID string (e.g. "rpi5-bcm2712-8gb-a76")
 * into the target buffer.
 */
void litrun_derive_profile_id(const litrun_hw_profile_t *p, char *out_id, size_t max_len);

#ifdef __cplusplus
}
#endif

#endif /* LITRUN_FINGERPRINT_H */
