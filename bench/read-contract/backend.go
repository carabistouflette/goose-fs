// SPDX-License-Identifier: Apache-2.0
//go:build linux && amd64

package main

import (
	"runtime"
	"syscall"
	"unsafe"
)

type openHow struct{ Flags, Mode, Resolve uint64 }

func realOpenParent2(path *byte) (int, int) {
	how := openHow{Flags: dirFlags, Resolve: 4}
	fd, _, e := syscall.Syscall6(437, ^uintptr(99), uintptr(unsafe.Pointer(path)), uintptr(unsafe.Pointer(&how)), 24, 0, 0)
	runtime.KeepAlive(path)
	runtime.KeepAlive(&how)
	if e != 0 {
		return -1, int(e)
	}
	return int(fd), 0
}
func realOpenAt(dir int, path *byte, flags int) (int, int) {
	fd, _, e := syscall.Syscall6(syscall.SYS_OPENAT, uintptr(dir), uintptr(unsafe.Pointer(path)), uintptr(flags), 0, 0, 0)
	runtime.KeepAlive(path)
	if e != 0 {
		return -1, int(e)
	}
	return int(fd), 0
}
func errno(e error) int {
	if e == nil {
		return 0
	}
	if n, ok := e.(syscall.Errno); ok {
		return int(n)
	}
	panic(e)
}
func realRegularFD(fd int) (bool, int) {
	var s syscall.Stat_t
	e := statFD(fd, &s)
	return s.Mode&syscall.S_IFMT == syscall.S_IFREG, errno(e)
}
func realReadFD(fd int, buffer []byte) (int, int) {
	n, e := syscall.Read(fd, buffer)
	return n, errno(e)
}
func realCloseFD(fd, phase int) int { return errno(syscall.Close(fd)) }
