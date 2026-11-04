// SPDX-License-Identifier: Apache-2.0
package main
import (
    "fmt"
    "io"
    "os"
    "path/filepath"
    "strconv"
    "strings"
    "time"
)
var byteSink []byte
var entrySink []os.DirEntry
var infoSink os.FileInfo
func must(err error) { if err != nil { panic(err) } }
func checksum(data []byte) uint64 {
    value := uint64(len(data))
    if len(data) > 0 { value += uint64(data[0]); value += uint64(data[len(data)-1]) }
    return value
}
func nameValue(name string) uint64 {
    value := uint64(len(name))
    if len(name) > 0 { value += uint64(name[0]); value += uint64(name[len(name)-1]) }
    return value
}
func validate(data []byte) {
    for i, b := range data { if b != byte((i*17+13)%251) { panic("content mismatch") } }
}
func samples(label string, count int, operation func() uint64) {
    operation()
    for sample := 0; sample < 7; sample++ {
        start := time.Now(); var sum uint64
        for i := 0; i < count; i++ { sum += operation() }
        elapsed := time.Since(start).Nanoseconds()/int64(count)
        fmt.Printf("%s\t%d\t%d\t%d\tok\n",label,sample,elapsed,sum)
    }
}
func readReuse(path string, storage []byte) []byte {
    file, err := os.Open(path); must(err)
    used := 0
    for {
        n, readErr := file.Read(storage[used:]); used += n
        if readErr == io.EOF { break }
        if readErr != nil { file.Close(); panic(readErr) }
        if used == len(storage) { file.Close(); panic("fixture exceeds reusable storage") }
    }
    must(file.Close()); return storage[:used]
}
func main() {
    if len(os.Args)!=3 { panic("root and iterations required") }
    root := os.Args[1]; count, err := strconv.Atoi(os.Args[2]); must(err)
    if count < 1 || count > 1000000 { panic("invalid iterations") }
    for _, size := range []int{0,64,4096,65536,1048576} {
        path := filepath.Join(root,fmt.Sprintf("read-%d",size))
        warm, err := os.ReadFile(path); must(err); validate(warm)
        samples(fmt.Sprintf("read-fresh-%d",size),count,func() uint64 {
            data, err := os.ReadFile(path); must(err)
            if len(data)!=size { panic("wrong length") }
            value := checksum(data); byteSink = data; return value
        })
        storage := make([]byte,size+1)
        samples(fmt.Sprintf("read-reuse-%d",size),count,func() uint64 {
            data := readReuse(path,storage)
            if len(data)!=size { panic("wrong length") }
            byteSink = data; return checksum(data)
        })
        validate(byteSink)
        file, err := os.Open(path); must(err)
        retained := make([]byte,size)
        samples(fmt.Sprintf("read-retained-%d",size),count,func() uint64 {
            n, err := file.ReadAt(retained,0); must(err)
            if n!=size { panic("wrong retained read length") }
            byteSink=retained; return checksum(retained)
        })
        validate(retained); must(file.Close())
    }
    for _, countEntries := range []int{0,1,128,4096} {
        path := filepath.Join(root,fmt.Sprintf("list-%d",countEntries))
        warm, err := os.ReadDir(path); must(err)
        if len(warm)!=countEntries { panic("wrong listing length") }
        for i, entry := range warm { if entry.Name()!=fmt.Sprintf("entry-%04d",i) { panic("name mismatch") } }
        samples(fmt.Sprintf("list-sorted-%d",countEntries),count,func() uint64 {
            entries, err := os.ReadDir(path); must(err); var sum uint64
            for _, entry := range entries { sum += nameValue(entry.Name()) }
            entrySink = entries; return sum
        })
    }
    file := filepath.Join(root,"read-64")
    samples("metadata-file",count,func() uint64 {
        info, err := os.Lstat(file); must(err)
        if !info.Mode().IsRegular() || info.Size()!=64 { panic("metadata mismatch") }
        infoSink = info; return 65
    })
    directory := filepath.Join(root,"list-0")
    samples("is-dir",count,func() uint64 {
        info, err := os.Stat(directory); must(err); if !info.IsDir() { panic("not directory") }; return 1
    })
    status, err := os.ReadFile("/proc/self/status"); must(err)
    for _, line := range strings.Split(string(status),"\n") {
        if strings.HasPrefix(line,"VmHWM:") { fmt.Printf("MEMORY\t%s\n",line) }
    }
}
