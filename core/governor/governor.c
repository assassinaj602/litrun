#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/sysinfo.h>

#include "governor.h"

static int read_long_from_file(const char *path, long *out_val) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;
    char buf[64];
    if (!fgets(buf, sizeof(buf), f)) {
        fclose(f);
        return -1;
    }
    fclose(f);
    if (strncmp(buf, "max", 3) == 0) {
        *out_val = -1; /* unlimited */
        return 0;
    }
    *out_val = strtol(buf, NULL, 10);
    return 0;
}

static void read_governor_meminfo(long *total_mb, long *avail_mb, long *swap_tot_mb, long *swap_free_mb) {
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

static float read_governor_temp(void) {
    char path[64];
    for (int zone = 0; zone < 5; zone++) {
        snprintf(path, sizeof(path), "/sys/class/thermal/thermal_zone%d/temp", zone);
        FILE *f = fopen(path, "r");
        if (f) {
            long temp_milli = 0;
            if (fscanf(f, "%ld", &temp_milli) == 1) {
                fclose(f);
                if (temp_milli > 0) {
                    return (float)temp_milli / 1000.0f;
                }
            }
            fclose(f);
        }
    }
    return -1.0f;
}

int litrun_governor_poll(litrun_governor_status_t *gov) {
    if (!gov) return -1;
    memset(gov, 0, sizeof(*gov));

    /* 1. cgroup Inspection */
    long cgroup_curr = 0, cgroup_max = -1;
    if (read_long_from_file("/sys/fs/cgroup/memory.current", &cgroup_curr) == 0) {
        gov->cgroup_version = 2;
        gov->cgroup_mem_usage_mb = cgroup_curr / (1024 * 1024);
        if (read_long_from_file("/sys/fs/cgroup/memory.max", &cgroup_max) == 0) {
            gov->cgroup_mem_limit_mb = (cgroup_max > 0) ? cgroup_max / (1024 * 1024) : -1;
        }
    } else if (read_long_from_file("/sys/fs/cgroup/memory/memory.usage_in_bytes", &cgroup_curr) == 0) {
        gov->cgroup_version = 1;
        gov->cgroup_mem_usage_mb = cgroup_curr / (1024 * 1024);
        if (read_long_from_file("/sys/fs/cgroup/memory/memory.limit_in_bytes", &cgroup_max) == 0) {
            /* Large numbers indicate unlimited */
            if (cgroup_max > 0 && cgroup_max < (1L << 60)) {
                gov->cgroup_mem_limit_mb = cgroup_max / (1024 * 1024);
            } else {
                gov->cgroup_mem_limit_mb = -1;
            }
        }
    } else {
        gov->cgroup_version = 0;
        gov->cgroup_mem_usage_mb = -1;
        gov->cgroup_mem_limit_mb = -1;
    }

    /* 2. System Memory Query */
    struct sysinfo si;
    if (sysinfo(&si) == 0) {
        gov->ram_total_mb = (long)((si.totalram * si.mem_unit) / (1024 * 1024));
        gov->ram_avail_mb = (long)((si.freeram * si.mem_unit) / (1024 * 1024));
        gov->swap_total_mb = (long)((si.totalswap * si.mem_unit) / (1024 * 1024));
        gov->swap_free_mb = (long)((si.freeswap * si.mem_unit) / (1024 * 1024));
    }
    read_governor_meminfo(&gov->ram_total_mb, &gov->ram_avail_mb, &gov->swap_total_mb, &gov->swap_free_mb);

    /* 3. Thermals */
    gov->temp_c = read_governor_temp();
    if (gov->temp_c >= LITRUN_THERMAL_CRIT_TEMP_C) {
        gov->thermal_state = 2; /* Critical */
    } else if (gov->temp_c >= LITRUN_THERMAL_WARN_TEMP_C) {
        gov->thermal_state = 1; /* Warm */
    } else {
        gov->thermal_state = 0; /* Nominal */
    }

    /* 4. CPU Cores & Thread Recommendation */
    gov->online_cores = (int)sysconf(_SC_NPROCESSORS_ONLN);
    if (gov->online_cores <= 0) gov->online_cores = 4;

    if (gov->thermal_state == 2) {
        /* Under critical thermal conditions, shed threads to prevent emergency throttling */
        gov->recommended_threads = (gov->online_cores > 2) ? (gov->online_cores / 2) : 1;
    } else if (gov->thermal_state == 1) {
        /* Slightly warm, leave at least 1 core for cooling / OS */
        gov->recommended_threads = (gov->online_cores > 2) ? (gov->online_cores - 1) : gov->online_cores;
    } else {
        /* Nominal: If 4 or more cores, use N - 1 cores or all cores */
        gov->recommended_threads = (gov->online_cores >= 4) ? (gov->online_cores - 1) : gov->online_cores;
    }

    return 0;
}

int litrun_governor_check_envelope(
    long model_size_mb,
    int context_length,
    float kv_bytes_per_token,
    long *out_ram_needed_mb,
    char *out_reason,
    size_t reason_len
) {
    litrun_governor_status_t gov;
    if (litrun_governor_poll(&gov) != 0) {
        if (out_reason && reason_len > 0) {
            snprintf(out_reason, reason_len, "Failed to poll system resources");
        }
        return -1;
    }

    /* Calculate KV cache footprint */
    long kv_cache_mb = (long)(((double)context_length * (double)kv_bytes_per_token) / (1024.0 * 1024.0));
    long ram_needed = model_size_mb + kv_cache_mb + LITRUN_OVERHEAD_MB;

    if (out_ram_needed_mb) {
        *out_ram_needed_mb = ram_needed;
    }

    /* Effective available RAM: cgroup limit vs OS available RAM */
    long effective_avail_mb = gov.ram_avail_mb;
    if (gov.cgroup_mem_limit_mb > 0 && gov.cgroup_mem_usage_mb >= 0) {
        long cgroup_headroom = gov.cgroup_mem_limit_mb - gov.cgroup_mem_usage_mb;
        if (cgroup_headroom < effective_avail_mb) {
            effective_avail_mb = (cgroup_headroom > 0) ? cgroup_headroom : 0;
        }
    }

    long safe_ceiling_mb = (long)((float)effective_avail_mb * LITRUN_RAM_SAFETY_RATIO);

    if (ram_needed > effective_avail_mb) {
        if (out_reason && reason_len > 0) {
            snprintf(out_reason, reason_len,
                     "OOM RISK: Required %ldMB exceeds total available memory (%ldMB). Execution blocked.",
                     ram_needed, effective_avail_mb);
        }
        return -1;
    }

    if (ram_needed > safe_ceiling_mb) {
        if (out_reason && reason_len > 0) {
            snprintf(out_reason, reason_len,
                     "TIGHT MEMORY: Required %ldMB exceeds 85%% safety ceiling (%ldMB / %ldMB free). Downgrade recommended.",
                     ram_needed, safe_ceiling_mb, effective_avail_mb);
        }
        return 0;
    }

    if (out_reason && reason_len > 0) {
        int pct = (effective_avail_mb > 0) ? (int)((ram_needed * 100) / effective_avail_mb) : 0;
        snprintf(out_reason, reason_len,
                 "PASS: %ldMB required out of %ldMB available (%d%% headroom utilized).",
                 ram_needed, effective_avail_mb, pct);
    }
    return 1;
}

char* litrun_governor_json(void) {
    litrun_governor_status_t gov;
    if (litrun_governor_poll(&gov) != 0) {
        return NULL;
    }

    char *json = (char*)malloc(1024);
    if (!json) return NULL;

    const char *state_str = "nominal";
    if (gov.thermal_state == 1) state_str = "warm";
    else if (gov.thermal_state == 2) state_str = "critical_throttled";

    snprintf(json, 1024,
        "{\n"
        "  \"cgroup\": {\n"
        "    \"version\": %d,\n"
        "    \"usage_mb\": %ld,\n"
        "    \"limit_mb\": %ld\n"
        "  },\n"
        "  \"memory\": {\n"
        "    \"total_mb\": %ld,\n"
        "    \"avail_mb\": %ld,\n"
        "    \"swap_total_mb\": %ld,\n"
        "    \"swap_free_mb\": %ld\n"
        "  },\n"
        "  \"thermals\": {\n"
        "    \"temp_c\": %.1f,\n"
        "    \"state\": \"%s\"\n"
        "  },\n"
        "  \"threads\": {\n"
        "    \"online_cores\": %d,\n"
        "    \"recommended\": %d\n"
        "  }\n"
        "}\n",
        gov.cgroup_version,
        gov.cgroup_mem_usage_mb,
        gov.cgroup_mem_limit_mb,
        gov.ram_total_mb,
        gov.ram_avail_mb,
        gov.swap_total_mb,
        gov.swap_free_mb,
        gov.temp_c,
        state_str,
        gov.online_cores,
        gov.recommended_threads
    );

    return json;
}

