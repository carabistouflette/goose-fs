// SPDX-License-Identifier: Apache-2.0
#[cfg(not(all(target_os = "linux", target_arch = "x86_64")))]
compile_error!("read-contract supports Linux x86-64 only");
use std::ffi::{c_char, c_int, c_long};
use std::fs::File;
use std::io::Read;
use std::os::fd::{AsRawFd, FromRawFd, IntoRawFd, OwnedFd};
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Status {
    pub code: i32,
    pub error: i32,
}
const OK: Status = Status { code: 0, error: 0 };
const DIR: c_int = 0x200000 | 0x10000 | 0x80000;
const LEAF: c_int = 0x20000 | 0x800 | 0x100 | 0x80000;
#[repr(C)]
struct OpenHow {
    flags: u64,
    mode: u64,
    resolve: u64,
}
unsafe extern "C" {
    fn syscall(number: c_long, ...) -> c_long;
    fn openat(dir: c_int, path: *const c_char, flags: c_int, ...) -> c_int;
    fn close(fd: c_int) -> c_int;
    fn contract_fstat_mode(fd: c_int, mode: *mut u32) -> c_int;
}
fn os_error() -> i32 {
    std::io::Error::last_os_error().raw_os_error().unwrap()
}
fn system(error: i32) -> Status {
    Status { code: 4, error }
}
fn owned(fd: c_int) -> Result<OwnedFd, i32> {
    if fd < 0 {
        Err(os_error())
    } else {
        Ok(unsafe { OwnedFd::from_raw_fd(fd) })
    }
}
fn close_owned(fd: impl IntoRawFd) -> Result<(), i32> {
    let raw = fd.into_raw_fd();
    if unsafe { close(raw) } < 0 {
        Err(os_error())
    } else {
        Ok(())
    }
}
fn valid(path: &[u8]) -> bool {
    if path.is_empty() || path.len() > 4095 || path[0] != b'/' || path.contains(&0) {
        return false;
    }
    path.len() == 1
        || path[1..]
            .split(|&b| b == b'/')
            .all(|p| !p.is_empty() && p != b"." && p != b"..")
}
fn parent(text: &mut [u8; 4096], len: usize, separator: usize) -> Result<OwnedFd, i32> {
    text[separator] = 0;
    let directory = if separator == 0 {
        c"/".as_ptr()
    } else {
        text.as_ptr().cast()
    };
    let how = OpenHow {
        flags: DIR as u64,
        mode: 0,
        resolve: 4,
    };
    let result = owned(unsafe {
        syscall(
            437,
            -100 as c_int,
            directory,
            &how as *const OpenHow,
            std::mem::size_of::<OpenHow>(),
        )
    } as c_int);
    text[separator] = b'/';
    match result {
        Ok(fd) => return Ok(fd),
        Err(e) if e != 38 && e != 1 => return Err(e),
        _ => (),
    }
    let mut fd = owned(unsafe { openat(-100, c"/".as_ptr(), DIR) })?;
    let mut start = 1;
    for i in 1..len {
        if text[i] != b'/' {
            continue;
        }
        text[i] = 0;
        let next = owned(unsafe {
            openat(
                fd.as_raw_fd(),
                text.as_ptr().add(start).cast(),
                DIR | 0x20000,
            )
        });
        let closed = close_owned(fd);
        match (next, closed) {
            (Ok(n), Ok(())) => fd = n,
            (Ok(n), Err(e)) => {
                let _ = close_owned(n);
                return Err(e);
            }
            (Err(e), _) => return Err(e),
        }
        start = i + 1;
    }
    Ok(fd)
}
pub fn bounded_read(path: &[u8], limit: i64, out: &mut Vec<u8>) -> Status {
    if !valid(path) || !(0..=1048576).contains(&limit) {
        out.clear();
        return Status { code: 1, error: 0 };
    }
    let limit = limit as usize;
    out.resize(limit, 0);
    let mut text = [0u8; 4096];
    text[..path.len()].copy_from_slice(path);
    let separator = path.iter().rposition(|&b| b == b'/').unwrap();
    let dir = match parent(&mut text, path.len(), separator) {
        Ok(fd) => fd,
        Err(e) => {
            out.clear();
            return system(e);
        }
    };
    let leaf = if path.len() == 1 {
        c".".as_ptr()
    } else {
        unsafe { text.as_ptr().add(separator + 1).cast() }
    };
    let opened = owned(unsafe { openat(dir.as_raw_fd(), leaf, LEAF) });
    let mut used = 0;
    let mut result = match opened {
        Err(e) => system(e),
        Ok(fd) => {
            let mut file = File::from(fd);
            let mut mode = 0u32;
            let stat_error = unsafe { contract_fstat_mode(file.as_raw_fd(), &mut mode) };
            let mut status = if stat_error != 0 {
                system(stat_error)
            } else if mode & 0xf000 != 0x8000 {
                Status { code: 3, error: 0 }
            } else {
                OK
            };
            if status == OK {
                while used < limit {
                    match file.read(&mut out[used..]) {
                        Ok(0) => break,
                        Ok(n) => used += n,
                        Err(e) if e.raw_os_error() == Some(4) => continue,
                        Err(e) => {
                            status = system(e.raw_os_error().unwrap());
                            break;
                        }
                    }
                }
                if status == OK && used == limit {
                    let mut extra = [0u8; 1];
                    loop {
                        match file.read(&mut extra) {
                            Ok(0) => (),
                            Ok(_) => status = Status { code: 2, error: 0 },
                            Err(e) if e.raw_os_error() == Some(4) => continue,
                            Err(e) => status = system(e.raw_os_error().unwrap()),
                        }
                        break;
                    }
                }
            }
            if let Err(e) = close_owned(file) {
                if status == OK {
                    status = system(e);
                }
            }
            status
        }
    };
    let _ = close_owned(dir);
    if result.code == 0 {
        out.truncate(used);
    } else {
        out.clear();
    }
    // Non-system errors never expose stale errno.
    if result.code != 4 {
        result.error = 0;
    }
    result
}
