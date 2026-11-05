// SPDX-License-Identifier: Apache-2.0
//go:build linux && amd64

package main

const maxBytes = 1048576
const dirFlags = 0x200000 | 0x10000 | 0x80000
const fileFlags = 0x20000 | 0x800 | 0x100 | 0x80000
const (
	parentCleanup = iota
	fileCleanup
	walkCleanup
	nextCleanup
)

type status struct {
	Code int
	Err  int
}

func system(e int) status { return status{4, e} }
func validPath(path string) bool {
	if len(path) < 1 || len(path) > 4095 || path[0] != '/' {
		return false
	}
	start := 1
	for i := 0; i <= len(path); i++ {
		if i < len(path) && path[i] == 0 {
			return false
		}
		if i < 1 || (i < len(path) && path[i] != '/') {
			continue
		}
		if len(path) == 1 {
			return true
		}
		n := i - start
		if n == 0 || (n == 1 && path[start] == '.') || (n == 2 && path[start] == '.' && path[start+1] == '.') {
			return false
		}
		start = i + 1
	}
	return true
}

var rootName = [2]byte{'/', 0}
var selfName = [2]byte{'.', 0}

func parent(text *[4096]byte, length, separator int) (int, int) {
	text[separator] = 0
	directory := &text[0]
	if separator == 0 {
		directory = &rootName[0]
	}
	fd, e := openParent2(directory)
	text[separator] = '/'
	if e == 0 {
		return fd, 0
	}
	if e != 38 && e != 1 {
		return -1, e
	}
	fd, e = openAt(-100, &rootName[0], dirFlags)
	if e != 0 {
		return -1, e
	}
	start := 1
	for i := 1; i < length; i++ {
		if text[i] != '/' {
			continue
		}
		text[i] = 0
		next, opened := openAt(fd, &text[start], dirFlags|0x20000)
		closed := closeFD(fd, walkCleanup)
		if opened != 0 || closed != 0 {
			if next >= 0 {
				closeFD(next, nextCleanup)
			}
			if opened != 0 {
				return -1, opened
			}
			return -1, closed
		}
		fd = next
		start = i + 1
	}
	return fd, 0
}
func boundedRead(path string, limit int, out *[]byte) status {
	if !validPath(path) || limit < 0 || limit > maxBytes {
		*out = (*out)[:0]
		return status{Code: 1}
	}
	old := len(*out)
	if cap(*out) < limit {
		grown := make([]byte, limit)
		copy(grown, *out)
		*out = grown
	} else {
		*out = (*out)[:limit]
		if limit > old {
			clear((*out)[old:])
		}
	}
	var text [4096]byte
	copy(text[:], path)
	separator := 0
	for i := range len(path) {
		if path[i] == '/' {
			separator = i
		}
	}
	dir, e := parent(&text, len(path), separator)
	if e != 0 {
		*out = (*out)[:0]
		return system(e)
	}
	leaf := &text[separator+1]
	if len(path) == 1 {
		leaf = &selfName[0]
	}
	fd, e := openAt(dir, leaf, fileFlags)
	result := status{}
	used := 0
	if e != 0 {
		result = system(e)
	} else {
		regular, se := regularFD(fd)
		if se != 0 {
			result = system(se)
		} else if !regular {
			result.Code = 3
		} else {
			for used < limit {
				n, re := readFD(fd, (*out)[used:])
				if re == 4 {
					continue
				}
				if re != 0 {
					result = system(re)
					break
				}
				if n == 0 {
					break
				}
				used += n
			}
			if result.Code == 0 && used == limit {
				var extra [1]byte
				for {
					n, re := readFD(fd, extra[:])
					if re == 4 {
						continue
					}
					if re != 0 {
						result = system(re)
					} else if n > 0 {
						result.Code = 2
					}
					break
				}
			}
		}
		ce := closeFD(fd, fileCleanup)
		if result.Code == 0 && ce != 0 {
			result = system(ce)
		}
	}
	closeFD(dir, parentCleanup)
	if result.Code != 0 {
		*out = (*out)[:0]
	} else {
		*out = (*out)[:used]
	}
	return result
}
