// SPDX-License-Identifier: Apache-2.0
mod adapter;
use std::{io::Write, os::unix::ffi::OsStrExt, time::Instant};
fn value(p: &[u8]) -> u64 {
    p.len() as u64 + p.first().copied().unwrap_or(0) as u64 + p.last().copied().unwrap_or(0) as u64
}
fn fresh_value(path: &[u8], limit: i64, expected: i32) -> u64 {
    let mut out = Vec::new();
    let s = adapter::bounded_read(path, limit, &mut out);
    assert_eq!(s.code, expected);
    if expected != 0 {
        assert!(out.is_empty());
    }
    value(&out) + (expected + 1) as u64
}
#[cfg(adaptertest)]
unsafe extern "C" {
    fn contract_fault_finish();
}
fn main() {
    let a: Vec<_> = std::env::args_os().collect();
    if a.len() == 5 && (a[1] == "probe" || a[1] == "growth" || a[1] == "empty-probe") {
        let hex = a[2].as_bytes();
        assert_eq!(hex.len() % 2, 0);
        let path: Vec<u8> = hex
            .chunks(2)
            .map(|b| u8::from_str_radix(std::str::from_utf8(b).unwrap(), 16).unwrap())
            .collect();
        let limit: i64 = a[3].to_str().unwrap().parse().unwrap();
        let mut loops: usize = a[4].to_str().unwrap().parse().unwrap();
        if a[1] != "growth" {
            assert!((1..=10000).contains(&loops));
        }
        let before = std::fs::read_dir("/proc/self/fd").unwrap().count();
        let mut out = b"sentinel".to_vec();
        if a[1] == "empty-probe" {
            out = Vec::new();
        }
        if a[1] == "growth" {
            assert!((0..=1048576).contains(&limit) && loops <= limit as usize);
            out = vec![165; limit as usize];
            out.truncate(loops);
            loops = 1;
        }
        let mut s = adapter::Status { code: 0, error: 0 };
        for _ in 0..loops {
            if a[1] == "empty-probe" {
                out = Vec::new();
            }
            s = adapter::bounded_read(&path, limit, &mut out);
        }
        #[cfg(adaptertest)]
        unsafe {
            contract_fault_finish();
        }
        let after = std::fs::read_dir("/proc/self/fd").unwrap().count();
        println!(
            "{}\t{}\t{}\t{}\t{}",
            s.code,
            s.error,
            out.len(),
            before,
            after
        );
        std::io::stdout().write_all(&out).unwrap();
        return;
    }
    assert!(a.len() == 6 && (a[1] == "measure" || a[1] == "fresh"));
    let path = a[2].as_bytes();
    let limit: i64 = a[3].to_str().unwrap().parse().unwrap();
    let expected: i32 = a[4].to_str().unwrap().parse().unwrap();
    let count: u64 = a[5].to_str().unwrap().parse().unwrap();
    assert!((1..=1000000).contains(&count));
    let mut out = Vec::new();
    if a[1] == "fresh" {
        let _ = fresh_value(path, limit, expected);
    } else {
        let s = adapter::bounded_read(path, limit, &mut out);
        assert_eq!(s.code, expected);
    }
    for sample in 0..7 {
        let start = Instant::now();
        let mut sum = 0;
        if a[1] == "fresh" {
            for _ in 0..count {
                sum += fresh_value(path, limit, expected);
            }
        } else {
            for _ in 0..count {
                let s = adapter::bounded_read(path, limit, &mut out);
                assert_eq!(s.code, expected);
                if expected != 0 {
                    assert!(out.is_empty());
                }
                sum += value(&out) + (expected + 1) as u64;
            }
        }
        println!(
            "{}\t{}\t{}",
            sample,
            start.elapsed().as_nanos() / count as u128,
            sum
        );
    }
}
