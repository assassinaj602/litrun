#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <unistd.h>
#include <sys/sysinfo.h>
#include <sys/stat.h>

#ifdef __linux__
#include <sys/auxv.h>
#endif

#include "fingerprint.h"

/* ARM64 HWCAP bit definitions fallback */
#ifndef HWCAP_ASIMD
#define HWCAP_ASIMD     (1UL << 1)
#endif
#ifndef HWCAP_FPHP
#define HWCAP_FPHP      (1UL << 9)
#endif
#ifndef HWCAP_ASIMDDP
#define HWCAP_ASIMDDP   (1UL << 20)
#endif
#ifndef HWCAP_SVE
#define HWCAP_SVE       (1UL << 22)
#endif
#ifndef HWCAP2_I8MM
#define HWCAP2_I8MM     (1UL << 13)
#endif
#ifndef HWCAP2_SVE2
#define HWCAP2_SVE2     (1UL << 1)
#endif

static void trim_trailing_whitespace(char *str) {
    if (!str) return;
    size_t len = strlen(str);
    while (len > 0 && (isspace((unsigned char)str[len - 1]) || str[len - 1] == '\0')) {
        str[len - 1] = '\0';
        len--;
    }
}

static void safe_copy(char *dst, const char *src, size_t dst_size) {
    if (!dst || dst_size == 0) return;
    if (!src) {
        dst[0] = '\0';
        return;
    }
    snprintf(dst, dst_size, "%s", src);
    dst[dst_size - 1] = '\0';
}

static int read_sysfs_string(const char *path, char *buf, size_t max_len) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    if (!fgets(buf, (int)max_len, f)) {
        fclose(f);
        return -1;
    }
    fclose(f);
    trim_trailing_whitespace(buf);
    return 0;
}

static int read_thermal_temp(float *out_temp) {
    char path[64];
    for (int zone = 0; zone < 5; zone++) {
        snprintf(path, sizeof(path), "/sys/class/thermal/thermal_zone%d/temp", zone);
        FILE *f = fopen(path, "r");
        if (f) {
            long temp_milli = 0;
            if (fscanf(f, "%ld", &temp_milli) == 1) {
                fclose(f);
                if (temp_milli > 0) {
                    *out_temp = (float)temp_milli / 1000.0f;
                    return 0;
                }
            }
            fclose(f);
        }
    }
    *out_temp = -1.0f;
    return -1;
}

static void read_accurate_meminfo(long *total_mb, long *avail_mb, long *swap_tot_mb, long *swap_free_mb) {
    FILE *f = fopen("/proc/meminfo", "r");
    if (!f) return;

    char line[256];
    long mem_total_kb = 0, mem_avail_kb = 0, mem_free_kb = 0;
    long swap_total_kb = 0, swap_free_kb = 0;

    while (fgets(line, sizeof(line), f)) {
        if (strncmp(line, "MemTotal:", 9) == 0) {
            sscanf(line + 9, "%ld", &mem_total_kb);
        } else if (strncmp(line, "MemAvailable:", 13) == 0) {
            sscanf(line + 13, "%ld", &mem_avail_kb);
        } else if (strncmp(line, "MemFree:", 8) == 0) {
            sscanf(line + 8, "%ld", &mem_free_kb);
        } else if (strncmp(line, "SwapTotal:", 10) == 0) {
            sscanf(line + 10, "%ld", &swap_total_kb);
        } else if (strncmp(line, "SwapFree:", 9) == 0) {
            sscanf(line + 9, "%ld", &swap_free_kb);
        }
    }
    fclose(f);

    if (mem_total_kb > 0) *total_mb = mem_total_kb / 1024;
    if (mem_avail_kb > 0) {
        *avail_mb = mem_avail_kb / 1024;
    } else if (mem_free_kb > 0) {
        *avail_mb = mem_free_kb / 1024;
    }
    if (swap_total_kb > 0) *swap_tot_mb = swap_total_kb / 1024;
    if (swap_free_kb > 0) *swap_free_mb = swap_free_kb / 1024;
}

static const char* map_arm_part_to_name(int part_num) {
    switch (part_num) {
        case 0xd03: return "Cortex-A53";
        case 0xd05: return "Cortex-A55";
        case 0xd07: return "Cortex-A57";
        case 0xd08: return "Cortex-A72";
        case 0xd09: return "Cortex-A73";
        case 0xd0a: return "Cortex-A75";
        case 0xd0b: return "Cortex-A76";
        case 0xd0c: return "Neoverse-N1";
        case 0xd0d: return "Cortex-A77";
        case 0xd0e: return "Cortex-A78";
        case 0xd40: return "Neoverse-V1";
        case 0xd41: return "Cortex-A78AE";
        case 0xd46: return "Cortex-A510";
        case 0xd47: return "Cortex-A710";
        case 0xd48: return "Cortex-X2";
        default: return NULL;
    }
}

int litrun_probe_hardware(litrun_hw_profile_t *p) {
    if (!p) return -1;
    memset(p, 0, sizeof(*p));

    /* 1. Architecture */
#if defined(__aarch64__)
    safe_copy(p->arch, "aarch64", sizeof(p->arch));
#elif defined(__x86_64__)
    safe_copy(p->arch, "x86_64", sizeof(p->arch));
#elif defined(__arm__)
    safe_copy(p->arch, "armv7l", sizeof(p->arch));
#elif defined(__riscv) && (__riscv_xlen == 64)
    safe_copy(p->arch, "riscv64", sizeof(p->arch));
#else
    safe_copy(p->arch, "unknown", sizeof(p->arch));
#endif

    /* 2. Board Identification (Devicetree / DMI / CPUInfo) */
    int found_board = 0;
    if (read_sysfs_string("/sys/firmware/devicetree/base/model", p->board_name, sizeof(p->board_name)) == 0) {
        found_board = 1;
    } else if (read_sysfs_string("/proc/device-tree/model", p->board_name, sizeof(p->board_name)) == 0) {
        found_board = 1;
    }

    /* Fallback on x86 to DMI sysfs */
    if (!found_board) {
        char vendor[64] = {0};
        char product[64] = {0};
        read_sysfs_string("/sys/class/dmi/id/sys_vendor", vendor, sizeof(vendor));
        read_sysfs_string("/sys/class/dmi/id/product_name", product, sizeof(product));
        if (product[0] != '\0') {
            if (vendor[0] != '\0') {
                snprintf(p->board_name, sizeof(p->board_name), "%s %s", vendor, product);
            } else {
                snprintf(p->board_name, sizeof(p->board_name), "%s", product);
            }
            found_board = 1;
        }
    }

    /* 3. Parse /proc/cpuinfo for SoC, Part Number, and Cores */
    FILE *f_cpu = fopen("/proc/cpuinfo", "r");
    int core_count = 0;
    int max_arm_part = 0;
    char cpu_hardware[64] = {0};
    char cpu_model_name[128] = {0};

    if (f_cpu) {
        char line[256];
        while (fgets(line, sizeof(line), f_cpu)) {
            if (strncmp(line, "processor", 9) == 0) {
                core_count++;
            } else if (strncmp(line, "CPU part", 8) == 0) {
                char *colon = strchr(line, ':');
                if (colon) {
                    int part = (int)strtol(colon + 1, NULL, 0);
                    if (part > max_arm_part) {
                        max_arm_part = part;
                    }
                }
            } else if (strncmp(line, "Hardware", 8) == 0) {
                char *colon = strchr(line, ':');
                if (colon) {
                    safe_copy(cpu_hardware, colon + 1, sizeof(cpu_hardware));
                    trim_trailing_whitespace(cpu_hardware);
                }
            } else if (strncmp(line, "model name", 10) == 0 && cpu_model_name[0] == '\0') {
                char *colon = strchr(line, ':');
                if (colon) {
                    safe_copy(cpu_model_name, colon + 1, sizeof(cpu_model_name));
                    trim_trailing_whitespace(cpu_model_name);
                }
            }
        }
        fclose(f_cpu);
    }

    p->cores = (core_count > 0) ? core_count : (int)sysconf(_SC_NPROCESSORS_ONLN);

    /* Determine CPU Part name */
    if (max_arm_part > 0) {
        const char *name = map_arm_part_to_name(max_arm_part);
        if (name) {
            safe_copy(p->cpu_part, name, sizeof(p->cpu_part));
        } else {
            snprintf(p->cpu_part, sizeof(p->cpu_part), "ARM-0x%03x", max_arm_part);
        }
    } else if (cpu_model_name[0] != '\0') {
        safe_copy(p->cpu_part, cpu_model_name, sizeof(p->cpu_part));
    } else {
        safe_copy(p->cpu_part, p->arch, sizeof(p->cpu_part));
    }

    /* Board name fallback */
    if (!found_board) {
        if (cpu_model_name[0] != '\0') {
            snprintf(p->board_name, sizeof(p->board_name), "%s System", cpu_model_name);
        } else {
            snprintf(p->board_name, sizeof(p->board_name), "Generic %s Host", p->arch);
        }
    }

    /* Determine SoC model name */
    if (strstr(p->board_name, "Raspberry Pi 5") != NULL) {
        safe_copy(p->soc, "BCM2712", sizeof(p->soc));
        if (p->cpu_part[0] == '\0') safe_copy(p->cpu_part, "Cortex-A76", sizeof(p->cpu_part));
    } else if (strstr(p->board_name, "Raspberry Pi 4") != NULL || strstr(p->board_name, "Raspberry Pi 400") != NULL) {
        safe_copy(p->soc, "BCM2711", sizeof(p->soc));
        if (p->cpu_part[0] == '\0') safe_copy(p->cpu_part, "Cortex-A72", sizeof(p->cpu_part));
    } else if (strstr(p->board_name, "Raspberry Pi 3") != NULL || strstr(p->board_name, "Zero 2") != NULL) {
        safe_copy(p->soc, "BCM2837", sizeof(p->soc));
        if (p->cpu_part[0] == '\0') safe_copy(p->cpu_part, "Cortex-A53", sizeof(p->cpu_part));
    } else if (strstr(p->board_name, "Orange Pi 5") != NULL || strstr(p->board_name, "Rock 5") != NULL ||
               strstr(cpu_hardware, "RK3588") != NULL) {
        safe_copy(p->soc, "RK3588", sizeof(p->soc));
    } else if (strstr(p->board_name, "Jetson") != NULL) {
        safe_copy(p->soc, "Tegra-Orin", sizeof(p->soc));
    } else if (cpu_hardware[0] != '\0') {
        safe_copy(p->soc, cpu_hardware, sizeof(p->soc));
    } else if (strcmp(p->arch, "x86_64") == 0) {
        safe_copy(p->soc, "x86_64", sizeof(p->soc));
    } else {
        snprintf(p->soc, sizeof(p->soc), "%s-SoC", p->arch);
    }

    /* 4. Runtime ISA Vector Probing via getauxval or builtin */
#if defined(__aarch64__) && defined(__linux__)
    unsigned long hwcap = getauxval(AT_HWCAP);
    unsigned long hwcap2 = getauxval(AT_HWCAP2);

    p->has_neon    = (hwcap  & HWCAP_ASIMD)   ? 1 : 0;
    p->has_dotprod = (hwcap  & HWCAP_ASIMDDP) ? 1 : 0;
    p->has_fp16    = (hwcap  & HWCAP_FPHP)    ? 1 : 0;
    p->has_sve     = (hwcap  & HWCAP_SVE)     ? 1 : 0;
    p->has_i8mm    = (hwcap2 & HWCAP2_I8MM)   ? 1 : 0;
#elif defined(__x86_64__)
    #if defined(__GNUC__) || defined(__clang__)
    p->has_avx    = __builtin_cpu_supports("avx") ? 1 : 0;
    p->has_avx2   = __builtin_cpu_supports("avx2") ? 1 : 0;
    p->has_avx512 = __builtin_cpu_supports("avx512f") ? 1 : 0;
    p->has_fma    = __builtin_cpu_supports("fma") ? 1 : 0;
    #endif
#endif

    /* 5. Memory Query */
    struct sysinfo si;
    if (sysinfo(&si) == 0) {
        p->ram_total_mb = (long)((si.totalram * si.mem_unit) / (1024 * 1024));
        p->ram_avail_mb = (long)((si.freeram * si.mem_unit) / (1024 * 1024));
        p->swap_total_mb = (long)((si.totalswap * si.mem_unit) / (1024 * 1024));
        p->swap_free_mb = (long)((si.freeswap * si.mem_unit) / (1024 * 1024));
    }
    /* Refine with /proc/meminfo MemAvailable */
    read_accurate_meminfo(&p->ram_total_mb, &p->ram_avail_mb, &p->swap_total_mb, &p->swap_free_mb);

    /* 6. Thermals */
    read_thermal_temp(&p->temp_c);

    /* 7. NPU Device Nodes */
    struct stat st;
    p->has_rknn = (stat("/dev/rknpu", &st) == 0 || stat("/dev/rknpu0", &st) == 0) ? 1 : 0;
    p->has_nvdla = (stat("/dev/nvhost-nvdla0", &st) == 0 || stat("/dev/nvhost-ctrl-nvdla", &st) == 0) ? 1 : 0;

    /* 8. Construct Canonical Profile ID */
    litrun_derive_profile_id(p, p->profile_id, sizeof(p->profile_id));

    return 0;
}

void litrun_derive_profile_id(const litrun_hw_profile_t *p, char *out_id, size_t max_len) {
    if (!p || !out_id || max_len == 0) return;

    int ram_gb = (int)((p->ram_total_mb + 512) / 1024);
    if (ram_gb < 1) ram_gb = 1;

    if (strstr(p->board_name, "Raspberry Pi 5") != NULL) {
        snprintf(out_id, max_len, "rpi5-bcm2712-%dgb-a76", ram_gb);
    } else if (strstr(p->board_name, "Raspberry Pi 4") != NULL) {
        snprintf(out_id, max_len, "rpi4-bcm2711-%dgb-a72", ram_gb);
    } else if (strstr(p->board_name, "Orange Pi 5") != NULL || strstr(p->soc, "RK3588") != NULL) {
        snprintf(out_id, max_len, "opi5-rk3588-%dgb-a76", ram_gb);
    } else if (strstr(p->board_name, "Jetson") != NULL) {
        snprintf(out_id, max_len, "jetson-orin-%dgb", ram_gb);
    } else if (strcmp(p->arch, "x86_64") == 0) {
        if (p->has_avx512) {
            snprintf(out_id, max_len, "x86_64-avx512-%dgb", ram_gb);
        } else if (p->has_avx2) {
            snprintf(out_id, max_len, "x86_64-avx2-%dgb", ram_gb);
        } else {
            snprintf(out_id, max_len, "x86_64-generic-%dgb", ram_gb);
        }
    } else {
        snprintf(out_id, max_len, "%s-%s-%dgb", p->arch, p->soc, ram_gb);
    }

    /* Convert to lowercase and sanitize */
    for (size_t i = 0; i < strlen(out_id); i++) {
        out_id[i] = (char)tolower((unsigned char)out_id[i]);
        if (out_id[i] == ' ' || out_id[i] == '_') {
            out_id[i] = '-';
        }
    }
}

char* litrun_probe_json(void) {
    litrun_hw_profile_t p;
    if (litrun_probe_hardware(&p) != 0) {
        return NULL;
    }

    char *json = (char*)malloc(2048);
    if (!json) return NULL;

    snprintf(json, 2048,
        "{\n"
        "  \"profile_id\": \"%s\",\n"
        "  \"board_name\": \"%s\",\n"
        "  \"soc\": \"%s\",\n"
        "  \"arch\": \"%s\",\n"
        "  \"cpu_part\": \"%s\",\n"
        "  \"cores\": %d,\n"
        "  \"memory\": {\n"
        "    \"total_mb\": %ld,\n"
        "    \"avail_mb\": %ld,\n"
        "    \"swap_total_mb\": %ld,\n"
        "    \"swap_free_mb\": %ld\n"
        "  },\n"
        "  \"thermals\": {\n"
        "    \"temp_c\": %.1f\n"
        "  },\n"
        "  \"vector_extensions\": {\n"
        "    \"neon\": %s,\n"
        "    \"dotprod\": %s,\n"
        "    \"i8mm\": %s,\n"
        "    \"fp16\": %s,\n"
        "    \"sve\": %s,\n"
        "    \"avx\": %s,\n"
        "    \"avx2\": %s,\n"
        "    \"avx512\": %s,\n"
        "    \"fma\": %s\n"
        "  },\n"
        "  \"accelerators\": {\n"
        "    \"rknn\": %s,\n"
        "    \"nvdla\": %s\n"
        "  }\n"
        "}\n",
        p.profile_id,
        p.board_name,
        p.soc,
        p.arch,
        p.cpu_part,
        p.cores,
        p.ram_total_mb,
        p.ram_avail_mb,
        p.swap_total_mb,
        p.swap_free_mb,
        p.temp_c,
        p.has_neon ? "true" : "false",
        p.has_dotprod ? "true" : "false",
        p.has_i8mm ? "true" : "false",
        p.has_fp16 ? "true" : "false",
        p.has_sve ? "true" : "false",
        p.has_avx ? "true" : "false",
        p.has_avx2 ? "true" : "false",
        p.has_avx512 ? "true" : "false",
        p.has_fma ? "true" : "false",
        p.has_rknn ? "true" : "false",
        p.has_nvdla ? "true" : "false"
    );

    return json;
}
