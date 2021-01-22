# Install macOS Docker Virtualization
## Setup
This walks through setting up QEMU virtualization for running macOS in Docker & Kubernetes

Please note, this guide assumes the host operation system is running Centos 7 (or ClearOS 7 more specifically). These commands can mostly be transferred to other distros, but there are a few areas that need commands (i.e. updating )

### Host configuration

## Build QEMU and libvirt from source

Since there is no official QEMU 5.X repo it appears, build from source.

### QEMU Requirements

Python, glib2-devel, and pixman

```
sudo yum install python glib2-devel cairo-devel -y
```

Ninja

```
pip3 install ninja
```

### Build QEMU from source steps

Clone the offical QEMU repo and build from source:

```
git clone git://git.qemu-project.org/qemu.git
cd qemu
mkdir -p bin/debug/native
cd bin/debug/native
../../../configure --enable-debug
make -j24
make install
```

_Note: adjust make to use the desired number of threads avaliable on your system_

### libvirt Requirements

Configure repo:

```
yum-config-manager --nogpgcheck --add-repo http://mirror.centos.org/centos/7/virt/x86_64/libvirt-latest/
```

### Install libvirt

```
yum install libvirt -y
```

### Update permissions

```
chmod 660 -R /dev/kvm && chown 1000:1000 /dev/kvm
usermod -a -G kvm root
```

_Note: these may not be required_

### Verification

Ensure latest version installed

```
virsh -c qemu:///system version --daemon
```

* For example, should output something like:

    ```
    [root@server repos]# virsh -c qemu:///system version --daemon
    Compiled against library: libvirt 5.0.0
    Using library: libvirt 5.0.0
    Using API: QEMU 5.0.0
    Running hypervisor: QEMU 5.2.50
    Running against daemon: 5.0.0
    ```

## Install IMMO for GPU passthrough

1. Modify GRUB boot args:

    Add the following to `/etc/default/grub` to the end of the `GRUB_CMDLINE_LINUX` parameter:
    
    ```
    GRUB_CMDLINE_LINUX="... iommu=pt intel_iommu=on"
    ```

1. Update GRUB2:

    ```
    grub2-mkconfig -o /boot/efi/EFI/clearos/grub.cfg
    ```

    _Note: this command may vary based on location of the grub.cfg for the boot entry_

1. Reboot system

1. Ensure that the kernel parameter changes worked:

    ```
    cat /proc/cmdline
    ```

1. Find GPU hardware ids with `lspci`

    Example:
    ```
    lspci -nn | grep -i nvidia
    ```

1. Add the hardware ids to `/etc/modprobe.d/vfio.conf`

    Example:
    ```
    options vfio-pci ids=10de:1b81,10de:10f0
    ```

    _Note: this is for the NVIDIA GTX 1070_

1. Enable `vfio-pci`

    ```
    echo 'vfio-pci' > /etc/modules-load.d/vfio-pci.conf
    ```

    Make backup and rebuild `initramfs`:

    ```
    cp -p /boot/initramfs-$(uname -r).img /boot/initramfs-$(uname -r).img.bak
    dracut -f 
    ```

    _Note: `dracut -f` may take awhile.._

1. Increase ulimits

    _This is done to avoid memory issues like `VFIO_MAP_DMA: -12` and etc_

    Append the following to `/etc/security/limits.conf`:

    ```
    @kvm            soft    memlock         unlimited
    @kvm            hard    memlock         unlimited
    ```

    Append the following to `/etc/docker/daemon.json`:

    ```
    {
        "default-ulimits": {
            "nofile": {
                "name": "nofile",
                "hard": 65536,
                "soft": 1024
            },
            "memlock":
            {
                "name": "memlock",
                "soft": -1,
                "hard": -1
            }
        }
    }
    ```

    Add `LimitMEMLOCK` to `/etc/systemd/system/multi-user.target.wants/libvirtd.service` like:

    ```
    [Unit]
    Description=Virtualization daemon
    ...

    [Service]
    ...
    LimitMEMLOCK=infinity
    ```

1. Reload systemd after changing config

    ```
    systemctl daemon-reload
    ```

1. Reboot system

1. Ensure that `vfio` worked

    ```
    dmesg | grep -i vfio
    ```

# Issues

Many issues can rise up as a result of adding the complexity layers involved here. Some of the main areas are improperly loading the `vfio-pci` driver for the GPU and permission issues.

## Modules for vfio not loading

When `vfio` does not load, errors such as the following can be seen:

```
error getting device from group *: No such device
Verify all devices in group * are bound to vfio-<bus> or pci-stub and not already in use
```

This can show up when `vfio-pci` driver is not loaded for the peripheral. Ensure that `vfio-pci` is loaded.

```
dmesg | grep -i vfio
```

If so, explicitly tell `vfio` modules to start

```
echo 'vfio
vfio_iommu_type1
vfio_pci
vfio_virqfd' > /etc/modules
```

Make backup and rebuild `initramfs`:

```
cp -p /boot/initramfs-$(uname -r).img /boot/initramfs-$(uname -r).img.bak
dracut -f 
```

_Note: `dracut -f` may take awhile.._

Do a system reboot

After rebooting, check on the gpu with `lspci` utilizing your gpu hardware id:

I.E.

```
[root@server docker-docker-osx]# lspci -vvv -s 09:00.0
09:00.0 VGA compatible controller: Advanced Micro Devices, Inc. [AMD/ATI] Ellesmere [Radeon RX 470/480/570/570X/580/580X/590] (rev c7) (prog-if 00 [VGA controller])
        Subsystem: Advanced Micro Devices, Inc. [AMD/ATI] Radeon RX 480
        Physical Slot: 5
        Control: I/O- Mem- BusMaster- SpecCycle- MemWINV- VGASnoop- ParErr+ Stepping- SERR+ FastB2B- DisINTx-
        Status: Cap+ 66MHz- UDF- FastB2B- ParErr- DEVSEL=fast >TAbort- <TAbort- <MAbort- >SERR- <PERR- INTx-
        Interrupt: pin A routed to IRQ 255
        ...
        Kernel driver in use: vfio-pci
        Kernel modules: amdgpu
```

_It does not matter if the host os loads a gpu module as seen with `Kernel modules: amdgpu` in the case above, the important part is that `vfio-pci` is the driver in use._

## Permissions on vfio and kvm

One of the biggest areas of pain can be setting permissions on `/dev/kvm`, `/dev/vfio/vfio`, or `/dev/vfio/<iommu_group>`. If permission errors are seen, try the following commands:

```
chmod 660 -R /dev/kvm && chown 1000:1000 /dev/kvm
chmod 777 -R /dev/vfio && chown 1000:1000 -R /dev/vfio
```

# References

https://gist.github.com/dghubble/c2dc319249b156db06aff1d49c15272e

`Configure IOMMU and vfio`
https://www.server-world.info/en/note?os=CentOS_7&p=kvm&f=10

`Configuring GPU driver with vfio-pci binding`
https://github.com/intel/nemu/wiki/Testing-VFIO-with-GPU

`IOMMU Interrupt Mapping`
https://pve.proxmox.com/wiki/Pci_passthrough#IOMMU_Interrupt_Remapping

`Manual Graphics Driver Binding`
https://lwn.net/Articles/143397/

`QEMU Stdio Example`
https://lists.gnu.org/archive/html/qemu-devel/2017-08/msg04521.html