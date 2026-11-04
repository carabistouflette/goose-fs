// SPDX-License-Identifier: Apache-2.0
use std::{fs, hint::black_box, io::Read, path::Path, time::Instant};
use std::os::unix::fs::{FileExt, MetadataExt, PermissionsExt};
use std::io::{Seek, SeekFrom};
fn file_setters(path: &Path, count: u64) {
    let mut file = fs::File::open(path).unwrap();
    let before = file.metadata().unwrap();
    let (uid, gid) = (before.uid(), before.gid());
    file.seek(SeekFrom::Start(3)).unwrap();
    samples("file-set-permissions", count, || {
        file.set_permissions(fs::Permissions::from_mode(0o640)).unwrap(); 1
    });
    assert_eq!(file.metadata().unwrap().mode() & 0o7777, 0o640);
    samples("file-set-owner", count, || {
        std::os::unix::fs::fchown(&file, Some(uid), Some(gid)).unwrap(); 1
    });
    let after = file.metadata().unwrap(); assert_eq!((after.uid(), after.gid()), (uid, gid));
    let accessed = std::time::UNIX_EPOCH + std::time::Duration::new(1000, 123456789);
    let modified = std::time::UNIX_EPOCH + std::time::Duration::new(2200000000, 987654321);
    let times = fs::FileTimes::new().set_accessed(accessed).set_modified(modified);
    samples("file-set-times", count, || { file.set_times(times).unwrap(); 1 });
    let after = file.metadata().unwrap();
    assert_eq!(after.accessed().unwrap(), accessed); assert_eq!(after.modified().unwrap(), modified);
    assert_eq!(file.stream_position().unwrap(), 3);
}
fn checksum(bytes: &[u8]) -> u64 {
    bytes.len() as u64 + bytes.first().copied().unwrap_or(0) as u64
        + bytes.last().copied().unwrap_or(0) as u64
}
fn validate(bytes: &[u8]) {
    for (i, &byte) in bytes.iter().enumerate() { assert_eq!(byte, ((i * 17 + 13) % 251) as u8); }
}
fn samples<F: FnMut() -> u64>(label: &str, count: u64, mut operation: F) {
    black_box(operation());
    for sample in 0..7 {
        let start = Instant::now();
        let mut sum = 0u64;
        for _ in 0..count { sum += operation(); }
        let elapsed = start.elapsed().as_nanos() / u128::from(count);
        println!("{label}\t{sample}\t{elapsed}\t{sum}\tok");
    }
}
fn absent(path: &Path) {
    match fs::symlink_metadata(path) {
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => (),
        other => panic!("expected absent entry: {other:?}"),
    }
}
fn rename_checked(from: &Path, to: &Path) -> std::io::Result<()> {
    let a = fs::File::open(from.parent().unwrap())?;
    let b = fs::File::open(to.parent().unwrap())?;
    fs::rename(from, to)?;
    let first = a.sync_all();
    let second = b.sync_all();
    first?; second?; Ok(())
}
fn rename_cases(path: &Path, count: u64) {
    let from = path.join("left"); let to = path.join("right");
    for checked in [false, true] {
        assert_eq!(fs::read(&from).unwrap(), b"rename fixture"); absent(&to);
        let label = if checked { "rename-parents-sync-pair" } else { "rename-replace-pair" };
        if checked { rename_checked(&from, &to).unwrap(); } else { fs::rename(&from, &to).unwrap(); }
        absent(&from); assert_eq!(fs::read(&to).unwrap(), b"rename fixture");
        if checked { rename_checked(&to, &from).unwrap(); } else { fs::rename(&to, &from).unwrap(); }
        absent(&to); assert_eq!(fs::read(&from).unwrap(), b"rename fixture");
        samples(label, count, || {
            if checked { rename_checked(&from, &to).unwrap(); rename_checked(&to, &from).unwrap(); }
            else { fs::rename(&from, &to).unwrap(); fs::rename(&to, &from).unwrap(); }
            1
        });
        assert_eq!(fs::read(&from).unwrap(), b"rename fixture"); absent(&to);
    }
    for label in ["rename-noreplace-pair", "root-rename-replace-pair", "root-rename-parents-sync-pair", "root-rename-noreplace-pair"] {
        for sample in 0..7 { println!("{label}\t{sample}\t0\t0\tunsupported"); }
    }
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(args.len(), 3);
    let root = Path::new(&args[1]); let count: u64 = args[2].parse().unwrap();
    assert!((1..=1_000_000).contains(&count));
    for size in [0usize, 64, 4096, 65536, 1048576] {
        let path = root.join(format!("read-{size}"));
        let mut reused = fs::read(&path).unwrap(); validate(&reused);
        samples(&format!("read-fresh-{size}"), count, || {
            let data = fs::read(&path).unwrap(); assert_eq!(data.len(), size);
            let value = checksum(&data); black_box(data); value
        });
        samples(&format!("read-reuse-{size}"), count, || {
            reused.clear(); fs::File::open(&path).unwrap().read_to_end(&mut reused).unwrap();
            assert_eq!(reused.len(), size); checksum(black_box(&reused))
        });
        validate(&reused);
        let file = fs::File::open(&path).unwrap();
        samples(&format!("read-retained-{size}"), count, || {
            assert_eq!(file.read_at(&mut reused, 0).unwrap(), size);
            checksum(black_box(&reused))
        });
        validate(&reused);
    }
    for entries in [0usize, 1, 128, 4096] {
        let path = root.join(format!("list-{entries}"));
        let expected: Vec<_> = (0..entries).map(|i| format!("entry-{i:04}").into()).collect::<Vec<std::ffi::OsString>>();
        let list = || {
            let mut names = fs::read_dir(&path).unwrap().map(|e| e.unwrap().file_name()).collect::<Vec<_>>();
            names.sort(); names
        };
        assert_eq!(list(), expected);
        samples(&format!("list-sorted-{entries}"), count, || {
            let names = list();
            let sum = names.iter().map(|n| checksum(n.as_encoded_bytes())).sum();
            black_box(names); sum
        });
    }
    let file = root.join("read-64");
    samples("metadata-file", count, || {
        let info = fs::symlink_metadata(&file).unwrap(); assert!(info.is_file()); assert_eq!(info.len(), 64);
        black_box(info); 65
    });
    let locked = fs::File::open(&file).unwrap();
    samples("lock-exclusive-pair", count, || {
        locked.try_lock().unwrap(); locked.unlock().unwrap(); 1
    });
    let directory = root.join("list-0");
    samples("is-dir", count, || { assert!(directory.is_dir()); 1 });
    for label in ["root-read-fresh-64", "root-metadata-file", "root-list-sorted-128"] {
        for sample in 0..7 { println!("{label}\t{sample}\t0\t0\tunsupported"); }
    }
    rename_cases(&root.join("rename"), count);
    file_setters(&root.join("file-metadata"), count);
    let status = fs::read_to_string("/proc/self/status").unwrap();
    for line in status.lines().filter(|s| s.starts_with("VmHWM:")) { println!("MEMORY\t{line}"); }
}
