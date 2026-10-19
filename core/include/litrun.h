#ifndef LITRUN_H
#define LITRUN_H

#include <stddef.h>
#include <stdint.h>
#include "fingerprint.h"
#include "governor.h"

#ifdef __cplusplus
extern "C" {
#endif

#define LITRUN_VERSION "0.1.0"
#define LITRUN_API_VERSION 1

const char* litrun_get_version(void);

#ifdef __cplusplus
}
#endif

#endif /* LITRUN_H */
