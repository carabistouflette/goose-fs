/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "fs_internal.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pthread.h>
#include <stdbool.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <time.h>
#include <unistd.h>

/* Context -> entry -> allocator. Never wait for another lock with allocator held.
 * Allocation owner bookkeeping is separate from entry state and protected by
 * allocator. Context W drains all of that context's operations/reservations. */
enum { CONTEXTS = 64, FILES = 4096, SLOT_BITS = 12 };
typedef struct { pthread_rwlock_t lock; int64_t id; bool reserved; } context_slot;
typedef struct { pthread_rwlock_t lock; int64_t id; int64_t owner; int fd; int flags; } file_slot;
static context_slot contexts[CONTEXTS];
static file_slot files[FILES];
static int64_t owners[FILES];
static uint64_t serial;
static pthread_mutex_t allocator = PTHREAD_MUTEX_INITIALIZER;
static pthread_once_t once = PTHREAD_ONCE_INIT;
static int init_error;

static void initialize(void) {
    pthread_rwlockattr_t attr;
    int rc = pthread_rwlockattr_init(&attr);
    if (rc) { init_error = rc; return; }
#ifdef __GLIBC__
    rc = pthread_rwlockattr_setkind_np(&attr, PTHREAD_RWLOCK_PREFER_WRITER_NONRECURSIVE_NP);
#endif
    int nc = 0, nf = 0;
    if (!rc) for (; nc < CONTEXTS; ++nc) {
        rc = pthread_rwlock_init(&contexts[nc].lock, &attr);
        if (rc) break;
    }
    if (!rc) for (; nf < FILES; ++nf) {
        rc = pthread_rwlock_init(&files[nf].lock, &attr);
        if (rc) break;
        files[nf].fd = -1;
    }
    pthread_rwlockattr_destroy(&attr);
    if (rc) {
        while (nf) pthread_rwlock_destroy(&files[--nf].lock);
        while (nc) pthread_rwlock_destroy(&contexts[--nc].lock);
        init_error = rc;
    }
}
static int ready(void) {
    int rc = pthread_once(&once, initialize);
    return rc ? rc : init_error;
}
static int64_t new_id(int index) {
    if (serial == (uint64_t)INT64_MAX >> SLOT_BITS) return 0;
    return (int64_t)(++serial << SLOT_BITS) | index;
}
static int result(gf_meta meta, int error) {
    meta.data[0] = error;
    return error ? GF_SYSTEM : GF_OK;
}
static bool meta_valid(gf_meta meta) {
    if (meta.len != 3 || !meta.data) return false;
    meta.data[0] = meta.data[1] = meta.data[2] = 0;
    return true;
}
static context_slot *lock_context(int64_t id, bool exclusive, int *error) {
    *error = ready();
    if (*error) return NULL;
    if (id <= 0 || (id & (FILES - 1)) >= CONTEXTS) { *error = EBADF; return NULL; }
    context_slot *ctx = &contexts[id & (FILES - 1)];
    *error = exclusive ? pthread_rwlock_wrlock(&ctx->lock) : pthread_rwlock_rdlock(&ctx->lock);
    if (*error) return NULL;
    if (ctx->id != id) { pthread_rwlock_unlock(&ctx->lock); *error = EBADF; return NULL; }
    return ctx;
}
static file_slot *lock_file(int64_t context, int64_t id, bool exclusive,
                            context_slot **owner, int *error) {
    *owner = lock_context(context, false, error);
    if (!*owner) return NULL;
    file_slot *file = &files[(uint64_t)id & (FILES - 1)];
    *error = exclusive ? pthread_rwlock_wrlock(&file->lock) : pthread_rwlock_rdlock(&file->lock);
    if (!*error) {
        /* Global IDs are unique; validate the owner too, without reading allocator state. */
        if (id > 0 && file->id == id && file->fd >= 0) {
            if (file->owner == context) return file;
        }
        pthread_rwlock_unlock(&file->lock);
        *error = EBADF;
    }
    pthread_rwlock_unlock(&(*owner)->lock);
    *owner = NULL;
    return NULL;
}
static void unlock_file(context_slot *ctx, file_slot *file) {
    pthread_rwlock_unlock(&file->lock);
    pthread_rwlock_unlock(&ctx->lock);
}
static void release_slot(int index) {
    files[index].id = 0;
    files[index].owner = 0;
    files[index].fd = -1;
    files[index].flags = 0;
    pthread_mutex_lock(&allocator);
    owners[index] = 0;
    pthread_mutex_unlock(&allocator);
}
/* Reserve before filesystem effects. The caller holds Context R. */
static int reserve_slot(int64_t context, int *index, int64_t *id) {
    *index = -1; *id = 0;
    int error = 0;
    pthread_mutex_lock(&allocator);
    for (int i = 0; i < FILES; ++i) if (!owners[i]) { *index = i; break; }
    if (*index < 0) error = EMFILE;
    else if (!(*id = new_id(*index))) error = EOVERFLOW;
    else owners[*index] = context;
    pthread_mutex_unlock(&allocator);
    return error;
}
int64_t gf_context_create(gf_meta meta) {
    if (!meta_valid(meta)) return GF_INVALID;
    int error = ready();
    if (error) return result(meta, error);
    int index = -1; int64_t id = 0;
    pthread_mutex_lock(&allocator);
    for (int i = 0; i < CONTEXTS; ++i) if (!contexts[i].reserved) { index = i; break; }
    if (index < 0) error = EMFILE;
    else if (!(id = new_id(index))) error = EOVERFLOW;
    else contexts[index].reserved = true;
    pthread_mutex_unlock(&allocator);
    if (error) return GF_LIMIT;
    context_slot *ctx = &contexts[index];
    error = pthread_rwlock_wrlock(&ctx->lock);
    if (error) {
        pthread_mutex_lock(&allocator); ctx->reserved = false; pthread_mutex_unlock(&allocator);
        return result(meta, error);
    }
    ctx->id = id;
    pthread_rwlock_unlock(&ctx->lock);
    meta.data[1] = id;
    return GF_OK;
}
int64_t gf_context_close(int64_t id, gf_meta meta) {
    if (!meta_valid(meta)) return GF_INVALID;
    int error;
    context_slot *ctx = lock_context(id, true, &error);
    if (!ctx) return result(meta, error);
    ctx->id = 0;
    int indices[FILES], count = 0;
    pthread_mutex_lock(&allocator);
    for (int i = 0; i < FILES; ++i) if (owners[i] == id) indices[count++] = i;
    pthread_mutex_unlock(&allocator);
    int first_error = 0;
    for (int i = 0; i < count; ++i) {
        int index = indices[i]; file_slot *file = &files[index];
        /* No operation on this context can hold/claim the entry while Context W is held. */
        pthread_rwlock_wrlock(&file->lock);
        if (close(file->fd) < 0 && !first_error) first_error = errno;
        release_slot(index);
        pthread_rwlock_unlock(&file->lock);
    }
    pthread_mutex_lock(&allocator); ctx->reserved = false; pthread_mutex_unlock(&allocator);
    pthread_rwlock_unlock(&ctx->lock);
    return result(meta, first_error);
}
/* flags: access low2 (0 read,1 write,2 both), creation bits2..3
 * (0 existing,1 exclusive,2 open-or-create), append bit4, truncate bit5. */
int64_t gf_file_open(int64_t context, gf_input path, int64_t options, int64_t permissions, gf_meta meta) {
    if (meta.len != 3 || !meta.data || gf_overlap(meta.data, 24, path.data, path.len)) return GF_INVALID;
    meta_valid(meta);
    char text[GF_MAX_PATH + 1];
    int access = (int)(options & 3), creation = (int)((options >> 2) & 3);
    if (options < 0 || options > 63 || access > 2 || creation > 2 ||
        (access == 0 && (options & 48)) || permissions < 0 || permissions > 0777 ||
        !gf_path_copy(path, text)) return GF_INVALID;
    int error;
    context_slot *ctx = lock_context(context, false, &error);
    if (!ctx) return result(meta, error);
    int index; int64_t id;
    error = reserve_slot(context, &index, &id);
    if (error) { pthread_rwlock_unlock(&ctx->lock); return GF_LIMIT; }
    file_slot *file = &files[index];
    error = pthread_rwlock_wrlock(&file->lock);
    if (error) {
        pthread_mutex_lock(&allocator); owners[index] = 0; pthread_mutex_unlock(&allocator);
        pthread_rwlock_unlock(&ctx->lock); return result(meta, error);
    }
    char *leaf;
    int dir = gf_parent(text, &leaf), fd = -1, code = GF_OK;
    if (dir < 0) { error = errno; code = GF_SYSTEM; }
    else {
        int flags = (access == 0 ? O_RDONLY : access == 1 ? O_WRONLY : O_RDWR) |
                    O_NOFOLLOW | O_NONBLOCK | O_NOCTTY | O_CLOEXEC;
        if (creation) flags |= O_CREAT;
        if (creation == 1) flags |= O_EXCL;
        if (options & 16) flags |= O_APPEND;
        fd = openat(dir, leaf, flags, (mode_t)permissions);
        if (fd < 0) { error = errno; code = GF_SYSTEM; }
        else {
            struct stat st;
            if (fstat(fd, &st) < 0) { error = errno; code = GF_SYSTEM; }
            else if (!S_ISREG(st.st_mode)) code = GF_NOT_REGULAR;
            else if ((options & 32) && ftruncate(fd, 0) < 0) { error = errno; code = GF_SYSTEM; }
        }
        close(dir);
    }
    if (code == GF_OK) {
        file->id = id; file->owner = context; file->fd = fd; file->flags = (int)options;
        meta.data[1] = id;
    } else {
        if (fd >= 0) close(fd);
        release_slot(index);
        meta.data[0] = code == GF_SYSTEM ? error : 0;
    }
    pthread_rwlock_unlock(&file->lock);
    pthread_rwlock_unlock(&ctx->lock);
    return code;
}
int64_t gf_file_duplicate(int64_t context, int64_t id, gf_meta meta) {
    if (!meta_valid(meta)) return GF_INVALID;
    context_slot *ctx; int error;
    file_slot *source = lock_file(context, id, false, &ctx, &error);
    if (!source) return result(meta, error);
    int index; int64_t copy_id;
    error = reserve_slot(context, &index, &copy_id);
    if (error) { unlock_file(ctx, source); return GF_LIMIT; }
    file_slot *copy = &files[index];
    /* A reserved free slot cannot be a live lock dependency. Any previous close
     * released allocator before unlocking it, and never needs source's lock. */
    error = pthread_rwlock_wrlock(&copy->lock);
    if (!error) {
        int fd = fcntl(source->fd, F_DUPFD_CLOEXEC, 0);
        if (fd < 0) { error = errno; release_slot(index); }
        else {
            copy->id = copy_id; copy->owner = context; copy->fd = fd; copy->flags = source->flags;
            meta.data[1] = copy_id;
        }
        pthread_rwlock_unlock(&copy->lock);
    } else {
        pthread_mutex_lock(&allocator); owners[index] = 0; pthread_mutex_unlock(&allocator);
    }
    unlock_file(ctx, source);
    return result(meta, error);
}
int64_t gf_file_close(int64_t context, int64_t id, gf_meta meta) {
    if (!meta_valid(meta)) return GF_INVALID;
    context_slot *ctx; int error;
    file_slot *file = lock_file(context, id, true, &ctx, &error);
    if (!file) return result(meta, error);
    int rc = close(file->fd), saved = rc < 0 ? errno : 0;
    release_slot((int)(id & (FILES - 1)));
    unlock_file(ctx, file);
    return result(meta, saved);
}
int64_t gf_file_read(int64_t context, int64_t id, gf_output out, int64_t offset,
                     bool positioned, gf_meta meta) {
    if (meta.len != 3 || !meta.data || gf_overlap(meta.data, 24, out.data, out.len)) return GF_INVALID;
    meta_valid(meta);
    if (out.len < 0 || out.len > GF_MAX_BYTES || (out.len && !out.data) ||
        (positioned && (offset < 0 || offset > INT64_MAX - out.len))) return GF_INVALID;
    context_slot *ctx; int error;
    file_slot *file = lock_file(context, id, !positioned, &ctx, &error);
    if (!file) return result(meta, error);
    if ((file->flags & 3) == 1) error = EBADF;
    else if (out.len) {
        ssize_t n;
        do { n = positioned ? pread(file->fd, out.data, (size_t)out.len, (off_t)offset)
                            : read(file->fd, out.data, (size_t)out.len); } while (n < 0 && errno == EINTR);
        if (n < 0) error = errno;
        else { meta.data[1] = n; meta.data[2] = !n; }
    }
    unlock_file(ctx, file);
    return result(meta, error);
}
int64_t gf_file_write(int64_t context, int64_t id, gf_input data, int64_t offset,
                      bool positioned, bool all, gf_meta meta) {
    if (meta.len != 3 || !meta.data || gf_overlap(meta.data, 24, data.data, data.len)) return GF_INVALID;
    meta_valid(meta);
    if (data.len < 0 || data.len > GF_MAX_BYTES || (data.len && !data.data) ||
        (positioned && (offset < 0 || offset > INT64_MAX - data.len))) return GF_INVALID;
    context_slot *ctx; int error;
    file_slot *file = lock_file(context, id, true, &ctx, &error);
    if (!file) return result(meta, error);
    if ((file->flags & 3) == 0) error = EBADF;
    else if (positioned && (file->flags & 16)) error = EINVAL;
    else while (meta.data[1] < data.len) {
        int64_t used = meta.data[1]; ssize_t n;
        do { n = positioned ? pwrite(file->fd, data.data + used, (size_t)(data.len - used), (off_t)(offset + used))
                            : write(file->fd, data.data + used, (size_t)(data.len - used));
        } while (n < 0 && errno == EINTR);
        if (n <= 0) { error = n < 0 ? errno : EIO; break; }
        meta.data[1] += n;
        if (!all) break;
    }
    unlock_file(ctx, file);
    return result(meta, error);
}
int64_t gf_file_seek(int64_t context, int64_t id, int64_t offset, int64_t origin, gf_meta meta) {
    if (!meta_valid(meta)) return GF_INVALID;
    if (origin < 0 || origin > 2 || (origin == 0 && offset < 0)) return GF_INVALID;
    context_slot *ctx; int error;
    file_slot *file = lock_file(context, id, true, &ctx, &error);
    if (!file) return result(meta, error);
    off_t position = lseek(file->fd, (off_t)offset, origin == 0 ? SEEK_SET : origin == 1 ? SEEK_CUR : SEEK_END);
    if (position < 0) error = errno; else meta.data[1] = position;
    unlock_file(ctx, file);
    return result(meta, error);
}
int64_t gf_file_truncate(int64_t context, int64_t id, int64_t size, gf_meta meta) {
    if (!meta_valid(meta)) return GF_INVALID;
    if (size < 0) return GF_INVALID;
    context_slot *ctx; int error;
    file_slot *file = lock_file(context, id, true, &ctx, &error);
    if (!file) return result(meta, error);
    if ((file->flags & 3) == 0) error = EBADF;
    else if (ftruncate(file->fd, (off_t)size) < 0) error = errno;
    unlock_file(ctx, file);
    return result(meta, error);
}
int64_t gf_file_sync(int64_t context, int64_t id, bool data_only, gf_meta meta) {
    if (!meta_valid(meta)) return GF_INVALID;
    context_slot *ctx; int error;
    file_slot *file = lock_file(context, id, true, &ctx, &error);
    if (!file) return result(meta, error);
    int rc;
    do { rc = data_only ? fdatasync(file->fd) : fsync(file->fd); } while (rc < 0 && errno == EINTR);
    if (rc < 0) error = errno;
    unlock_file(ctx, file);
    return result(meta, error);
}
int64_t gf_file_metadata(int64_t context, int64_t id, gf_meta fields) {
    if (fields.len != 18 || !fields.data) return GF_INVALID;
    memset(fields.data, 0, 18 * sizeof(int64_t));
    context_slot *ctx; int error;
    file_slot *file = lock_file(context, id, false, &ctx, &error);
    if (!file) { fields.data[0] = error; return GF_SYSTEM; }
    int rc = gf_metadata_at(file->fd, "", AT_EMPTY_PATH | AT_SYMLINK_NOFOLLOW, fields.data);
    error = rc < 0 ? errno : 0;
    unlock_file(ctx, file);
    fields.data[0] = error;
    return error ? GF_SYSTEM : GF_OK;
}
/* No blocking flock while registry locks are held: it could prevent the
 * Context's owner from closing the descriptors needed to release contention. */
int64_t gf_file_try_lock(int64_t context, int64_t id, int64_t mode, gf_meta meta) {
    if (!meta_valid(meta)) return GF_INVALID;
    if (mode < 0 || mode > 2) return GF_INVALID;
    context_slot *ctx; int error;
    file_slot *file = lock_file(context, id, true, &ctx, &error);
    if (!file) return result(meta, error);
    int operation = mode == 0 ? LOCK_UN : (mode == 1 ? LOCK_SH : LOCK_EX) | LOCK_NB;
    int rc;
    do { rc = flock(file->fd, operation); } while (rc < 0 && errno == EINTR);
    if (rc < 0) error = errno;
    unlock_file(ctx, file);
    return result(meta, error);
}
_Bool gf_lock_contended(int64_t error) { return error == EAGAIN || error == EWOULDBLOCK; }
/* Called by Goose only after an unsuccessful attempt has released all locks. */
int64_t gf_lock_pause(void) {
    struct timespec delay = { .tv_sec = 0, .tv_nsec = 1000000 };
    while (nanosleep(&delay, &delay) < 0) {
        if (errno != EINTR) return errno;
    }
    return 0;
}
