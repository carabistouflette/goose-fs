// SPDX-License-Identifier: Apache-2.0
package main
import (
    "fmt"
    "io"
    "os"
    "path/filepath"
    "strconv"
    "slices"
    "strings"
    "time"
)
var byteSink []byte
var entrySink []os.DirEntry
var infoSink os.FileInfo
var nameSink []string
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
func rootNames(root *os.Root) []string {
    file, err := root.Open("list-128"); must(err)
    names, readErr := file.Readdirnames(-1)
    closeErr := file.Close(); must(readErr); must(closeErr)
    slices.Sort(names); return names
}
func finishRename(a, b *os.File, renameErr error) error {
    var firstSync, secondSync error
    if renameErr == nil { firstSync=a.Sync(); secondSync=b.Sync() }
    firstClose, secondClose := a.Close(), b.Close()
    for _, err := range []error{renameErr,firstSync,secondSync,firstClose,secondClose} {
        if err != nil { return err }
    }
    return nil
}
func renameChecked(from, to string) error {
    a, err := os.Open(filepath.Dir(from)); if err != nil { return err }
    b, err := os.Open(filepath.Dir(to)); if err != nil { a.Close(); return err }
    return finishRename(a,b,os.Rename(from,to))
}
func rootRenameChecked(root *os.Root, from, to string) error {
    a, err := root.Open("."); if err != nil { return err }
    b, err := root.Open("."); if err != nil { a.Close(); return err }
    return finishRename(a,b,root.Rename(from,to))
}
func renameCases(path string, count int) {
    from, to := filepath.Join(path,"left"), filepath.Join(path,"right")
    for _, checked := range []bool{false,true} {
        warm, err := os.ReadFile(from); must(err)
        if string(warm)!="rename fixture" { panic("rename preflight") }
        if _, err:=os.Lstat(to); !os.IsNotExist(err) { panic("rename target present") }
        label:="rename-replace-pair"; if checked { label="rename-parents-sync-pair" }
        if checked { must(renameChecked(from,to)) } else { must(os.Rename(from,to)) }
        moved, err:=os.ReadFile(to); must(err)
        if string(moved)!="rename fixture" { panic("rename did not move content") }
        if _, err:=os.Lstat(from); !os.IsNotExist(err) { panic("rename did not remove source") }
        if checked { must(renameChecked(to,from)) } else { must(os.Rename(to,from)) }
        samples(label,count,func() uint64 {
            if checked { must(renameChecked(from,to)); must(renameChecked(to,from)) } else { must(os.Rename(from,to)); must(os.Rename(to,from)) }
            return 1
        })
        after, err := os.ReadFile(from); must(err)
        if string(after)!="rename fixture" { panic("rename postflight") }
        if _, err:=os.Lstat(to); !os.IsNotExist(err) { panic("rename target remains") }
    }
    root, err := os.OpenRoot(path); must(err)
    for _, checked := range []bool{false,true} {
        label:="root-rename-replace-pair"; if checked { label="root-rename-parents-sync-pair" }
        warm, err:=root.ReadFile("left"); must(err)
        if string(warm)!="rename fixture" { panic("root rename preflight") }
        if _, err:=root.Lstat("right"); !os.IsNotExist(err) { panic("root rename target present") }
        if checked { must(rootRenameChecked(root,"left","right")) } else { must(root.Rename("left","right")) }
        moved, err:=root.ReadFile("right"); must(err)
        if string(moved)!="rename fixture" { panic("root rename did not move content") }
        if _, err:=root.Lstat("left"); !os.IsNotExist(err) { panic("root rename did not remove source") }
        if checked { must(rootRenameChecked(root,"right","left")) } else { must(root.Rename("right","left")) }
        samples(label,count,func() uint64 {
            if checked { must(rootRenameChecked(root,"left","right")); must(rootRenameChecked(root,"right","left")) } else { must(root.Rename("left","right")); must(root.Rename("right","left")) }
            return 1
        })
        after, err:=root.ReadFile("left"); must(err)
        if string(after)!="rename fixture" { panic("root rename postflight") }
        if _, err:=root.Lstat("right"); !os.IsNotExist(err) { panic("root rename target remains") }
    }
    must(root.Close())
    for _, label:=range []string{"rename-noreplace-pair","root-rename-noreplace-pair"} {
        for sample:=0;sample<7;sample++ { fmt.Printf("%s\t%d\t0\t0\tunsupported\n",label,sample) }
    }
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
    for sample := 0; sample < 7; sample++ {
        fmt.Printf("lock-exclusive-pair\t%d\t0\t0\tunsupported\n",sample)
    }
    directory := filepath.Join(root,"list-0")
    samples("is-dir",count,func() uint64 {
        info, err := os.Stat(directory); must(err); if !info.IsDir() { panic("not directory") }; return 1
    })
    held, err := os.OpenRoot(root); must(err)
    warmRoot, err := held.ReadFile("read-64"); must(err); validate(warmRoot)
    if len(warmRoot)!=64 { panic("root warm read length") }
    samples("root-read-fresh-64",count,func() uint64 {
        data, err := held.ReadFile("read-64"); must(err)
        if len(data)!=64 { panic("root read length") }
        value:=checksum(data); byteSink=data; return value
    })
    samples("root-metadata-file",count,func() uint64 {
        info, err := held.Lstat("read-64"); must(err)
        if !info.Mode().IsRegular() || info.Size()!=64 { panic("root metadata mismatch") }
        infoSink=info; return 65
    })
    rootEntries := rootNames(held)
    if len(rootEntries)!=128 { panic("root listing length") }
    for i, name := range rootEntries { if name!=fmt.Sprintf("entry-%04d",i) { panic("root name mismatch") } }
    samples("root-list-sorted-128",count,func() uint64 {
        names := rootNames(held); var sum uint64
        for _, name := range names { sum+=nameValue(name) }
        nameSink=names; return sum
    })
    must(held.Close())
    renameCases(filepath.Join(root,"rename"),count)
    status, err := os.ReadFile("/proc/self/status"); must(err)
    for _, line := range strings.Split(string(status),"\n") {
        if strings.HasPrefix(line,"VmHWM:") { fmt.Printf("MEMORY\t%s\n",line) }
    }
}
