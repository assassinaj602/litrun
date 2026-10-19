#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "litrun.h"

const char* litrun_get_version(void) {
    return LITRUN_VERSION;
}

static void print_banner(void) {
    printf("⚡ litrun-probe v%s (Hardware Fingerprinter)\n", LITRUN_VERSION);
    printf("=====================================================\n");
}

int main(int argc, char **argv) {
    int json_mode = 0;
    int profile_only = 0;
    int time_probe = 0;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--json") == 0 || strcmp(argv[i], "-j") == 0) {
            json_mode = 1;
        } else if (strcmp(argv[i], "--profile") == 0 || strcmp(argv[i], "-p") == 0) {
            profile_only = 1;
        } else if (strcmp(argv[i], "--benchmark") == 0 || strcmp(argv[i], "-b") == 0) {
            time_probe = 1;
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            printf("Usage: litrun-probe [OPTIONS]\n\n"
                   "Options:\n"
                   "  -j, --json       Output raw JSON hardware profile\n"
                   "  -p, --profile    Output only the canonical profile ID\n"
                   "  -b, --benchmark  Measure and print probing latency\n"
                   "  -h, --help       Show this help message\n");
            return 0;
        }
    }

    struct timespec ts_start, ts_end;
    if (time_probe) {
        clock_gettime(CLOCK_MONOTONIC, &ts_start);
    }

    litrun_hw_profile_t p;
    if (litrun_probe_hardware(&p) != 0) {
        fprintf(stderr, "Error: Failed to probe hardware.\n");
        return 1;
    }

    double elapsed_ms = 0.0;
    if (time_probe) {
        clock_gettime(CLOCK_MONOTONIC, &ts_end);
        elapsed_ms = (ts_end.tv_sec - ts_start.tv_sec) * 1000.0 +
                     (ts_end.tv_nsec - ts_start.tv_nsec) / 1000000.0;
    }

    if (profile_only) {
        printf("%s\n", p.profile_id);
        return 0;
    }

    if (json_mode) {
        char *json = litrun_probe_json();
        if (json) {
            printf("%s", json);
            free(json);
        }
        return 0;
    }

    print_banner();
    printf("Canonical Profile: %s\n", p.profile_id);
    printf("Detected Board:    %s\n", p.board_name);
    printf("SoC / Processor:   %s (%s, %d cores)\n", p.soc, p.cpu_part, p.cores);
    printf("System Memory:     %ld MB Total / %ld MB Free\n", p.ram_total_mb, p.ram_avail_mb);
    if (p.temp_c > 0) {
        printf("Thermal Zone 0:    %.1f°C\n", p.temp_c);
    } else {
        printf("Thermal Zone 0:    N/A\n");
    }

    printf("Vector Extensions: ");
#if defined(__aarch64__)
    printf("[NEON: %s] [DotProd: %s] [FP16: %s] [I8MM: %s] [SVE: %s]\n",
           p.has_neon ? "YES" : "no",
           p.has_dotprod ? "YES" : "no",
           p.has_fp16 ? "YES" : "no",
           p.has_i8mm ? "YES" : "no",
           p.has_sve ? "YES" : "no");
#elif defined(__x86_64__)
    printf("[AVX: %s] [AVX2: %s] [AVX-512: %s] [FMA: %s]\n",
           p.has_avx ? "YES" : "no",
           p.has_avx2 ? "YES" : "no",
           p.has_avx512 ? "YES" : "no",
           p.has_fma ? "YES" : "no");
#else
    printf("Standard ISA\n");
#endif

    if (p.has_rknn) {
        printf("Hardware NPU:      Rockchip RKNN (/dev/rknpu detected)\n");
    } else if (p.has_nvdla) {
        printf("Hardware NPU:      NVIDIA NVDLA accelerator detected\n");
    }

    if (time_probe) {
        printf("Probe Latency:     %.3f ms\n", elapsed_ms);
    }

    return 0;
}
