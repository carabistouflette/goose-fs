// SPDX-License-Identifier: Apache-2.0
use std::{fs, hint::black_box, io::Read, path::Path, time::Instant};
use std::os::unix::fs::FileExt;
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
    let directory = root.join("list-0");
    samples("is-dir", count, || { assert!(directory.is_dir()); 1 });
    let status = fs::read_to_string("/proc/self/status").unwrap();
    for line in status.lines().filter(|s| s.starts_with("VmHWM:")) { println!("MEMORY\t{line}"); }
}
