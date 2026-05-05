# Resource Limits Verification Guide

## Overview

This guide helps verify that CPU, memory, and ephemeral-storage resource limits are properly configured and enforced for the pg-airman-mcp container on OpenShift 4.20.

**Configured Limits (from values.yaml):**
```yaml
resources:
  requests:
    cpu: 250m
    memory: 256Mi
    ephemeral-storage: 1Gi
  limits:
    cpu: 500m
    memory: 512Mi
    ephemeral-storage: 2Gi
```

---

## Prerequisites

**For regular users:**
- Access to the namespace where pg-airman-mcp is deployed
- Ability to run `oc exec` into pods

**For administrators:**
- Cluster-admin privileges or namespace admin
- Ability to view pod metrics and events

---

## 1. Verify Resource Configuration

### Test 1.1: Inspect Configured Resources (User)

**Purpose:** Verify that resource limits are actually set on the container.

```bash
# Get the pod name
POD=$(oc get pods -n <namespace> -l app.kubernetes.io/name=pg-airman-mcp -o jsonpath='{.items[0].metadata.name}')

# Check configured resources
oc get pod $POD -n <namespace> -o jsonpath='{.spec.containers[0].resources}' | jq .
```

**Expected Output:**
```json
{
  "limits": {
    "cpu": "500m",
    "ephemeral-storage": "2Gi",
    "memory": "512Mi"
  },
  "requests": {
    "cpu": "250m",
    "ephemeral-storage": "1Gi",
    "memory": "256Mi"
  }
}
```

**✅ PASS:** All three resource types (cpu, memory, ephemeral-storage) have both requests and limits configured.

**❌ FAIL:** Missing resources or values don't match values.yaml.

---

### Test 1.2: View Resource Usage (User)

**Purpose:** Check current resource consumption against limits.

```bash
# Get current resource usage
oc adm top pod $POD -n <namespace> --containers
```

**Expected Output:**
```
POD                              NAME             CPU(cores)   MEMORY(bytes)
pg-airman-mcp-754b6b445b-bmcvk   pg-airman-mcp   5m           89Mi
```

**✅ PASS:** CPU and memory usage are well below limits (CPU < 500m, Memory < 512Mi).

**Note:** `oc adm top` doesn't show ephemeral-storage usage - we'll test that separately.

---

## 2. CPU Limits Verification

### Test 2.1: CPU Throttling Test (User)

**Purpose:** Attempt to consume more CPU than the limit and observe throttling.

```bash
# Run a CPU stress test that tries to use 1 full CPU (exceeds 500m limit)
oc exec $POD -n <namespace> -- python3 -c "
import time
import os

print('Starting CPU stress test...')
print(f'CPU limit: 500m (0.5 cores)')
print(f'Attempting to use 1 full core...')
print()

# Try to peg 1 CPU core
start = time.time()
iterations = 0
while time.time() - start < 10:  # Run for 10 seconds
    iterations += 1
    _ = sum(i*i for i in range(10000))

elapsed = time.time() - start
rate = iterations / elapsed
print(f'Completed {iterations} iterations in {elapsed:.2f}s')
print(f'Rate: {rate:.0f} iterations/second')
print()
print('If CPU was unlimited, rate would be higher.')
print('Throttling is working if rate seems constrained.')
"
```

**Expected Behavior:**
- The process will try to use 1 full CPU core
- Kubernetes will throttle it to max 500m (0.5 cores)
- Performance will be limited compared to unlimited CPU

**✅ PASS:** Process completes but runs slower due to throttling. No errors.

**❌ FAIL:** Process uses more than 0.5 CPU cores consistently (check with `oc adm top`).

---

### Test 2.2: Monitor CPU Throttling (Admin)

**Purpose:** View actual CPU throttling metrics.

```bash
# Check CPU throttling from cgroup metrics
oc exec $POD -n <namespace> -- sh -c "
cat /sys/fs/cgroup/cpu/cpu.stat 2>/dev/null || 
cat /sys/fs/cgroup/cpu.stat 2>/dev/null ||
echo 'CPU cgroup stats not accessible in this container'
"
```

**Expected Output (if accessible):**
```
nr_periods 1234
nr_throttled 567
throttled_time 123456789
```

**✅ PASS:** `nr_throttled > 0` indicates CPU throttling is occurring.

**Note:** Some containers may not have access to cgroup stats due to security restrictions.

---

## 3. Memory Limits Verification

### Test 3.1: Memory Usage Check (User)

**Purpose:** Verify current memory usage is within limits.

```bash
# Check memory usage from inside the container
oc exec $POD -n <namespace> -- python3 -c "
import os
import psutil

# Get memory info
mem = psutil.virtual_memory()
print(f'Memory Limit: 512 MiB (536870912 bytes)')
print(f'Current Usage: {mem.used / 1024 / 1024:.0f} MiB ({mem.used} bytes)')
print(f'Available: {mem.available / 1024 / 1024:.0f} MiB')
print(f'Percent Used: {mem.percent}%')
print()

if mem.used < 536870912:
    print('✅ Memory usage is within limits')
else:
    print('⚠️ Memory usage exceeds configured limit')
"
```

**Expected Output:**
```
Memory Limit: 512 MiB (536870912 bytes)
Current Usage: 89 MiB (93323264 bytes)
Available: 423 MiB
Percent Used: 17.4%

✅ Memory usage is within limits
```

**✅ PASS:** Memory usage is well below 512Mi limit.

---

### Test 3.2: Memory OOM Test (User)

**Purpose:** Attempt to allocate more memory than the limit and observe OOM kill.

**⚠️ WARNING:** This test will cause the container to be killed and restarted. Only run in non-production environments.

```bash
# Try to allocate 600Mi of memory (exceeds 512Mi limit)
oc exec $POD -n <namespace> -- python3 -c "
import time

print('Attempting to allocate 600 MiB of memory...')
print('Container limit is 512 MiB - expecting OOM kill')
print()

try:
    # Allocate memory in chunks
    chunks = []
    chunk_size = 50 * 1024 * 1024  # 50MB chunks
    total_allocated = 0
    
    for i in range(13):  # 13 * 50MB = 650MB
        chunks.append(bytearray(chunk_size))
        total_allocated += chunk_size
        print(f'Allocated: {total_allocated / 1024 / 1024:.0f} MiB')
        time.sleep(0.5)
    
    print('❌ FAIL: Memory allocation succeeded (should have been killed)')
except MemoryError:
    print('✅ Python MemoryError (container limit enforced)')
except KeyboardInterrupt:
    print('⚠️ Process interrupted')
"
```

**Expected Behavior:**
- Process will be killed by OOM killer when it exceeds 512Mi
- Pod will restart automatically
- You'll see connection lost or "command terminated with exit code 137"

**✅ PASS:** Process is killed with exit code 137 (OOM killed).

**❌ FAIL:** Process allocates more than 512Mi without being killed.

---

### Test 3.3: View OOM Events (Admin)

**Purpose:** Verify OOM kill events are recorded.

```bash
# Check pod events for OOM kills
oc get events -n <namespace> --field-selector involvedObject.name=$POD | grep -i oom
```

**Expected Output:**
```
5m    Warning   OOMKilling   pod/pg-airman-mcp-xxx   Memory cgroup out of memory: Killed process 1234 (python3)
```

**✅ PASS:** OOM events are visible in pod events.

---

## 4. Ephemeral Storage Limits Verification

### Test 4.1: Check Ephemeral Storage Usage (User)

**Purpose:** View current ephemeral storage usage.

```bash
# Check disk usage in container filesystem
oc exec $POD -n <namespace> -- sh -c "
echo 'Container Filesystem Usage:'
df -h / | tail -1
echo
echo 'Ephemeral Storage Limit: 2Gi'
echo 'Ephemeral Storage Request: 1Gi'
echo
echo 'Temporary Directory Usage:'
du -sh /tmp 2>/dev/null || echo '/tmp not accessible'
"
```

**Expected Output:**
```
Container Filesystem Usage:
/dev/vda1       100G   45G   55G   45% /

Ephemeral Storage Limit: 2Gi
Ephemeral Storage Request: 1Gi

Temporary Directory Usage:
12K     /tmp
```

**✅ PASS:** Usage is well below 2Gi limit.

---

### Test 4.2: Ephemeral Storage Limit Test (User)

**Purpose:** Attempt to write more than 2Gi of ephemeral storage and observe eviction.

**⚠️ WARNING:** This test will cause pod eviction. Only run in non-production environments.

```bash
# Try to write 2.5Gi of data to /tmp (exceeds 2Gi limit)
oc exec $POD -n <namespace> -- sh -c "
echo 'Attempting to write 2.5 GiB to /tmp...'
echo 'Ephemeral storage limit: 2 GiB'
echo 'Expecting pod eviction when limit exceeded'
echo

# Write in 100MB chunks
for i in \$(seq 1 26); do
    dd if=/dev/zero of=/tmp/testfile.\$i bs=1M count=100 2>/dev/null
    TOTAL=\$((i * 100))
    echo \"Written: \${TOTAL} MiB\"
    sleep 1
done

echo '❌ FAIL: Wrote 2.6 GiB without eviction'
"
```

**Expected Behavior:**
- Pod will be evicted when ephemeral storage exceeds 2Gi
- Connection will be lost
- Pod will be restarted by Kubernetes

**✅ PASS:** Pod is evicted before completing the write (connection lost).

**❌ FAIL:** Successfully writes more than 2Gi without eviction.

---

### Test 4.3: View Eviction Events (Admin)

**Purpose:** Verify pod eviction events due to ephemeral storage.

```bash
# Check for eviction events
oc get events -n <namespace> --field-selector involvedObject.name=$POD --sort-by='.lastTimestamp' | grep -i evict
```

**Expected Output:**
```
5m    Warning   Evicted   pod/pg-airman-mcp-xxx   Pod ephemeral local storage usage exceeds the total limit of containers 2Gi
```

**✅ PASS:** Eviction event is visible with reason related to ephemeral storage.

---

## 5. Resource Quota Interaction (Admin)

### Test 5.1: View Namespace Resource Quota

**Purpose:** Check if namespace-level quotas exist that could interact with pod limits.

```bash
# Check for ResourceQuota
oc get resourcequota -n <namespace>

# If quotas exist, view details
oc describe resourcequota -n <namespace>
```

**Expected Output:**
```
No resources found in <namespace> namespace.
```
OR
```
Name:            namespace-quota
Resource         Used   Hard
--------         ----   ----
requests.cpu     750m   4
requests.memory  768Mi  8Gi
limits.cpu       1500m  8
limits.memory    1536Mi 16Gi
```

**✅ PASS:** Either no quota exists, or pod limits fit within namespace quota.

**❌ FAIL:** Pod resource requests exceed namespace quota (pod won't schedule).

---

### Test 5.2: View LimitRange (Admin)

**Purpose:** Check for default limits or constraints imposed by LimitRange.

```bash
# Check for LimitRange objects
oc get limitrange -n <namespace>

# View details if they exist
oc describe limitrange -n <namespace>
```

**Expected Output:**
```
No resources found in <namespace> namespace.
```

**✅ PASS:** No conflicting LimitRange, or LimitRange doesn't override our explicit limits.

---

## 6. Quality of Service (QoS) Class

### Test 6.1: Verify QoS Class (User)

**Purpose:** Understand the pod's QoS class based on resource configuration.

```bash
# Check QoS class
oc get pod $POD -n <namespace> -o jsonpath='{.status.qosClass}'
echo
```

**Expected Output:**
```
Burstable
```

**Explanation:**
- **Guaranteed:** All containers have requests = limits for CPU and memory
- **Burstable:** At least one container has requests < limits (our case: cpu request 250m < limit 500m)
- **BestEffort:** No requests or limits set

**✅ PASS:** QoS class is `Burstable` (expected for our configuration).

**❌ FAIL:** QoS class is `BestEffort` (would indicate resources aren't set).

---

## 7. Real-World Stress Test

### Test 7.1: Combined Resource Stress (Admin)

**Purpose:** Test all three resource types simultaneously under realistic load.

```bash
# Run combined stress test
oc exec $POD -n <namespace> -- python3 -c "
import time
import threading
import os

print('Combined Resource Stress Test')
print('==============================')
print('CPU Limit: 500m (0.5 cores)')
print('Memory Limit: 512 MiB')
print('Ephemeral Storage Limit: 2 GiB')
print()

# CPU stress function
def cpu_stress():
    print('[CPU] Starting CPU stress...')
    for _ in range(100000000):
        _ = sum(i*i for i in range(100))
    print('[CPU] Completed')

# Memory stress function  
def memory_stress():
    print('[Memory] Allocating 300 MiB...')
    data = bytearray(300 * 1024 * 1024)
    time.sleep(5)
    print('[Memory] Holding memory for 5 seconds')
    del data

# Disk stress function
def disk_stress():
    print('[Disk] Writing 500 MiB to /tmp...')
    with open('/tmp/stress_test', 'wb') as f:
        f.write(os.urandom(500 * 1024 * 1024))
    print('[Disk] Write completed')
    os.remove('/tmp/stress_test')
    print('[Disk] Cleanup completed')

# Run all stress tests concurrently
print('Starting all stress tests...')
print()

t1 = threading.Thread(target=cpu_stress)
t2 = threading.Thread(target=memory_stress)
t3 = threading.Thread(target=disk_stress)

t1.start()
t2.start()
t3.start()

t1.join()
t2.join()
t3.join()

print()
print('✅ All stress tests completed successfully')
print('Container handled concurrent resource pressure within limits')
"
```

**Expected Behavior:**
- All three stress tests complete successfully
- Container remains stable under load
- Resources stay within configured limits

**✅ PASS:** All tests complete without OOM, eviction, or errors.

**❌ FAIL:** Container crashes, gets evicted, or kills processes.

---

## Summary Checklist

Use this checklist to verify all resource limits are working correctly:

- [ ] **Configuration:** Resources visible in pod spec (Test 1.1)
- [ ] **CPU Limits:** Throttling occurs when exceeding 500m (Test 2.1)
- [ ] **Memory Limits:** OOM kill occurs when exceeding 512Mi (Test 3.2)
- [ ] **Ephemeral Storage:** Eviction occurs when exceeding 2Gi (Test 4.2)
- [ ] **QoS Class:** Pod is classified as Burstable (Test 6.1)
- [ ] **Combined Load:** Container handles realistic multi-resource stress (Test 7.1)

---

## Troubleshooting

### Resources Not Configured

**Symptom:** Test 1.1 shows missing or incorrect limits.

**Solution:**
```bash
# Redeploy with updated values
make install

# Verify Helm rendered the template correctly
helm get values pg-airman-mcp -n <namespace>
```

---

### OOM Kills Not Happening

**Symptom:** Test 3.2 allows more than 512Mi allocation.

**Possible Causes:**
- Memory limit not actually enforced (check cgroup configuration)
- Python not allocating memory as expected
- Swap enabled (shouldn't be on OpenShift)

**Check:**
```bash
oc exec $POD -n <namespace> -- cat /sys/fs/cgroup/memory/memory.limit_in_bytes
# Should show 536870912 (512 MiB)
```

---

### Eviction Not Happening

**Symptom:** Test 4.2 writes more than 2Gi without eviction.

**Possible Causes:**
- Ephemeral storage monitoring disabled
- Kubelet not configured to enforce ephemeral storage
- Storage backend doesn't support quota enforcement

**Check:**
```bash
# Admin: Check kubelet configuration for ephemeral storage
oc get node <node-name> -o yaml | grep -A 5 ephemeral
```

---

## Additional Resources

- [Kubernetes Resource Management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [OpenShift Resource Quotas](https://docs.openshift.com/container-platform/4.20/applications/quotas/quotas-setting-per-project.html)
- [Quality of Service Classes](https://kubernetes.io/docs/tasks/configure-pod-container/quality-service-pod/)
- [Ephemeral Storage Management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/#local-ephemeral-storage)
