#ifndef LITRUN_GOVERNOR_H
#define LITRUN_GOVERNOR_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LITRUN_THERMAL_WARN_TEMP_C   75.0f
#define LITRUN_THERMAL_CRIT_TEMP_C   80.0f
#define LITRUN_RAM_SAFETY_RATIO      0.85f  /* Keep 15% RAM headroom */
#define LITRUN_OVERHEAD_MB           250    /* Runtime overhead */

typedef struct {
    int cgroup_version;             /* 0: not in cgroup, 1: cgroup v1, 2: cgroup v2 */
    long cgroup_mem_usage_mb;       /* Current cgroup memory usage (-1 if n/a) */
    long cgroup_mem_limit_mb;       /* Memory limit (-1 if unlimited) */

    long ram_total_mb;              /* Physical RAM */
    long ram_avail_mb;              /* Available RAM */
    long swap_total_mb;             /* Swap total */
    long swap_free_mb;              /* Swap free */

    float temp_c;                   /* Current SoC temperature */
    int thermal_state;              /* 0: Nominal, 1: Warm, 2: Critical / Throttled */
    int online_cores;               /* Total cores available */
    int recommended_threads;        /* Dynamic thread allocation recommendation */
} litrun_governor_status_t;

/**
 * Polls active resource consumption, cgroup boundaries, and SoC thermals.
 * Returns 0 on success.
 */
int litrun_governor_poll(litrun_governor_status_t *gov);

/**
 * Calculates whether a proposed model execution fits inside the available RAM envelope.
 * Formula: RAM_needed = model_size_mb + (context_length * kv_bytes_per_token / (1024 * 1024)) + LITRUN_OVERHEAD_MB
 *
 * Returns:
 *   1 if execution is safe.
 *   0 if execution exceeds safety threshold (downgrade recommended).
 *  -1 on critical error or guaranteed OOM crash.
 */
int litrun_governor_check_envelope(
    long model_size_mb,
    int context_length,
    float kv_bytes_per_token,
    long *out_ram_needed_mb,
    char *out_reason,
    size_t reason_len
);

/**
 * Emits a JSON telemetry report from the active resource governor.
 * The caller is responsible for calling free() on the returned pointer.
 */
char* litrun_governor_json(void);

#ifdef __cplusplus
}
#endif

#endif /* LITRUN_GOVERNOR_H */
