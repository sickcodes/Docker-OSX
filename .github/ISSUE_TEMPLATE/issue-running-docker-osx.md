---
name: Issue Running Docker-OSX
about: OS related issued, please help us identify the issue by posting the output
  of this
title: ''
labels: ''
assignees: ''

---

# OS related issued, please help us identify the issue by posting the output of this
uname -a \
; echo "${DISPLAY}" \
; echo 1 | sudo tee /sys/module/kvm/parameters/ignore_msrs \
; grep NAME /etc/os-release \
; df -h . \
; qemu-system-x86_64 --version \
; libvirtd --version \
; free -mh \
; nproc \
; egrep -c '(svm|vmx)' /proc/cpuinfo \
; ls -lha /dev/kvm \
; ls -lha /tmp/.X11-unix/ \
; ps aux | grep dockerd \
; docker ps | grep osx \
; grep "docker\|kvm\|virt" /etc/group
