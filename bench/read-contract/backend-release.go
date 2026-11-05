//go:build linux && amd64 && !adaptertest

// SPDX-License-Identifier: Apache-2.0
package main

import "syscall"

func openParent2(path *byte) (int, int)                { return realOpenParent2(path) }
func openAt(dir int, path *byte, flags int) (int, int) { return realOpenAt(dir, path, flags) }
func regularFD(fd int) (bool, int)                     { return realRegularFD(fd) }
func readFD(fd int, p []byte) (int, int)               { return realReadFD(fd, p) }
func closeFD(fd, phase int) int                        { return realCloseFD(fd, phase) }

func finishFault() {}

func statFD(fd int, s *syscall.Stat_t) error { return syscall.Fstat(fd, s) }
