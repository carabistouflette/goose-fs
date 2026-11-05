//go:build linux && amd64

// SPDX-License-Identifier: Apache-2.0
package main

import (
	"encoding/hex"
	"fmt"
	"os"
	"strconv"
	"time"
)

func must(e error) {
	if e != nil {
		panic(e)
	}
}
func value(p []byte) int64 {
	v := int64(len(p))
	if len(p) > 0 {
		v += int64(p[0]) + int64(p[len(p)-1])
	}
	return v
}
func fdCount() int { entries, e := os.ReadDir("/proc/self/fd"); must(e); return len(entries) }
func freshValue(path string, limit, expected int) int64 {
	var out []byte
	s := boundedRead(path, limit, &out)
	if s.Code != expected || (expected != 0 && len(out) != 0) {
		panic("status mismatch")
	}
	return value(out) + int64(expected+1)
}
func main() {
	a := os.Args
	if len(a) == 5 && (a[1] == "probe" || a[1] == "growth" || a[1] == "empty-probe") {
		path, e := hex.DecodeString(a[2])
		must(e)
		limit, e := strconv.Atoi(a[3])
		must(e)
		loops, e := strconv.Atoi(a[4])
		must(e)
		if a[1] != "growth" && (loops < 1 || loops > 10000) {
			panic("invalid loops")
		}
		before := fdCount()
		out := []byte("sentinel")
		if a[1] == "empty-probe" {
			out = nil
		}
		if a[1] == "growth" {
			if limit < 0 || limit > maxBytes || loops < 0 || loops > limit {
				panic("growth bounds")
			}
			out = make([]byte, limit)
			for i := range out {
				out[i] = 165
			}
			out = out[:loops]
			loops = 1
		}
		var s status
		for i := 0; i < loops; i++ {
			if a[1] == "empty-probe" {
				out = nil
			}
			s = boundedRead(string(path), limit, &out)
		}
		finishFault()
		after := fdCount()
		fmt.Printf("%d\t%d\t%d\t%d\t%d\n", s.Code, s.Err, len(out), before, after)
		_, e = os.Stdout.Write(out)
		must(e)
		return
	}
	if len(a) != 6 || (a[1] != "measure" && a[1] != "fresh") {
		panic("probe HEX LIMIT LOOPS or measure PATH LIMIT EXPECTED_CODE COUNT")
	}
	limit, e := strconv.Atoi(a[3])
	must(e)
	expected, e := strconv.Atoi(a[4])
	must(e)
	count, e := strconv.Atoi(a[5])
	must(e)
	if count < 1 || count > 1000000 {
		panic("invalid count")
	}
	var out []byte
	check := func() {
		s := boundedRead(a[2], limit, &out)
		if s.Code != expected || (expected != 0 && len(out) != 0) {
			panic("status mismatch")
		}
	}
	if a[1] == "fresh" {
		_ = freshValue(a[2], limit, expected)
	} else {
		check()
	}
	for sample := 0; sample < 7; sample++ {
		var sum int64
		start := time.Now()
		if a[1] == "fresh" {
			for i := 0; i < count; i++ {
				sum += freshValue(a[2], limit, expected)
			}
		} else {
			for i := 0; i < count; i++ {
				check()
				sum += value(out) + int64(expected+1)
			}
		}
		elapsed := time.Since(start).Nanoseconds() / int64(count)
		fmt.Printf("%d\t%d\t%d\n", sample, elapsed, sum)
	}
}
