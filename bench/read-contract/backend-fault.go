// SPDX-License-Identifier: Apache-2.0
//go:build linux && amd64 && adaptertest

package main

import (
	"encoding/json"
	"os"
	"strconv"
	"strings"
	"syscall"
)

var fault = os.Getenv("READ_CONTRACT_FAULT")
var stats = map[string]int{}
var leafFD = -1
var reusedFD = -1

func hit(key string) { stats[key]++ }
func inject()        { hit("injected") }
func openParent2(path *byte) (int, int) {
	hit("open2")
	if fault == "fallback1" {
		inject()
		return -1, 1
	}
	if fault == "fallback38" || strings.HasPrefix(fault, "walk_") {
		inject()
		return -1, 38
	}
	return realOpenParent2(path)
}
func openAt(dir int, path *byte, flags int) (int, int) {
	hit("opens")
	if fault == "walk_open_close" && dir >= 0 && flags&dirFlags == dirFlags {
		inject()
		return -1, 13
	}
	fd, e := realOpenAt(dir, path, flags)
	if e == 0 && flags == fileFlags {
		leafFD = fd
	}
	return fd, e
}
func statFD(fd int, s *syscall.Stat_t) error {
	e := syscall.Fstat(fd, s)
	if fault == "stat_eio" {
		inject()
		return syscall.EIO
	}
	if e == nil && (fault == "stat_small" || fault == "stat_large") {
		inject()
		s.Size = 0
		if fault == "stat_large" {
			s.Size = 9223372036854775807
		}
	}
	return e
}
func regularFD(fd int) (bool, int) { hit("stats"); return realRegularFD(fd) }
func readFD(fd int, buf []byte) (int, int) {
	hit("reads")
	if strings.HasPrefix(fault, "growth-") && stats["reads"] == 1 {
		old, e := strconv.Atoi(strings.TrimPrefix(fault, "growth-"))
		if e != nil || old > len(buf) {
			panic("growth old bounds")
		}
		for _, b := range buf[old:] {
			if b != 0 {
				panic("uninitialized/regrown output tail")
			}
		}
		hit("growth_checked")
		inject()
	}
	if fault == "eintr" && stats["reads"] == 1 {
		inject()
		return -1, 4
	}
	if fault == "read_eio" || strings.HasPrefix(fault, "read_close_") {
		if stats["reads"] > 1 {
			inject()
			return -1, 5
		}
		if len(buf) > 1 {
			buf = buf[:1]
		}
	}
	if fault == "short" && len(buf) > 3 {
		buf = buf[:3]
		inject()
	}
	n, e := realReadFD(fd, buf)
	if n > 0 {
		stats["read_bytes"] += n
	}
	return n, e
}
func closeFD(fd, phase int) int {
	hit("closes")
	key := []string{"parent_closes", "file_closes", "walk_closes", "next_closes"}[phase]
	hit(key)
	e := realCloseFD(fd, phase)
	fail := (phase == fileCleanup && (strings.Contains(fault, "close_eio") || strings.Contains(fault, "close_eintr") || fault == "reuse_file")) ||
		(phase == walkCleanup && strings.HasPrefix(fault, "walk_") && stats["walk_closes"] == 1) ||
		(phase == parentCleanup && fault == "parent_close")
	if !fail {
		return e
	}
	if e != 0 {
		panic("real consumed close failed")
	}
	inject()
	// Install another object at the exact consumed FD number. It must survive
	// the rest of the actual adapter call; any retry/double close is detected.
	var err error
	reusedFD, err = syscall.Open("/dev/null", syscall.O_RDONLY|syscall.O_CLOEXEC, 0)
	if err != nil || reusedFD != fd {
		panic("FD reuse setup failed")
	}
	if strings.HasSuffix(fault, "eintr") {
		return 4
	}
	return 5
}
func finishFault() {
	if fault == "" {
		return
	}
	if reusedFD >= 0 {
		_, _, e := syscall.Syscall(syscall.SYS_FCNTL, uintptr(reusedFD), syscall.F_GETFD, 0)
		if e != 0 {
			panic("consumed FD retried or double-closed")
		}
		hit("reuse_checked")
		if syscall.Close(reusedFD) != nil {
			panic("replacement close")
		}
		reusedFD = -1
	}
	stats["leaf_seen"] = 0
	if leafFD >= 0 {
		stats["leaf_seen"] = 1
	}
	b, e := json.Marshal(stats)
	if e != nil {
		panic(e)
	}
	if _, e = os.Stderr.Write(append(b, '\n')); e != nil {
		panic(e)
	}
}
