# How to Verify Seccomp Profile on OpenShift

## Method 1: Check Container Process (from inside pod)

### Get a shell in the running pg-airman-mcp pod
### Check the seccomp status of PID 1 (the main process)

```bash
oc exec -it deployment/pg-airman-mcp -n user-nmmzz-data-gov -- /bin/bash
cat /proc/1/status | grep Seccomp
```

**Output interpretation:**
```
Seccomp:    2    # 0 = disabled, 1 = strict, 2 = filter mode (good!)
```

## Method 2: Query Pod Spec

### Get the pod's actual seccomp configuration

```bash
oc get pod -n user-nmmzz-data-gov -l app.kubernetes.io/name=pg-airman-mcp -o json | \
  jq '.items[0].spec.securityContext.seccompProfile'
```

**Expected output:**
```json
{
  "type": "RuntimeDefault"
}
```

## Method 3: Test Blocked Syscall

```bash
# Try a syscall that should be blocked by seccomp
oc exec -it deployment/pg-airman-mcp -n user-nmmzz-data-gov -- python3 -c "
import ctypes
import os

# Load libc to make syscalls directly
libc = ctypes.CDLL(None)

# Get errno location
get_errno_loc = ctypes.CDLL(None).__errno_location
get_errno_loc.restype = ctypes.POINTER(ctypes.c_int)

# Try the reboot syscall (syscall number 169 on x86_64)
print('Testing seccomp with reboot syscall...')
result = libc.syscall(169, 0xfee1dead, 672274793, 0x1234567)

if result == -1:
    # Syscall failed - check errno
    errno_val = get_errno_loc()[0]
    if errno_val == 1:  # EPERM - Operation not permitted
        print(f'SUCCESS: Syscall blocked by seccomp (errno={errno_val}: {os.strerror(errno_val)})')
    else:
        print(f'Syscall failed with errno={errno_val}: {os.strerror(errno_val)}')
else:
    print(f'ERROR: Syscall succeeded (result={result}) - seccomp NOT working!')
"
```

**Expected output:**
```
Testing seccomp with reboot syscall...
SUCCESS: Syscall blocked by seccomp (errno=1: Operation not permitted)
```

**If seccomp is NOT working:**
```
ERROR: Syscall succeeded (result=0) - seccomp NOT working!
```

## What RuntimeDefault Blocks on OpenShift 4.20

The default CRI-O seccomp profile blocks these syscall categories:

### **Kernel Module Operations**
- `delete_module`, `init_module`, `finit_module`

### **System Reboot/Shutdown**
- `reboot`, `kexec_load`, `kexec_file_load`

### **Filesystem Operations**
- `mount`, `umount`, `umount2`, `pivot_root`

### **Swap Management**
- `swapon`, `swapoff`

### **Performance/Tracing**
- `perf_event_open`, `bpf`

### **Privileged Operations**
- `acct`, `quotactl`, `stime`, `settimeofday`

### **Process Manipulation**
- `ptrace` (in some configurations)

**Total:** ~44 syscalls blocked out of 300+ available

## Verifying the Profile Content

```bash
# On an OpenShift node, view the actual profile (NOTE: You will need node access to run this! Work with your sysadmin.)
oc debug node/<node-name>
chroot /host
cat /usr/share/containers/seccomp.json | jq '.' | less
```

**Key sections:**
```json
{
  "defaultAction": "SCMP_ACT_ERRNO",  // Block by default
  "defaultErrnoRet": 1,
  "syscalls": [
    {
      "names": ["accept", "accept4", ...],  // Allowed syscalls
      "action": "SCMP_ACT_ALLOW"
    },
    {
      "names": ["reboot", "mount", ...],    // Blocked syscalls
      "action": "SCMP_ACT_ERRNO"
    }
  ]
}
```

## Cross-Cluster Comparison

If deploying to multiple clusters with different runtimes:

```bash
# Create a test pod that prints syscall info
cat <<EOF | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: seccomp-test
spec:
  securityContext:
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: test
    image: ubuntu:22.04
    command: ["sleep", "3600"]
EOF

# Check what RuntimeDefault means on THIS cluster
oc exec seccomp-test -- cat /proc/1/status | grep Seccomp

# Cleanup
oc delete pod seccomp-test
```

## Summary

**On OpenShift 4.20:**
- RuntimeDefault → `/usr/share/containers/seccomp.json` (CRI-O)
- Profile blocks ~44 dangerous syscalls
- Mode: Filter (2) - whitelist approach
- Updated with each OpenShift release

**To verify:** Check `/proc/1/status | grep Seccomp` in your pod - should show `2`
