---
status: active
tags: [reading, kernel]
---
# Kernel Scheduler

Notes on how a kernel scheduler picks the next task. The scheduler keeps a run queue,
and the kernel timer interrupt triggers a context switch. See [[Home]].

A round robin scheduler gives each task the same time slice. A priority scheduler does not.
