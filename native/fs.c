/* SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include "fs.h"
#if !defined(__linux__)
#error "goose-fs currently requires Linux"
#endif
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

enum { OK, INVALID, LIMIT, NOT_REGULAR, SYSTEM };
enum { READ, LIST, CREATE, MKDIR, UNLINK, RMDIR };
enum { MAX_PATH = 4095, MAX_BYTES = 1048576, MAX_ENTRIES = 4096 };

static bool overlap(const void *a, int64_t an, const void *b, int64_t bn) {
    if (an <= 0 || bn <= 0) return false;
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    return x <= y ? y - x < (uint64_t)an : x - y < (uint64_t)bn;
}

/* Validate before copying; no normalization that could change path meaning. */
static bool path_copy(gf_input path, char text[MAX_PATH + 1]) {
    if (path.len < 1 || path.len > MAX_PATH || !path.data || path.data[0] != '/' ||
        memchr(path.data, 0, (size_t)path.len)) return false;
    if (path.len != 1) {
        size_t start = 1;
        for (size_t i = 1; i <= (size_t)path.len; ++i) {
            if (i != (size_t)path.len && path.data[i] != '/') continue;
            size_t n = i - start;
            if (!n || (n == 1 && path.data[start] == '.') ||
                (n == 2 && path.data[start] == '.' && path.data[start + 1] == '.')) return false;
            start = i + 1;
        }
    }
    memcpy(text, path.data, (size_t)path.len);
    text[path.len] = 0;
    return true;
}

/* Return parent descriptor and a leaf in text; every ancestor rejects symlinks. */
static int parent(char *text, char **leaf) {
    int fd = open("/", O_PATH | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0) return -1;
    char *part = text + 1, *slash;
    while ((slash = strchr(part, '/'))) {
        *slash = 0;
        int next = openat(fd, part, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        int saved = errno;
        close(fd); /* Linux: never retry close after EINTR. */
        if (next < 0) { errno = saved; return -1; }
        fd = next; part = slash + 1;
    }
    *leaf = *part ? part : ".";
    return fd;
}

static int read_regular(int dir, const char *leaf, gf_output out, int64_t *length) {
    int fd = openat(dir, leaf, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return SYSTEM;
    struct stat st;
    int result = OK, saved = 0;
    if (fstat(fd, &st) < 0) { result = SYSTEM; saved = errno; }
    else if (!S_ISREG(st.st_mode)) result = NOT_REGULAR;
    else {
        while (*length < out.len) {
            ssize_t n = read(fd, out.data + *length, (size_t)(out.len - *length));
            if (n < 0) { if (errno == EINTR) continue; result = SYSTEM; saved = errno; break; }
            if (!n) break;
            *length += n;
        }
        if (result == OK && *length == out.len) {
            uint8_t extra;
            ssize_t n;
            do { n = read(fd, &extra, 1); } while (n < 0 && errno == EINTR);
            if (n > 0) result = LIMIT;
            else if (n < 0) { result = SYSTEM; saved = errno; }
        }
    }
    if (close(fd) < 0 && result == OK) { result = SYSTEM; saved = errno; }
    errno = saved;
    return result;
}

static int list_dir(int dir, const char *leaf, gf_output out, int64_t cap, int64_t *length, int64_t *count) {
    int fd = openat(dir, leaf, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return SYSTEM;
    DIR *stream = fdopendir(fd);
    if (!stream) { int saved = errno; close(fd); errno = saved; return SYSTEM; }
    int result = OK, saved = 0;
    for (;;) {
        errno = 0;
        struct dirent *entry = readdir(stream);
        if (!entry) { if (errno) { result = SYSTEM; saved = errno; } break; }
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        size_t n = strlen(entry->d_name);
        if (*count == cap || (int64_t)n + 2 > out.len - *length) { result = LIMIT; break; }
        uint8_t kind = entry->d_type == DT_REG ? 1 : entry->d_type == DT_DIR ? 2 :
                       entry->d_type == DT_LNK ? 3 : entry->d_type == DT_UNKNOWN ? 0 : 4;
        out.data[(*length)++] = kind;
        memcpy(out.data + *length, entry->d_name, n + 1);
        *length += (int64_t)n + 1;
        ++*count;
    }
    if (closedir(stream) < 0 && result == OK) { result = SYSTEM; saved = errno; }
    errno = saved;
    return result;
}

static int create_file(int dir, const char *leaf, gf_input data) {
    int fd = openat(dir, leaf, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) return SYSTEM;
    int result = OK, saved = 0;
    int64_t done = 0;
    while (done < data.len) {
        ssize_t n = write(fd, data.data + done, (size_t)(data.len - done));
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { result = SYSTEM; saved = n < 0 ? errno : EIO; break; }
        done += n;
    }
    if (close(fd) < 0 && result == OK) { result = SYSTEM; saved = errno; }
    errno = saved;
    return result;
}

int64_t gf_call(int64_t op, gf_input path, gf_input data, int64_t entries,
                gf_output out, gf_meta meta) {
    if (meta.len != 3 || !meta.data) return INVALID;
    /* Guard the private ABI before touching writable slices, including metadata. */
    if (overlap(meta.data, 24, path.data, path.len) || overlap(meta.data, 24, data.data, data.len) ||
        overlap(meta.data, 24, out.data, out.len)) return INVALID;
    meta.data[0] = meta.data[1] = meta.data[2] = 0;
    char text[MAX_PATH + 1];
    if (op < READ || op > RMDIR || !path_copy(path, text) ||
        data.len < 0 || data.len > MAX_BYTES || (data.len && !data.data) ||
        out.len < 0 || out.len > MAX_BYTES || (out.len && !out.data) ||
        entries < 0 || entries > MAX_ENTRIES ||
        overlap(out.data, out.len, path.data, path.len) || overlap(out.data, out.len, data.data, data.len) ||
        (op >= CREATE && path.len == 1)) return INVALID;
    char *leaf;
    int dir = parent(text, &leaf);
    if (dir < 0) { meta.data[0] = errno; return SYSTEM; }
    int result;
    if (op == READ) result = read_regular(dir, leaf, out, &meta.data[1]);
    else if (op == LIST) result = list_dir(dir, leaf, out, entries, &meta.data[1], &meta.data[2]);
    else if (op == CREATE) result = create_file(dir, leaf, data);
    else {
        int rc = op == MKDIR ? mkdirat(dir, leaf, 0700) : unlinkat(dir, leaf, op == RMDIR ? AT_REMOVEDIR : 0);
        result = rc < 0 ? SYSTEM : OK;
    }
    int saved = result == SYSTEM ? errno : 0;
    close(dir);
    if (result != OK) meta.data[1] = meta.data[2] = 0;
    meta.data[0] = saved;
    return result;
}
