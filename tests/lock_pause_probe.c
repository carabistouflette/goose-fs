/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

/* Test-program interposition only. Production contains no pause observer hook.
 * Arm only the tested worker, leaving runtime/sanitizer sleeps untouched. */
static _Thread_local bool armed;
static pthread_mutex_t gate = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t wake = PTHREAD_COND_INITIALIZER;
static bool entered, released, deny;
static int64_t calls;
void lp_arm(void) { armed = true; }
void lp_disarm(void) { armed = false; }
void lp_configure(bool fail) {
    pthread_mutex_lock(&gate);
    entered = released = false; deny = fail; calls = 0;
    pthread_mutex_unlock(&gate);
}
void lp_wait(void) {
    pthread_mutex_lock(&gate);
    while (!entered) pthread_cond_wait(&wake,&gate);
    pthread_mutex_unlock(&gate);
}
void lp_release(void) {
    pthread_mutex_lock(&gate); released = true; pthread_cond_broadcast(&wake); pthread_mutex_unlock(&gate);
}
int64_t lp_calls(void) {
    pthread_mutex_lock(&gate); int64_t value = calls; pthread_mutex_unlock(&gate); return value;
}
int64_t lp_permission_error(void) { return EPERM; }
int nanosleep(const struct timespec *delay, struct timespec *remaining) {
    if (!armed) return (int)syscall(SYS_clock_nanosleep,CLOCK_MONOTONIC,0,delay,remaining);
    assert(delay->tv_sec == 0 && delay->tv_nsec == 1000000);
    pthread_mutex_lock(&gate);
    ++calls; entered = true; pthread_cond_broadcast(&wake);
    while (!deny && !released) pthread_cond_wait(&wake,&gate);
    bool failed = deny; pthread_mutex_unlock(&gate);
    if (failed) { errno = EPERM; return -1; }
    return 0;
}
